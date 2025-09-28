"""
Code Generation Service
High-level service for orchestrating AI-powered code generation
"""
import asyncio
from typing import Dict, List, Optional, Any, Set, AsyncIterator
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
import uuid
import time

from .model_types import (
    AIModelType, AIModelCapability, ModelProvider,
    GenerationFramework, GenerationQuality,
    ModelRequest, ModelResponse, GenerationOptions,
    create_request_id, validate_image_data
)
from .model_manager import AIModelManager
from .providers import (
    BaseModelProvider, OpenAIProvider, AnthropicProvider,
    GoogleProvider, AzureProvider, HuggingFaceProvider,
    LocalModelProvider
)

try:
    from shared.monitoring.structured_logger import StructuredLogger
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger


@dataclass
class GenerationContext:
    """Context information for code generation"""
    user_id: str
    session_id: Optional[str] = None
    project_id: Optional[str] = None
    
    # Generation preferences
    preferred_providers: List[ModelProvider] = field(default_factory=list)
    fallback_providers: List[ModelProvider] = field(default_factory=list)
    
    # Quality requirements
    min_quality_score: float = 0.7
    require_validation: bool = True
    
    # Performance settings
    max_wait_time_seconds: int = 30
    enable_caching: bool = True
    
    # Custom settings
    custom_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationResult:
    """Result of code generation process"""
    request_id: str
    success: bool
    
    # Generated content
    html_code: Optional[str] = None
    css_code: Optional[str] = None
    js_code: Optional[str] = None
    raw_code: Optional[str] = None
    
    # Generation metadata
    model_used: Optional[str] = None
    provider_used: Optional[str] = None
    generation_time_ms: int = 0
    
    # Quality metrics
    quality_score: float = 0.0
    confidence_score: float = 0.0
    validation_passed: bool = False
    
    # Analysis results
    detected_elements: List[Dict[str, Any]] = field(default_factory=list)
    detected_patterns: List[str] = field(default_factory=list)
    suggested_improvements: List[str] = field(default_factory=list)
    
    # Error information
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    
    # Cost information
    estimated_cost: float = 0.0
    token_usage: Dict[str, int] = field(default_factory=dict)
    
    # Timestamps
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.completed_at is None:
            self.completed_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "request_id": self.request_id,
            "success": self.success,
            "generated_code": {
                "html": self.html_code,
                "css": self.css_code,
                "js": self.js_code,
                "raw": self.raw_code
            },
            "metadata": {
                "model_used": self.model_used,
                "provider_used": self.provider_used,
                "generation_time_ms": self.generation_time_ms,
                "quality_score": self.quality_score,
                "confidence_score": self.confidence_score,
                "validation_passed": self.validation_passed,
                "estimated_cost": self.estimated_cost,
                "token_usage": self.token_usage
            },
            "analysis": {
                "detected_elements": self.detected_elements,
                "detected_patterns": self.detected_patterns,
                "suggested_improvements": self.suggested_improvements
            },
            "error": {
                "message": self.error_message,
                "code": self.error_code
            } if self.error_message else None,
            "timestamps": {
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "completed_at": self.completed_at.isoformat() if self.completed_at else None
            }
        }


