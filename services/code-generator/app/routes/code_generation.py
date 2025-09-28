"""
Code Generation API Routes
Handles REST and WebSocket endpoints for code generation
"""
import asyncio
import json
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, validator
import structlog

from app.core.config import Settings, CodeStack, AIProvider
from app.services.provider_manager import ProviderManager, GenerationRequest, GenerationMode
from app.services.prompt_engine import PromptEngine, PromptRequest, InputMode, GenerationType
from shared.monitoring.correlation import get_correlation_id, set_correlation_id
from shared.monitoring.structured_logger import StructuredLogger

router = APIRouter()

# Request/Response Models
class CodeGenerationRequest(BaseModel):
    """Request model for code generation"""
    image_data_url: Optional[str] = Field(None, description="Base64 encoded image data URL")
    result_image_data_url: Optional[str] = Field(None, description="Result image for updates")
    code_stack: CodeStack = Field(CodeStack.HTML_TAILWIND, description="Target code stack")
    provider: Optional[AIProvider] = Field(None, description="AI provider to use")
    input_mode: InputMode = Field(InputMode.IMAGE, description="Input mode")
    generation_type: GenerationType = Field(GenerationType.CREATE, description="Generation type")
    history: List[str] = Field(default_factory=list, description="Conversation history")
    imported_code: Optional[str] = Field(None, description="Imported code for modifications")
    additional_instructions: Optional[str] = Field(None, description="Additional instructions")
    temperature: float = Field(0.0, ge=0.0, le=2.0, description="Generation temperature")
    max_tokens: int = Field(4096, ge=1, le=8192, description="Maximum tokens")
    stream: bool = Field(True, description="Enable streaming response")
    
    @validator('image_data_url')
    def validate_image_url(cls, v):
        if v and not v.startswith('data:image/'):
            raise ValueError('Invalid image data URL format')
        return v
    
    @validator('result_image_data_url')
    def validate_result_image_url(cls, v):
        if v and not v.startswith('data:image/'):
            raise ValueError('Invalid result image data URL format')
        return v

class CodeGenerationResponse(BaseModel):
    """Response model for code generation"""
    success: bool
    code: str
    provider: str
    model: str
    duration_seconds: float
    token_usage: Optional[Dict[str, int]] = None
    correlation_id: str
    error: Optional[str] = None

class ProvidersResponse(BaseModel):
    """Response model for available providers"""
    providers: List[Dict[str, Any]]
    default_provider: str

class StacksResponse(BaseModel):
    """Response model for supported code stacks"""
    stacks: List[Dict[str, Any]]
    default_stack: str

