"""
Base Model Provider
Abstract base class for AI model providers
"""
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, AsyncIterator
from datetime import datetime, timezone
import time

from ..model_types import (
    ModelConfiguration, ModelRequest, ModelResponse,
    GenerationMetrics, AIModelException
)

try:
    from shared.monitoring.structured_logger import StructuredLogger
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger


class ProviderError(AIModelException):
    """Base exception for provider-specific errors"""
    pass


class BaseModelProvider(ABC):
    """Abstract base class for AI model providers"""
    
    def __init__(self, config: ModelConfiguration, logger: StructuredLogger):
        self.config = config
        self.logger = logger
        self._session = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize the provider"""
        if self._initialized:
            return
        
        try:
            await self._initialize_provider()
            self._initialized = True
            self.logger.info("Provider initialized", 
                           provider=self.config.provider.value,
                           model_id=self.config.model_id)
        except Exception as e:
            self.logger.error("Provider initialization failed",
                            provider=self.config.provider.value,
                            model_id=self.config.model_id,
                            error=str(e))
            raise ProviderError(f"Failed to initialize provider: {str(e)}", 
                              model_id=self.config.model_id)
    
    async def cleanup(self):
        """Cleanup provider resources"""
        if not self._initialized:
            return
        
        try:
            await self._cleanup_provider()
            self._initialized = False
            self.logger.info("Provider cleaned up", 
                           provider=self.config.provider.value,
                           model_id=self.config.model_id)
        except Exception as e:
            self.logger.warning("Provider cleanup error",
                              provider=self.config.provider.value,
                              model_id=self.config.model_id,
                              error=str(e))
    
    async def generate_code(self, request: ModelRequest) -> ModelResponse:
        """Generate code from request"""
        if not self._initialized:
            await self.initialize()
        
        start_time = time.time()
        
        try:
            # Validate request
            self._validate_request(request)
            
            # Pre-process request
            processed_request = await self._preprocess_request(request)
            preprocess_time = time.time()
            
            # Make model inference
            raw_response = await self._make_inference(processed_request)
            inference_time = time.time()
            
            # Post-process response
            response = await self._postprocess_response(raw_response, request)
            postprocess_time = time.time()
            
            # Calculate metrics
            total_time = (postprocess_time - start_time) * 1000  # Convert to ms
            response.metrics = GenerationMetrics(
                total_duration_ms=int(total_time),
                preprocessing_ms=int((preprocess_time - start_time) * 1000),
                model_inference_ms=int((inference_time - preprocess_time) * 1000),
                postprocessing_ms=int((postprocess_time - inference_time) * 1000)
            )
            
            # Calculate costs
            response.metrics.estimated_cost = self._calculate_cost(
                response.metrics.input_tokens,
                response.metrics.output_tokens
            )
            
            self.logger.info("Code generation completed",
                           model_id=self.config.model_id,
                           request_id=request.request_id,
                           duration_ms=response.metrics.total_duration_ms,
                           success=response.success)
            
            return response
        
        except Exception as e:
            error_time = (time.time() - start_time) * 1000
            
            self.logger.error("Code generation failed",
                            model_id=self.config.model_id,
                            request_id=request.request_id,
                            error=str(e),
                            duration_ms=int(error_time))
            
            return ModelResponse(
                request_id=request.request_id,
                model_id=self.config.model_id,
                success=False,
                error_message=str(e),
                error_code=self._get_error_code(e),
                metrics=GenerationMetrics(total_duration_ms=int(error_time))
            )
    
    async def generate_code_stream(self, request: ModelRequest) -> AsyncIterator[Dict[str, Any]]:
        """Generate code with streaming response"""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Validate request
            self._validate_request(request)
            
            # Pre-process request
            processed_request = await self._preprocess_request(request)
            
            # Stream inference
            async for chunk in self._stream_inference(processed_request):
                yield chunk
        
        except Exception as e:
            self.logger.error("Streaming generation failed",
                            model_id=self.config.model_id,
                            request_id=request.request_id,
                            error=str(e))
            
            yield {
                "error": True,
                "error_message": str(e),
                "error_code": self._get_error_code(e)
            }
    
    async def validate_model(self) -> bool:
        """Validate that the model is working correctly"""
        try:
            if not self._initialized:
                await self.initialize()
            
            # Create a simple test request
            test_request = ModelRequest(
                request_id="health_check",
                model_id=self.config.model_id,
                user_id="system",
                text_prompt="Generate a simple HTML button"
            )
            
            response = await self.generate_code(test_request)
            
            # Check if response is successful and has content
            return response.success and response.has_code
        
        except Exception as e:
            self.logger.error("Model validation failed",
                            model_id=self.config.model_id,
                            error=str(e))
            return False
    
    def _validate_request(self, request: ModelRequest):
        """Validate request before processing"""
        if not request.request_id:
            raise ProviderError("Request ID is required", model_id=self.config.model_id)
        
        if not request.has_image and not request.has_text:
            raise ProviderError("Either image or text input is required", 
                              model_id=self.config.model_id)
        
        # Provider-specific validation
        self._validate_provider_request(request)
    
    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost for token usage"""
        # This would be provider-specific in real implementation
        # Using simple estimation for now
        
        input_cost_per_token = 0.0001  # $0.0001 per input token
        output_cost_per_token = 0.0002  # $0.0002 per output token
        
        # Adjust by provider
        if self.config.provider.value == "openai":
            if "gpt-4" in self.config.model_name.lower():
                input_cost_per_token = 0.0003
                output_cost_per_token = 0.0006
        elif self.config.provider.value == "anthropic":
            input_cost_per_token = 0.0008
            output_cost_per_token = 0.0024
        
        return (input_tokens * input_cost_per_token) + (output_tokens * output_cost_per_token)
    
    def _get_error_code(self, error: Exception) -> str:
        """Get error code from exception"""
        if isinstance(error, ProviderError):
            return error.error_code or "PROVIDER_ERROR"
        elif "rate limit" in str(error).lower():
            return "RATE_LIMIT_EXCEEDED"
        elif "auth" in str(error).lower():
            return "AUTHENTICATION_ERROR"
        elif "timeout" in str(error).lower():
            return "TIMEOUT_ERROR"
        else:
            return "UNKNOWN_ERROR"
    
    # Abstract methods that must be implemented by providers
    
    @abstractmethod
    async def _initialize_provider(self):
        """Provider-specific initialization"""
        pass
    
    @abstractmethod
    async def _cleanup_provider(self):
        """Provider-specific cleanup"""
        pass
    
    @abstractmethod
    async def _preprocess_request(self, request: ModelRequest) -> Dict[str, Any]:
        """Preprocess request for the specific provider"""
        pass
    
    @abstractmethod
    async def _make_inference(self, processed_request: Dict[str, Any]) -> Dict[str, Any]:
        """Make inference call to the model"""
        pass
    
    @abstractmethod
    async def _postprocess_response(self, raw_response: Dict[str, Any], 
                                   original_request: ModelRequest) -> ModelResponse:
        """Postprocess the raw model response"""
        pass
    
    @abstractmethod
    async def _stream_inference(self, processed_request: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        """Stream inference call to the model"""
        pass
    
    @abstractmethod
    def _validate_provider_request(self, request: ModelRequest):
        """Provider-specific request validation"""
        pass
    
    # Utility methods for providers
    
    def _build_system_prompt(self, request: ModelRequest) -> str:
        """Build system prompt based on request options"""
        framework = request.options.framework.value
        quality = request.options.quality.value
        
        prompt_parts = [
            f"You are an expert {framework.upper()} developer.",
            f"Generate {quality} quality code from the provided input.",
        ]
        
        if request.options.include_comments:
            prompt_parts.append("Include helpful comments in the code.")
        
        if request.options.responsive_design:
            prompt_parts.append("Make the design responsive for mobile and desktop.")
        
        if request.options.accessibility_features:
            prompt_parts.append("Include accessibility features (WCAG compliance).")
        
        if request.options.use_typescript and framework in ["react", "vue", "angular"]:
            prompt_parts.append("Use TypeScript instead of JavaScript.")
        
        if request.options.use_scss:
            prompt_parts.append("Use SCSS for styling.")
        
        return " ".join(prompt_parts)
    
    def _build_user_prompt(self, request: ModelRequest) -> str:
        """Build user prompt from request"""
        prompt_parts = []
        
        if request.has_image:
            prompt_parts.append("Based on the provided screenshot/image:")
        
        if request.has_text:
            prompt_parts.append(f"Additional requirements: {request.text_prompt}")
        
        prompt_parts.append(f"Generate {request.options.framework.value.upper()} code.")
        
        if request.options.custom_classes:
            prompt_parts.append(f"Use these CSS classes: {', '.join(request.options.custom_classes)}")
        
        if request.options.excluded_elements:
            prompt_parts.append(f"Exclude these elements: {', '.join(request.options.excluded_elements)}")
        
        return " ".join(prompt_parts)
    
    def _extract_code_blocks(self, text: str) -> Dict[str, str]:
        """Extract code blocks from response text"""
        import re
        
        code_blocks = {}
        
        # Pattern to match code blocks with language specification
        pattern = r'```(\w+)?\n(.*?)\n```'
        matches = re.findall(pattern, text, re.DOTALL)
        
        for lang, code in matches:
            lang = lang.lower() if lang else 'code'
            
            # Map language to standard names
            if lang in ['html', 'htm']:
                code_blocks['html'] = code.strip()
            elif lang in ['css', 'scss', 'sass']:
                code_blocks['css'] = code.strip()
            elif lang in ['javascript', 'js', 'jsx', 'typescript', 'ts', 'tsx']:
                code_blocks['js'] = code.strip()
            else:
                code_blocks['code'] = code.strip()
        
        # If no code blocks found, try to extract without markers
        if not code_blocks:
            # Look for HTML-like content
            html_pattern = r'(<[^>]+>.*?</[^>]+>|<[^>]+/>)'
            html_matches = re.findall(html_pattern, text, re.DOTALL)
            if html_matches:
                code_blocks['html'] = '\n'.join(html_matches)
        
        return code_blocks
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text"""
        # Simple estimation: ~4 characters per token
        return max(1, len(text) // 4)
    
    def _calculate_quality_score(self, response_data: Dict[str, Any], 
                                request: ModelRequest) -> float:
        """Calculate quality score for generated code"""
        score = 0.0
        max_score = 1.0
        
        # Check if code was generated
        if response_data.get('generated_code') or any(
            key in response_data for key in ['generated_html', 'generated_css', 'generated_js']
        ):
            score += 0.4
        
        # Check code quality indicators
        code_text = str(response_data)
        
        # Check for comments if requested
        if request.options.include_comments:
            if '<!--' in code_text or '//' in code_text or '/*' in code_text:
                score += 0.1
        
        # Check for responsive design indicators
        if request.options.responsive_design:
            responsive_keywords = ['@media', 'responsive', 'mobile', 'tablet', 'desktop']
            if any(keyword in code_text.lower() for keyword in responsive_keywords):
                score += 0.1
        
        # Check for accessibility features
        if request.options.accessibility_features:
            accessibility_keywords = ['alt=', 'aria-', 'role=', 'tabindex']
            if any(keyword in code_text.lower() for keyword in accessibility_keywords):
                score += 0.1
        
        # Check for proper structure
        if '<html' in code_text or '<!DOCTYPE' in code_text:
            score += 0.1
        
        # Check for CSS styling
        if 'style' in code_text or '.css' in code_text or '{' in code_text:
            score += 0.1
        
        # Normalize score
        return min(score / max_score, 1.0) if max_score > 0 else 0.0