class GenerationPipeline:
    """Pipeline for processing generation requests"""
    
    def __init__(self, model_manager: AIModelManager, logger: StructuredLogger):
        self.model_manager = model_manager
        self.logger = logger
        self._providers: Dict[str, BaseModelProvider] = {}
        self._request_cache: Dict[str, GenerationResult] = {}
        self._cache_ttl = 3600  # 1 hour
    
    async def initialize_providers(self):
        """Initialize all available providers"""
        # This would be done based on configuration
        # For now, we'll simulate provider initialization
        self.logger.info("Generation pipeline initialized")
    
    async def process_request(self, 
                            request: ModelRequest, 
                            context: GenerationContext) -> GenerationResult:
        """Process a code generation request"""
        start_time = time.time()
        
        try:
            # Check cache first
            if context.enable_caching:
                cached_result = await self._check_cache(request)
                if cached_result:
                    self.logger.info("Returning cached result",
                                   request_id=request.request_id)
                    return cached_result
            
            # Select best model for request
            model_id = await self._select_model(request, context)
            if not model_id:
                return GenerationResult(
                    request_id=request.request_id,
                    success=False,
                    error_message="No suitable model available",
                    error_code="NO_MODEL_AVAILABLE"
                )
            
            # Get provider for model
            provider = await self._get_provider(model_id)
            if not provider:
                return GenerationResult(
                    request_id=request.request_id,
                    success=False,
                    error_message="Provider not available",
                    error_code="PROVIDER_NOT_AVAILABLE"
                )
            
            # Track request
            self.model_manager.track_request(request)
            
            # Generate code
            model_response = await provider.generate_code(request)
            
            # Calculate generation time
            generation_time = int((time.time() - start_time) * 1000)
            
            # Track response
            self.model_manager.track_response(model_response, generation_time)
            
            # Convert to generation result
            result = await self._convert_response(
                model_response, model_id, generation_time, context
            )
            
            # Cache result if successful
            if result.success and context.enable_caching:
                await self._cache_result(request, result)
            
            # Release model
            await self.model_manager.release_model(model_id)
            
            return result
        
        except Exception as e:
            generation_time = int((time.time() - start_time) * 1000)
            
            self.logger.error("Generation request failed",
                            request_id=request.request_id,
                            error=str(e),
                            generation_time_ms=generation_time)
            
            return GenerationResult(
                request_id=request.request_id,
                success=False,
                error_message=str(e),
                error_code="GENERATION_FAILED",
                generation_time_ms=generation_time
            )
    
    async def process_stream_request(self, 
                                   request: ModelRequest, 
                                   context: GenerationContext) -> AsyncIterator[Dict[str, Any]]:
        """Process a streaming code generation request"""
        try:
            # Select model
            model_id = await self._select_model(request, context)
            if not model_id:
                yield {
                    "type": "error",
                    "error": "No suitable model available",
                    "error_code": "NO_MODEL_AVAILABLE"
                }
                return
            
            # Get provider
            provider = await self._get_provider(model_id)
            if not provider:
                yield {
                    "type": "error",
                    "error": "Provider not available",
                    "error_code": "PROVIDER_NOT_AVAILABLE"
                }
                return
            
            # Track request
            self.model_manager.track_request(request)
            
            # Stream generation
            async for chunk in provider.generate_code_stream(request):
                yield chunk
            
            # Release model
            await self.model_manager.release_model(model_id)
        
        except Exception as e:
            self.logger.error("Streaming generation failed",
                            request_id=request.request_id,
                            error=str(e))
            
            yield {
                "type": "error",
                "error": str(e),
                "error_code": "STREAMING_FAILED"
            }
    
    async def _select_model(self, request: ModelRequest, context: GenerationContext) -> Optional[str]:
        """Select the best model for the request"""
        # Determine required capabilities
        required_capabilities = set()
        
        if request.has_image:
            required_capabilities.add(AIModelCapability.IMAGE_ANALYSIS)
        
        if request.has_text:
            required_capabilities.add(AIModelCapability.TEXT_UNDERSTANDING)
        
        required_capabilities.add(AIModelCapability.CODE_GENERATION)
        
        # Add framework-specific capabilities
        if request.options.responsive_design:
            required_capabilities.add(AIModelCapability.RESPONSIVE_DESIGN)
        
        if request.options.accessibility_features:
            required_capabilities.add(AIModelCapability.ACCESSIBILITY_FEATURES)
        
        # Try preferred providers first
        for provider in context.preferred_providers:
            model_id = await self.model_manager.get_model_for_request(
                required_capabilities=required_capabilities,
                preferred_provider=provider,
                user_id=request.user_id
            )
            if model_id:
                return model_id
        
        # Try any available provider
        model_id = await self.model_manager.get_model_for_request(
            required_capabilities=required_capabilities,
            user_id=request.user_id
        )
        
        if model_id:
            return model_id
        
        # Try fallback providers
        for provider in context.fallback_providers:
            model_id = await self.model_manager.get_model_for_request(
                required_capabilities=required_capabilities,
                preferred_provider=provider,
                user_id=request.user_id
            )
            if model_id:
                return model_id
        
        return None
    
    async def _get_provider(self, model_id: str) -> Optional[BaseModelProvider]:
        """Get provider instance for model"""
        # This would be implemented to return the actual provider
        # For now, we'll simulate provider lookup
        model_config = self.model_manager.registry.get_model(model_id)
        if not model_config:
            return None
        
        # Create provider if not cached
        if model_id not in self._providers:
            provider_class = self._get_provider_class(model_config.provider)
            if provider_class:
                provider = provider_class(model_config, self.logger)
                await provider.initialize()
                self._providers[model_id] = provider
        
        return self._providers.get(model_id)
    
    def _get_provider_class(self, provider: ModelProvider) -> Optional[type]:
        """Get provider class for provider type"""
        provider_map = {
            ModelProvider.OPENAI: OpenAIProvider,
            ModelProvider.ANTHROPIC: AnthropicProvider,
            ModelProvider.GOOGLE: GoogleProvider,
            ModelProvider.AZURE: AzureProvider,
            ModelProvider.HUGGINGFACE: HuggingFaceProvider,
            ModelProvider.LOCAL: LocalModelProvider
        }
        
        return provider_map.get(provider)
    
    async def _convert_response(self, 
                              model_response: ModelResponse,
                              model_id: str,
                              generation_time: int,
                              context: GenerationContext) -> GenerationResult:
        """Convert model response to generation result"""
        model_config = self.model_manager.registry.get_model(model_id)
        provider_name = model_config.provider.value if model_config else "unknown"
        
        result = GenerationResult(
            request_id=model_response.request_id,
            success=model_response.success,
            html_code=model_response.generated_html,
            css_code=model_response.generated_css,
            js_code=model_response.generated_js,
            raw_code=model_response.generated_code,
            model_used=model_id,
            provider_used=provider_name,
            generation_time_ms=generation_time,
            quality_score=model_response.quality_score,
            confidence_score=model_response.metrics.confidence_score,
            detected_elements=model_response.detected_elements,
            detected_patterns=model_response.detected_patterns,
            suggested_improvements=model_response.suggested_improvements,
            error_message=model_response.error_message,
            error_code=model_response.error_code,
            estimated_cost=model_response.metrics.estimated_cost,
            token_usage={
                "input_tokens": model_response.metrics.input_tokens,
                "output_tokens": model_response.metrics.output_tokens,
                "total_tokens": model_response.metrics.total_tokens
            }
        )
        
        # Check validation requirements
        if context.require_validation:
            result.validation_passed = (
                result.quality_score >= context.min_quality_score and
                result.success and
                (result.html_code or result.css_code or result.js_code or result.raw_code)
            )
        else:
            result.validation_passed = result.success
        
        return result
    
    async def _check_cache(self, request: ModelRequest) -> Optional[GenerationResult]:
        """Check if request result is cached"""
        cache_key = self._generate_cache_key(request)
        
        if cache_key in self._request_cache:
            cached_result = self._request_cache[cache_key]
            
            # Check if cache is still valid
            cache_age = (datetime.now(timezone.utc) - cached_result.created_at).total_seconds()
            if cache_age < self._cache_ttl:
                # Update request ID for new request
                cached_result.request_id = request.request_id
                return cached_result
            else:
                # Remove expired cache entry
                del self._request_cache[cache_key]
        
        return None
    
    async def _cache_result(self, request: ModelRequest, result: GenerationResult):
        """Cache generation result"""
        cache_key = self._generate_cache_key(request)
        self._request_cache[cache_key] = result
        
        # Clean up old cache entries periodically
        if len(self._request_cache) > 1000:  # Max cache size
            await self._cleanup_cache()
    
    def _generate_cache_key(self, request: ModelRequest) -> str:
        """Generate cache key for request"""
        # Create key based on request content and options
        key_parts = [
            request.text_prompt or "",
            request.image_data or "",
            request.options.framework.value,
            request.options.quality.value,
            str(request.options.include_comments),
            str(request.options.responsive_design),
            str(request.options.accessibility_features)
        ]
        
        # Simple hash of concatenated parts
        import hashlib
        combined = "|".join(key_parts)
        return hashlib.md5(combined.encode()).hexdigest()
    
    async def _cleanup_cache(self):
        """Clean up expired cache entries"""
        now = datetime.now(timezone.utc)
        expired_keys = []
        
        for key, result in self._request_cache.items():
            cache_age = (now - result.created_at).total_seconds()
            if cache_age >= self._cache_ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._request_cache[key]
        
        self.logger.debug("Cache cleanup completed",
                        expired_entries=len(expired_keys),
                        remaining_entries=len(self._request_cache))