# WebSocket Connection Manager
class ConnectionManager:
    """Manages WebSocket connections for streaming code generation"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.logger = structlog.get_logger()
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.logger.info("WebSocket connection established", 
                        client=websocket.client.host if websocket.client else "unknown")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            self.logger.info("WebSocket connection closed")
    
    async def send_message(self, websocket: WebSocket, message: dict):
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            self.logger.error("Failed to send WebSocket message", error=str(e))
            self.disconnect(websocket)

manager = ConnectionManager()

# Dependency injection
async def get_provider_manager(request) -> ProviderManager:
    """Get provider manager from app state"""
    return request.app.state.provider_manager

async def get_logger(request) -> StructuredLogger:
    """Get logger from app state"""
    return request.app.state.logger

# REST Endpoints
@router.get("/providers", response_model=ProvidersResponse)
async def get_available_providers(
    provider_manager: ProviderManager = Depends(get_provider_manager)
):
    """Get list of available AI providers"""
    available_providers = provider_manager.get_available_providers()
    default_provider = provider_manager.get_default_provider()
    
    providers_info = []
    for provider in available_providers:
        config = provider_manager.provider_configs.get(provider, {})
        providers_info.append({
            "id": provider.value,
            "name": provider.value.replace("_", " ").title(),
            "model": config.get("model", "unknown"),
            "max_tokens": config.get("max_tokens", 4096),
            "temperature": config.get("temperature", 0.0)
        })
    
    return ProvidersResponse(
        providers=providers_info,
        default_provider=default_provider.value if default_provider else ""
    )

@router.get("/stacks", response_model=StacksResponse)
async def get_supported_stacks():
    """Get list of supported code stacks"""
    prompt_engine = PromptEngine()
    supported_stacks = prompt_engine.get_supported_stacks()
    
    stacks_info = []
    for stack in supported_stacks:
        stacks_info.append({
            "id": stack.value,
            "name": stack.value.replace("_", " ").title(),
            "description": prompt_engine.get_stack_description(stack)
        })
    
    return StacksResponse(
        stacks=stacks_info,
        default_stack=CodeStack.HTML_TAILWIND.value
    )

@router.post("/generate", response_model=CodeGenerationResponse)
async def generate_code(
    request: CodeGenerationRequest,
    background_tasks: BackgroundTasks,
    provider_manager: ProviderManager = Depends(get_provider_manager),
    logger: StructuredLogger = Depends(get_logger)
):
    """Generate code from image using specified provider"""
    correlation_id = get_correlation_id()
    set_correlation_id(correlation_id)
    
    logger.info("Code generation request received",
                code_stack=request.code_stack.value,
                provider=request.provider.value if request.provider else "default",
                input_mode=request.input_mode.value,
                correlation_id=correlation_id)
    
    try:
        # Initialize prompt engine
        prompt_engine = PromptEngine()
        
        # Create prompt request
        prompt_request = PromptRequest(
            image_data_url=request.image_data_url,
            result_image_data_url=request.result_image_data_url,
            code_stack=request.code_stack,
            input_mode=request.input_mode,
            generation_type=request.generation_type,
            history=request.history,
            imported_code=request.imported_code,
            additional_instructions=request.additional_instructions
        )
        
        # Validate prompt request
        validation_issues = prompt_engine.validate_request(prompt_request)
        if validation_issues:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "validation_failed",
                    "issues": validation_issues,
                    "correlation_id": correlation_id
                }
            )
        
        # Generate prompt messages
        prompt_messages = prompt_engine.generate_prompt(prompt_request)
        
        # Determine provider
        selected_provider = request.provider or provider_manager.get_default_provider()
        if not provider_manager.is_provider_available(selected_provider):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "provider_unavailable",
                    "message": f"Provider {selected_provider.value} is not available",
                    "correlation_id": correlation_id
                }
            )
        
        # Create generation request
        generation_request = GenerationRequest(
            prompt_messages=prompt_messages,
            provider=selected_provider,
            stack=request.code_stack.value,
            mode=GenerationMode.CREATE if request.generation_type == GenerationType.CREATE else GenerationMode.UPDATE,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=False,  # Non-streaming for REST API
            correlation_id=correlation_id
        )
        
        # Generate code
        result = await provider_manager.generate_code(generation_request)
        
        if result.error:
            logger.error("Code generation failed", 
                        error=result.error,
                        provider=selected_provider.value,
                        correlation_id=correlation_id)
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "generation_failed", 
                    "message": result.error,
                    "correlation_id": correlation_id
                }
            )
        
        # Extract HTML content
        clean_code = prompt_engine.extract_html_content(result.content)
        
        logger.info("Code generation completed successfully",
                   provider=result.provider.value,
                   duration_seconds=result.duration_seconds,
                   correlation_id=correlation_id)
        
        return CodeGenerationResponse(
            success=True,
            code=clean_code,
            provider=result.provider.value,
            model=result.model,
            duration_seconds=result.duration_seconds,
            token_usage=result.token_usage,
            correlation_id=correlation_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error during code generation",
                    error=str(e),
                    correlation_id=correlation_id,
                    exc_info=e)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_server_error",
                "message": "An unexpected error occurred",
                "correlation_id": correlation_id
            }
        )

@router.post("/generate/stream")
async def stream_generate_code(
    request: CodeGenerationRequest,
    provider_manager: ProviderManager = Depends(get_provider_manager),
    logger: StructuredLogger = Depends(get_logger)
):
    """Stream code generation from image using specified provider"""
    correlation_id = get_correlation_id()
    set_correlation_id(correlation_id)
    
    async def generate():
        try:
            # Initialize prompt engine
            prompt_engine = PromptEngine()
            
            # Create prompt request
            prompt_request = PromptRequest(
                image_data_url=request.image_data_url,
                result_image_data_url=request.result_image_data_url,
                code_stack=request.code_stack,
                input_mode=request.input_mode,
                generation_type=request.generation_type,
                history=request.history,
                imported_code=request.imported_code,
                additional_instructions=request.additional_instructions
            )
            
            # Validate prompt request
            validation_issues = prompt_engine.validate_request(prompt_request)
            if validation_issues:
                yield f"data: {json.dumps({'error': 'validation_failed', 'issues': validation_issues})}\n\n"
                return
            
            # Generate prompt messages
            prompt_messages = prompt_engine.generate_prompt(prompt_request)
            
            # Determine provider
            selected_provider = request.provider or provider_manager.get_default_provider()
            if not provider_manager.is_provider_available(selected_provider):
                yield f"data: {json.dumps({'error': 'provider_unavailable'})}\n\n"
                return
            
            # Create generation request
            generation_request = GenerationRequest(
                prompt_messages=prompt_messages,
                provider=selected_provider,
                stack=request.code_stack.value,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=True,
                correlation_id=correlation_id
            )
            
            # Stream code generation
            accumulated_content = ""
            async for chunk in provider_manager.stream_code_generation(generation_request):
                accumulated_content += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            
            # Send completion message
            clean_code = prompt_engine.extract_html_content(accumulated_content)
            yield f"data: {json.dumps({'type': 'complete', 'code': clean_code})}\n\n"
            
        except Exception as e:
            logger.error("Streaming generation failed", 
                        error=str(e),
                        correlation_id=correlation_id)
            yield f"data: {json.dumps({'error': 'generation_failed', 'message': str(e)})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/plain")

# WebSocket Endpoints
@router.websocket("/ws/generate")
async def websocket_generate_code(
    websocket: WebSocket,
    provider_manager: ProviderManager = Depends(get_provider_manager),
    logger: StructuredLogger = Depends(get_logger)
):
    """WebSocket endpoint for real-time code generation"""
    await manager.connect(websocket)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            correlation_id = get_correlation_id()
            set_correlation_id(correlation_id)
            
            logger.info("WebSocket generation request received",
                       correlation_id=correlation_id)
            
            try:
                # Parse request
                request = CodeGenerationRequest(**message)
                
                # Initialize prompt engine
                prompt_engine = PromptEngine()
                
                # Create prompt request
                prompt_request = PromptRequest(
                    image_data_url=request.image_data_url,
                    result_image_data_url=request.result_image_data_url,
                    code_stack=request.code_stack,
                    input_mode=request.input_mode,
                    generation_type=request.generation_type,
                    history=request.history,
                    imported_code=request.imported_code,
                    additional_instructions=request.additional_instructions
                )
                
                # Validate prompt request
                validation_issues = prompt_engine.validate_request(prompt_request)
                if validation_issues:
                    await manager.send_message(websocket, {
                        "type": "error",
                        "error": "validation_failed",
                        "issues": validation_issues,
                        "correlation_id": correlation_id
                    })
                    continue
                
                # Generate prompt messages
                prompt_messages = prompt_engine.generate_prompt(prompt_request)
                
                # Determine provider
                selected_provider = request.provider or provider_manager.get_default_provider()
                if not provider_manager.is_provider_available(selected_provider):
                    await manager.send_message(websocket, {
                        "type": "error",
                        "error": "provider_unavailable",
                        "correlation_id": correlation_id
                    })
                    continue
                
                # Send start message
                await manager.send_message(websocket, {
                    "type": "start",
                    "provider": selected_provider.value,
                    "correlation_id": correlation_id
                })
                
                # Create generation request
                generation_request = GenerationRequest(
                    prompt_messages=prompt_messages,
                    provider=selected_provider,
                    stack=request.code_stack.value,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    stream=True,
                    correlation_id=correlation_id
                )
                
                # Stream code generation
                accumulated_content = ""
                async for chunk in provider_manager.stream_code_generation(generation_request):
                    accumulated_content += chunk
                    await manager.send_message(websocket, {
                        "type": "chunk",
                        "content": chunk,
                        "correlation_id": correlation_id
                    })
                
                # Send completion message
                clean_code = prompt_engine.extract_html_content(accumulated_content)
                await manager.send_message(websocket, {
                    "type": "complete",
                    "code": clean_code,
                    "correlation_id": correlation_id
                })
                
                logger.info("WebSocket generation completed",
                           correlation_id=correlation_id)
                
            except Exception as e:
                logger.error("WebSocket generation failed",
                            error=str(e),
                            correlation_id=correlation_id)
                await manager.send_message(websocket, {
                    "type": "error",
                    "error": "generation_failed",
                    "message": str(e),
                    "correlation_id": correlation_id
                })
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error("WebSocket error", error=str(e))
        manager.disconnect(websocket)

@router.websocket("/ws/multi-generate")
async def websocket_multi_generate_code(
    websocket: WebSocket,
    provider_manager: ProviderManager = Depends(get_provider_manager),
    logger: StructuredLogger = Depends(get_logger)
):
    """WebSocket endpoint for multi-variant code generation"""
    await manager.connect(websocket)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            correlation_id = get_correlation_id()
            set_correlation_id(correlation_id)
            
            # Parse variants count and providers
            variants = message.get("variants", 1)
            providers = message.get("providers", [])
            
            # Limit variants
            max_variants = 3
            variants = min(variants, max_variants)
            
            if not providers:
                available_providers = provider_manager.get_available_providers()
                providers = [p.value for p in available_providers[:variants]]
            
            logger.info("Multi-variant generation request received",
                       variants=variants,
                       providers=providers,
                       correlation_id=correlation_id)
            
            try:
                # Parse base request
                base_request = CodeGenerationRequest(**message)
                
                # Send start message
                await manager.send_message(websocket, {
                    "type": "multi_start",
                    "variants": variants,
                    "providers": providers,
                    "correlation_id": correlation_id
                })
                
                # Generate multiple variants concurrently
                tasks = []
                for i, provider_name in enumerate(providers[:variants]):
                    provider = AIProvider(provider_name)
                    if provider_manager.is_provider_available(provider):
                        task = asyncio.create_task(
                            generate_variant(
                                websocket, base_request, provider, i,
                                provider_manager, logger, correlation_id
                            )
                        )
                        tasks.append(task)
                
                # Wait for all variants to complete
                await asyncio.gather(*tasks, return_exceptions=True)
                
                # Send completion message
                await manager.send_message(websocket, {
                    "type": "multi_complete",
                    "correlation_id": correlation_id
                })
                
            except Exception as e:
                logger.error("Multi-variant generation failed",
                            error=str(e),
                            correlation_id=correlation_id)
                await manager.send_message(websocket, {
                    "type": "error",
                    "error": "multi_generation_failed",
                    "message": str(e),
                    "correlation_id": correlation_id
                })
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error("WebSocket error", error=str(e))
        manager.disconnect(websocket)

async def generate_variant(
    websocket: WebSocket, 
    request: CodeGenerationRequest,
    provider: AIProvider,
    variant_index: int,
    provider_manager: ProviderManager,
    logger: StructuredLogger,
    correlation_id: str
):
    """Generate a single variant for multi-generation"""
    try:
        # Initialize prompt engine
        prompt_engine = PromptEngine()
        
        # Create prompt request
        prompt_request = PromptRequest(
            image_data_url=request.image_data_url,
            result_image_data_url=request.result_image_data_url,
            code_stack=request.code_stack,
            input_mode=request.input_mode,
            generation_type=request.generation_type,
            history=request.history,
            imported_code=request.imported_code,
            additional_instructions=request.additional_instructions
        )
        
        # Generate prompt messages
        prompt_messages = prompt_engine.generate_prompt(prompt_request)
        
        # Create generation request
        generation_request = GenerationRequest(
            prompt_messages=prompt_messages,
            provider=provider,
            stack=request.code_stack.value,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=True,
            correlation_id=correlation_id
        )
        
        # Send variant start message
        await manager.send_message(websocket, {
            "type": "variant_start",
            "variant": variant_index,
            "provider": provider.value,
            "correlation_id": correlation_id
        })
        
        # Stream code generation
        accumulated_content = ""
        async for chunk in provider_manager.stream_code_generation(generation_request):
            accumulated_content += chunk
            await manager.send_message(websocket, {
                "type": "variant_chunk",
                "variant": variant_index,
                "content": chunk,
                "correlation_id": correlation_id
            })
        
        # Send variant completion message
        clean_code = prompt_engine.extract_html_content(accumulated_content)
        await manager.send_message(websocket, {
            "type": "variant_complete",
            "variant": variant_index,
            "code": clean_code,
            "provider": provider.value,
            "correlation_id": correlation_id
        })
        
    except Exception as e:
        logger.error("Variant generation failed",
                    variant=variant_index,
                    provider=provider.value,
                    error=str(e),
                    correlation_id=correlation_id)
        await manager.send_message(websocket, {
            "type": "variant_error",
            "variant": variant_index,
            "error": str(e),
            "correlation_id": correlation_id
        })