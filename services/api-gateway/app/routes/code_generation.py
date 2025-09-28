"""
Code Generation Routes
Proxy routes for code generation service
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, Request, HTTPException, Depends, File, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from app.services.service_client import ServiceClient, RequestResult
from shared.monitoring.correlation import get_correlation_id

router = APIRouter()

# Request/Response models
class CodeGenerationRequest(BaseModel):
    """Request model for code generation"""
    image: Optional[str] = Field(None, description="Base64 encoded image or image URL")
    code_stack: str = Field(..., description="Target code stack (html_tailwind, react_tailwind, etc.)")
    generation_type: str = Field(default="create", description="Generation type (create, update, refine)")
    additional_instructions: Optional[str] = Field(None, description="Additional instructions for generation")
    should_generate_images: bool = Field(default=False, description="Whether to generate images for missing assets")
    user_preferences: Optional[Dict[str, Any]] = Field(default=None, description="User preferences")

class CodeGenerationResponse(BaseModel):
    """Response model for code generation"""
    id: str = Field(..., description="Generation ID")
    code: str = Field(..., description="Generated code")
    status: str = Field(..., description="Generation status")
    code_stack: str = Field(..., description="Code stack used")
    provider: str = Field(..., description="AI provider used")
    generation_time_ms: float = Field(..., description="Generation time in milliseconds")
    token_usage: Optional[Dict[str, int]] = Field(None, description="Token usage statistics")
    images_generated: Optional[List[str]] = Field(None, description="URLs of generated images")

def get_service_client(request: Request) -> ServiceClient:
    """Dependency to get service client from app state"""
    return request.app.state.service_client

def get_logger(request: Request):
    """Dependency to get logger from app state"""
    return request.app.state.logger

@router.post("/code/generate", response_model=CodeGenerationResponse)
async def generate_code(
    request_data: CodeGenerationRequest,
    request: Request,
    service_client: ServiceClient = Depends(get_service_client),
    logger = Depends(get_logger)
) -> JSONResponse:
    """Generate code from screenshot"""
    correlation_id = get_correlation_id()
    
    logger.info("Code generation request received",
                code_stack=request_data.code_stack,
                generation_type=request_data.generation_type,
                should_generate_images=request_data.should_generate_images,
                correlation_id=correlation_id)
    
    try:
        # Add user context from authentication middleware
        payload = request_data.dict()
        if hasattr(request.state, "user_id"):
            payload["user_id"] = request.state.user_id
            payload["tenant_id"] = getattr(request.state, "tenant_id", None)
        
        # Call code generation service
        result: RequestResult = await service_client.call_code_generator(
            method="POST",
            path="/generate",
            data=payload
        )
        
        if not result.success:
            logger.error("Code generation failed",
                        error=result.error,
                        status_code=result.status_code,
                        correlation_id=correlation_id)
            
            raise HTTPException(
                status_code=result.status_code or 500,
                detail=result.error or "Code generation failed"
            )
        
        logger.info("Code generation completed successfully",
                   generation_id=result.data.get("id"),
                   duration_ms=result.duration_ms,
                   correlation_id=correlation_id)
        
        return JSONResponse(content=result.data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in code generation",
                    error=str(e),
                    correlation_id=correlation_id)
        
        raise HTTPException(
            status_code=500,
            detail="Internal server error during code generation"
        )

@router.post("/code/upload-and-generate")
async def upload_and_generate_code(
    file: UploadFile = File(...),
    code_stack: str = "html_tailwind",
    generation_type: str = "create",
    additional_instructions: Optional[str] = None,
    should_generate_images: bool = False,
    request: Request = None,
    service_client: ServiceClient = Depends(get_service_client),
    logger = Depends(get_logger)
) -> JSONResponse:
    """Upload image file and generate code"""
    correlation_id = get_correlation_id()
    
    logger.info("File upload and code generation request",
                filename=file.filename,
                content_type=file.content_type,
                code_stack=code_stack,
                correlation_id=correlation_id)
    
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail="File must be an image"
            )
        
        # Read and encode file
        import base64
        file_content = await file.read()
        encoded_image = base64.b64encode(file_content).decode("utf-8")
        
        # Prepare request
        payload = {
            "image": f"data:{file.content_type};base64,{encoded_image}",
            "code_stack": code_stack,
            "generation_type": generation_type,
            "additional_instructions": additional_instructions,
            "should_generate_images": should_generate_images
        }
        
        # Add user context
        if hasattr(request.state, "user_id"):
            payload["user_id"] = request.state.user_id
            payload["tenant_id"] = getattr(request.state, "tenant_id", None)
        
        # Call code generation service
        result: RequestResult = await service_client.call_code_generator(
            method="POST",
            path="/generate",
            data=payload
        )
        
        if not result.success:
            logger.error("Upload and generation failed",
                        error=result.error,
                        status_code=result.status_code,
                        correlation_id=correlation_id)
            
            raise HTTPException(
                status_code=result.status_code or 500,
                detail=result.error or "Code generation failed"
            )
        
        logger.info("Upload and generation completed",
                   generation_id=result.data.get("id"),
                   file_size=len(file_content),
                   duration_ms=result.duration_ms,
                   correlation_id=correlation_id)
        
        return JSONResponse(content=result.data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in upload and generation",
                    error=str(e),
                    correlation_id=correlation_id)
        
        raise HTTPException(
            status_code=500,
            detail="Internal server error during upload and generation"
        )

@router.get("/code/generation/{generation_id}")
async def get_generation_status(
    generation_id: str,
    request: Request,
    service_client: ServiceClient = Depends(get_service_client),
    logger = Depends(get_logger)
) -> JSONResponse:
    """Get status of a code generation request"""
    correlation_id = get_correlation_id()
    
    try:
        result: RequestResult = await service_client.call_code_generator(
            method="GET",
            path=f"/generation/{generation_id}"
        )
        
        if not result.success:
            if result.status_code == 404:
                raise HTTPException(status_code=404, detail="Generation not found")
            
            raise HTTPException(
                status_code=result.status_code or 500,
                detail=result.error or "Failed to get generation status"
            )
        
        return JSONResponse(content=result.data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting generation status",
                    generation_id=generation_id,
                    error=str(e),
                    correlation_id=correlation_id)
        
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )

@router.get("/code/variants")
async def get_code_variants(
    request: Request,
    service_client: ServiceClient = Depends(get_service_client)
) -> JSONResponse:
    """Get available code generation variants/templates"""
    try:
        result: RequestResult = await service_client.call_code_generator(
            method="GET",
            path="/variants"
        )
        
        if not result.success:
            raise HTTPException(
                status_code=result.status_code or 500,
                detail=result.error or "Failed to get code variants"
            )
        
        return JSONResponse(content=result.data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )

@router.post("/code/refine/{generation_id}")
async def refine_generated_code(
    generation_id: str,
    refinement_instructions: Dict[str, Any],
    request: Request,
    service_client: ServiceClient = Depends(get_service_client),
    logger = Depends(get_logger)
) -> JSONResponse:
    """Refine previously generated code"""
    correlation_id = get_correlation_id()
    
    logger.info("Code refinement request",
                generation_id=generation_id,
                correlation_id=correlation_id)
    
    try:
        # Add user context
        payload = refinement_instructions.copy()
        if hasattr(request.state, "user_id"):
            payload["user_id"] = request.state.user_id
        
        result: RequestResult = await service_client.call_code_generator(
            method="POST",
            path=f"/refine/{generation_id}",
            data=payload
        )
        
        if not result.success:
            if result.status_code == 404:
                raise HTTPException(status_code=404, detail="Generation not found")
            
            raise HTTPException(
                status_code=result.status_code or 500,
                detail=result.error or "Code refinement failed"
            )
        
        logger.info("Code refinement completed",
                   generation_id=generation_id,
                   duration_ms=result.duration_ms,
                   correlation_id=correlation_id)
        
        return JSONResponse(content=result.data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in code refinement",
                    generation_id=generation_id,
                    error=str(e),
                    correlation_id=correlation_id)
        
        raise HTTPException(
            status_code=500,
            detail="Internal server error during refinement"
        )