class CodeGenerationService:
    """Main service for AI-powered code generation"""
    
    def __init__(self, 
                 model_manager: Optional[AIModelManager] = None,
                 logger: Optional[StructuredLogger] = None):
        self.logger = logger or StructuredLogger()
        self.model_manager = model_manager or AIModelManager(self.logger)
        self.pipeline = GenerationPipeline(self.model_manager, self.logger)
        
        # Service configuration
        self.default_context = GenerationContext(
            user_id="default",
            preferred_providers=[ModelProvider.OPENAI, ModelProvider.ANTHROPIC],
            fallback_providers=[ModelProvider.GOOGLE, ModelProvider.LOCAL]
        )
        
        self._started = False
    
    async def start(self):
        """Start the generation service"""
        if self._started:
            return
        
        await self.model_manager.start()
        await self.pipeline.initialize_providers()
        
        self._started = True
        self.logger.info("Code generation service started")
    
    async def stop(self):
        """Stop the generation service"""
        if not self._started:
            return
        
        await self.model_manager.stop()
        
        self._started = False
        self.logger.info("Code generation service stopped")
    
    async def generate_from_image(self,
                                image_data: str,
                                user_id: str,
                                options: Optional[GenerationOptions] = None,
                                context: Optional[GenerationContext] = None) -> GenerationResult:
        """Generate code from image"""
        # Validate image data
        if not validate_image_data(image_data):
            return GenerationResult(
                request_id=create_request_id(),
                success=False,
                error_message="Invalid image data",
                error_code="INVALID_IMAGE"
            )
        
        # Create request
        request = ModelRequest(
            request_id=create_request_id(),
            model_id="",  # Will be selected by pipeline
            user_id=user_id,
            image_data=image_data,
            options=options or GenerationOptions()
        )
        
        # Use provided context or default
        generation_context = context or GenerationContext(user_id=user_id)
        
        return await self.pipeline.process_request(request, generation_context)
    
    async def generate_from_text(self,
                               text_prompt: str,
                               user_id: str,
                               options: Optional[GenerationOptions] = None,
                               context: Optional[GenerationContext] = None) -> GenerationResult:
        """Generate code from text description"""
        if not text_prompt or not text_prompt.strip():
            return GenerationResult(
                request_id=create_request_id(),
                success=False,
                error_message="Text prompt is required",
                error_code="EMPTY_PROMPT"
            )
        
        # Create request
        request = ModelRequest(
            request_id=create_request_id(),
            model_id="",  # Will be selected by pipeline
            user_id=user_id,
            text_prompt=text_prompt,
            options=options or GenerationOptions()
        )
        
        # Use provided context or default
        generation_context = context or GenerationContext(user_id=user_id)
        
        return await self.pipeline.process_request(request, generation_context)
    
    async def generate_from_multimodal(self,
                                     image_data: str,
                                     text_prompt: str,
                                     user_id: str,
                                     options: Optional[GenerationOptions] = None,
                                     context: Optional[GenerationContext] = None) -> GenerationResult:
        """Generate code from both image and text"""
        # Validate inputs
        if not validate_image_data(image_data):
            return GenerationResult(
                request_id=create_request_id(),
                success=False,
                error_message="Invalid image data",
                error_code="INVALID_IMAGE"
            )
        
        if not text_prompt or not text_prompt.strip():
            return GenerationResult(
                request_id=create_request_id(),
                success=False,
                error_message="Text prompt is required",
                error_code="EMPTY_PROMPT"
            )
        
        # Create request
        request = ModelRequest(
            request_id=create_request_id(),
            model_id="",  # Will be selected by pipeline
            user_id=user_id,
            image_data=image_data,
            text_prompt=text_prompt,
            options=options or GenerationOptions()
        )
        
        # Use provided context or default
        generation_context = context or GenerationContext(user_id=user_id)
        
        return await self.pipeline.process_request(request, generation_context)
    
    async def generate_stream(self,
                            image_data: Optional[str] = None,
                            text_prompt: Optional[str] = None,
                            user_id: str = "default",
                            options: Optional[GenerationOptions] = None,
                            context: Optional[GenerationContext] = None) -> AsyncIterator[Dict[str, Any]]:
        """Generate code with streaming response"""
        # Validate inputs
        if not image_data and not text_prompt:
            yield {
                "type": "error",
                "error": "Either image or text input is required",
                "error_code": "NO_INPUT"
            }
            return
        
        if image_data and not validate_image_data(image_data):
            yield {
                "type": "error",
                "error": "Invalid image data",
                "error_code": "INVALID_IMAGE"
            }
            return
        
        # Create request
        request = ModelRequest(
            request_id=create_request_id(),
            model_id="",  # Will be selected by pipeline
            user_id=user_id,
            image_data=image_data,
            text_prompt=text_prompt,
            options=options or GenerationOptions()
        )
        
        # Use provided context or default
        generation_context = context or GenerationContext(user_id=user_id)
        
        async for chunk in self.pipeline.process_stream_request(request, generation_context):
            yield chunk
    
    async def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models"""
        return self.model_manager.list_models(available_only=True)
    
    async def get_model_metrics(self, model_id: Optional[str] = None) -> Dict[str, Any]:
        """Get model performance metrics"""
        if model_id:
            metrics = self.model_manager.get_model_metrics(model_id)
            return {model_id: metrics.__dict__ if metrics else None}
        else:
            all_metrics = self.model_manager.get_all_metrics()
            return {
                model_id: metrics.__dict__
                for model_id, metrics in all_metrics.items()
            }
    
    async def validate_generation_options(self, options: GenerationOptions) -> List[str]:
        """Validate generation options"""
        errors = []
        
        # Check framework compatibility
        if options.use_typescript and options.framework not in [
            GenerationFramework.REACT, GenerationFramework.VUE, GenerationFramework.ANGULAR
        ]:
            errors.append("TypeScript is only supported with React, Vue, and Angular")
        
        if options.use_scss and options.framework == GenerationFramework.HTML:
            errors.append("SCSS requires a framework that supports it")
        
        # Check optimization level
        if not (0 <= options.optimization_level <= 3):
            errors.append("Optimization level must be between 0 and 3")
        
        return errors
    
    async def get_service_health(self) -> Dict[str, Any]:
        """Get service health information"""
        models = await self.get_available_models()
        
        return {
            "service": "code_generation",
            "status": "healthy" if self._started else "stopped",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "models": {
                "total": len(self.model_manager.registry._models),
                "available": len(models),
                "providers": list(set(model["provider"] for model in models))
            },
            "cache": {
                "entries": len(self.pipeline._request_cache),
                "ttl_seconds": self.pipeline._cache_ttl
            }
        }