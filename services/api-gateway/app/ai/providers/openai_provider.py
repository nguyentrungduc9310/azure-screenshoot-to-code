"""
OpenAI Provider
Implementation for OpenAI models (GPT-4V, GPT-4, etc.)
"""
import asyncio
import json
from typing import Dict, List, Optional, Any, AsyncIterator
import base64

from .base_provider import BaseModelProvider, ProviderError
from ..model_types import ModelRequest, ModelResponse, GenerationMetrics

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp = None


class OpenAIProvider(BaseModelProvider):
    """OpenAI model provider implementation"""
    
    async def _initialize_provider(self):
        """Initialize OpenAI client"""
        if not OPENAI_AVAILABLE:
            raise ProviderError("OpenAI library not available. Install with: pip install openai",
                              model_id=self.config.model_id)
        
        if not self.config.api_key:
            raise ProviderError("OpenAI API key not configured",
                              model_id=self.config.model_id)
        
        # Initialize OpenAI client
        self.client = openai.AsyncOpenAI(
            api_key=self.config.api_key,
            timeout=self.config.timeout_seconds
        )
        
        # Test connection
        try:
            await self.client.models.list()
        except Exception as e:
            raise ProviderError(f"Failed to connect to OpenAI API: {str(e)}",
                              model_id=self.config.model_id)
    
    async def _cleanup_provider(self):
        """Cleanup OpenAI client"""
        if hasattr(self, 'client'):
            await self.client.close()
    
    def _validate_provider_request(self, request: ModelRequest):
        """Validate OpenAI-specific request parameters"""
        # Check model capabilities
        if request.has_image and "gpt-4" not in self.config.model_name.lower():
            raise ProviderError("Image input requires GPT-4V model",
                              model_id=self.config.model_id)
        
        # Check token limits
        estimated_tokens = 0
        if request.has_text:
            estimated_tokens += self._estimate_tokens(request.text_prompt)
        
        if request.has_image:
            estimated_tokens += 1000  # Rough estimate for image tokens
        
        if estimated_tokens > self.config.max_tokens:
            raise ProviderError(f"Request exceeds token limit: {estimated_tokens} > {self.config.max_tokens}",
                              model_id=self.config.model_id)
    
    async def _preprocess_request(self, request: ModelRequest) -> Dict[str, Any]:
        """Preprocess request for OpenAI API"""
        messages = []
        
        # Add system message
        system_prompt = self._build_system_prompt(request)
        messages.append({
            "role": "system",
            "content": system_prompt
        })
        
        # Build user message
        user_content = []
        
        # Add text content
        if request.has_text:
            user_prompt = self._build_user_prompt(request)
            user_content.append({
                "type": "text",
                "text": user_prompt
            })
        
        # Add image content
        if request.has_image:
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{request.image_data}",
                    "detail": "high"
                }
            })
        
        messages.append({
            "role": "user",
            "content": user_content if len(user_content) > 1 else user_content[0]["text"]
        })
        
        # Build API parameters
        api_params = {
            "model": self.config.model_name or "gpt-4-vision-preview",
            "messages": messages,
            "max_tokens": min(self.config.max_tokens, 4000),
            "temperature": self.config.temperature,
            "top_p": self.config.top_p
        }
        
        # Add custom parameters
        if self.config.custom_parameters:
            api_params.update(self.config.custom_parameters)
        
        return {
            "api_params": api_params,
            "messages": messages
        }
    
    async def _make_inference(self, processed_request: Dict[str, Any]) -> Dict[str, Any]:
        """Make inference call to OpenAI API"""
        try:
            response = await self.client.chat.completions.create(
                **processed_request["api_params"]
            )
            
            return {
                "response": response,
                "raw_content": response.choices[0].message.content,
                "usage": response.usage,
                "model": response.model
            }
        
        except openai.RateLimitError as e:
            raise ProviderError(f"OpenAI rate limit exceeded: {str(e)}",
                              model_id=self.config.model_id,
                              error_code="RATE_LIMIT_EXCEEDED")
        
        except openai.AuthenticationError as e:
            raise ProviderError(f"OpenAI authentication failed: {str(e)}",
                              model_id=self.config.model_id,
                              error_code="AUTHENTICATION_ERROR")
        
        except openai.APIError as e:
            raise ProviderError(f"OpenAI API error: {str(e)}",
                              model_id=self.config.model_id,
                              error_code="API_ERROR")
        
        except Exception as e:
            raise ProviderError(f"OpenAI request failed: {str(e)}",
                              model_id=self.config.model_id,
                              error_code="REQUEST_FAILED")
    
    async def _postprocess_response(self, raw_response: Dict[str, Any], 
                                   original_request: ModelRequest) -> ModelResponse:
        """Postprocess OpenAI response"""
        content = raw_response["raw_content"]
        usage = raw_response.get("usage")
        
        # Extract code blocks
        code_blocks = self._extract_code_blocks(content)
        
        # Create response
        response = ModelResponse(
            request_id=original_request.request_id,
            model_id=self.config.model_id,
            success=True
        )
        
        # Set generated code
        if "html" in code_blocks:
            response.generated_html = code_blocks["html"]
        if "css" in code_blocks:
            response.generated_css = code_blocks["css"]
        if "js" in code_blocks:
            response.generated_js = code_blocks["js"]
        if "code" in code_blocks and not response.has_code:
            response.generated_code = code_blocks["code"]
        
        # If no structured code found, use raw content
        if not response.has_code and content:
            response.generated_code = content
        
        # Set metrics
        if usage:
            response.metrics.input_tokens = usage.prompt_tokens
            response.metrics.output_tokens = usage.completion_tokens
            response.metrics.total_tokens = usage.total_tokens
        else:
            # Estimate tokens if usage not provided
            response.metrics.input_tokens = self._estimate_tokens(
                str(original_request.text_prompt or "")
            )
            response.metrics.output_tokens = self._estimate_tokens(content)
            response.metrics.total_tokens = response.metrics.input_tokens + response.metrics.output_tokens
        
        # Calculate quality score
        response.quality_score = self._calculate_quality_score(
            response.__dict__, original_request
        )
        
        # Set confidence score (OpenAI doesn't provide this, so we estimate)
        response.metrics.confidence_score = min(response.quality_score + 0.2, 1.0)
        
        # Analyze generated content
        response.detected_elements = self._analyze_elements(content)
        response.detected_patterns = self._analyze_patterns(content)
        response.suggested_improvements = self._generate_suggestions(content, original_request)
        
        return response
    
    async def _stream_inference(self, processed_request: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        """Stream inference call to OpenAI API"""
        try:
            # Add streaming parameter
            api_params = processed_request["api_params"].copy()
            api_params["stream"] = True
            
            stream = await self.client.chat.completions.create(**api_params)
            
            accumulated_content = ""
            
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta:
                    delta = chunk.choices[0].delta
                    
                    if delta.content:
                        accumulated_content += delta.content
                        
                        yield {
                            "type": "content",
                            "content": delta.content,
                            "accumulated": accumulated_content
                        }
                    
                    if chunk.choices[0].finish_reason:
                        # Extract final code blocks
                        code_blocks = self._extract_code_blocks(accumulated_content)
                        
                        yield {
                            "type": "complete",
                            "content": accumulated_content,
                            "code_blocks": code_blocks,
                            "finish_reason": chunk.choices[0].finish_reason
                        }
        
        except Exception as e:
            yield {
                "type": "error",
                "error": str(e),
                "error_code": self._get_error_code(e)
            }
    
    def _analyze_elements(self, content: str) -> List[Dict[str, Any]]:
        """Analyze HTML elements in generated code"""
        import re
        
        elements = []
        
        # Find HTML tags
        tag_pattern = r'<(\w+)([^>]*)>'
        matches = re.finditer(tag_pattern, content, re.IGNORECASE)
        
        for match in matches:
            tag_name = match.group(1).lower()
            attributes = match.group(2)
            
            element = {
                "tag": tag_name,
                "attributes": {},
                "position": match.start()
            }
            
            # Parse attributes
            attr_pattern = r'(\w+)=(["\'])([^"\']*)\2'
            attr_matches = re.finditer(attr_pattern, attributes)
            
            for attr_match in attr_matches:
                attr_name = attr_match.group(1)
                attr_value = attr_match.group(3)
                element["attributes"][attr_name] = attr_value
            
            elements.append(element)
        
        return elements
    
    def _analyze_patterns(self, content: str) -> List[str]:
        """Analyze design patterns in generated code"""
        patterns = []
        
        content_lower = content.lower()
        
        # CSS Framework patterns
        if "bootstrap" in content_lower or "btn-" in content_lower:
            patterns.append("Bootstrap Framework")
        
        if "tailwind" in content_lower or "w-" in content_lower or "h-" in content_lower:
            patterns.append("Tailwind CSS")
        
        # Layout patterns
        if "display: flex" in content_lower or "d-flex" in content_lower:
            patterns.append("Flexbox Layout")
        
        if "display: grid" in content_lower or "grid-" in content_lower:
            patterns.append("CSS Grid Layout")
        
        # Component patterns
        if "class=" in content_lower and ("card" in content_lower or "modal" in content_lower):
            patterns.append("Component-based Structure")
        
        # Responsive patterns
        if "@media" in content_lower:
            patterns.append("Responsive Design")
        
        # Accessibility patterns
        if "aria-" in content_lower or "role=" in content_lower:
            patterns.append("Accessibility Features")
        
        return patterns
    
    def _generate_suggestions(self, content: str, request: ModelRequest) -> List[str]:
        """Generate improvement suggestions"""
        suggestions = []
        
        content_lower = content.lower()
        
        # Check for missing DOCTYPE
        if "<html" in content_lower and "<!doctype" not in content_lower:
            suggestions.append("Add DOCTYPE declaration for HTML5")
        
        # Check for missing viewport meta tag
        if "<html" in content_lower and "viewport" not in content_lower:
            suggestions.append("Add viewport meta tag for mobile responsiveness")
        
        # Check for missing alt attributes on images
        if "<img" in content_lower and "alt=" not in content_lower:
            suggestions.append("Add alt attributes to images for accessibility")
        
        # Check for inline styles
        if "style=" in content_lower:
            suggestions.append("Consider moving inline styles to external CSS file")
        
        # Check for accessibility improvements
        if request.options.accessibility_features and "aria-" not in content_lower:
            suggestions.append("Add ARIA attributes for better accessibility")
        
        # Check for semantic HTML
        if "<div" in content_lower and all(tag not in content_lower for tag in ["<header", "<main", "<section", "<article"]):
            suggestions.append("Consider using semantic HTML elements (header, main, section, article)")
        
        return suggestions