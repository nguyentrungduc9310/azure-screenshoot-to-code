"""
Anthropic Provider
Implementation for Anthropic Claude models
"""
import asyncio
import json
from typing import Dict, List, Optional, Any, AsyncIterator
import base64

from .base_provider import BaseModelProvider, ProviderError
from ..model_types import ModelRequest, ModelResponse, GenerationMetrics

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    anthropic = None


class AnthropicProvider(BaseModelProvider):
    """Anthropic Claude model provider implementation"""
    
    async def _initialize_provider(self):
        """Initialize Anthropic client"""
        if not ANTHROPIC_AVAILABLE:
            raise ProviderError("Anthropic library not available. Install with: pip install anthropic",
                              model_id=self.config.model_id)
        
        if not self.config.api_key:
            raise ProviderError("Anthropic API key not configured",
                              model_id=self.config.model_id)
        
        # Initialize Anthropic client
        self.client = anthropic.AsyncAnthropic(
            api_key=self.config.api_key,
            timeout=self.config.timeout_seconds
        )
        
        # Test connection by making a simple request
        try:
            await self.client.messages.create(
                model=self.config.model_name or "claude-3-sonnet-20240229",
                max_tokens=10,
                messages=[{"role": "user", "content": "Hello"}]
            )
        except Exception as e:
            raise ProviderError(f"Failed to connect to Anthropic API: {str(e)}",
                              model_id=self.config.model_id)
    
    async def _cleanup_provider(self):
        """Cleanup Anthropic client"""
        if hasattr(self, 'client'):
            await self.client.aclose()
    
    def _validate_provider_request(self, request: ModelRequest):
        """Validate Anthropic-specific request parameters"""
        # Check model capabilities
        model_name = self.config.model_name or "claude-3-sonnet-20240229"
        
        if request.has_image and "claude-3" not in model_name.lower():
            raise ProviderError("Image input requires Claude-3 model",
                              model_id=self.config.model_id)
        
        # Check token limits (Claude has different limits than OpenAI)
        estimated_tokens = 0
        if request.has_text:
            estimated_tokens += self._estimate_tokens(request.text_prompt)
        
        if request.has_image:
            estimated_tokens += 1000  # Rough estimate for image tokens
        
        # Claude models have higher token limits
        max_tokens = min(self.config.max_tokens, 100000)  # Claude can handle up to 100k tokens
        
        if estimated_tokens > max_tokens:
            raise ProviderError(f"Request exceeds token limit: {estimated_tokens} > {max_tokens}",
                              model_id=self.config.model_id)
    
    async def _preprocess_request(self, request: ModelRequest) -> Dict[str, Any]:
        """Preprocess request for Anthropic API"""
        messages = []
        
        # Build user message content
        content = []
        
        # Add text content
        if request.has_text:
            user_prompt = self._build_user_prompt(request)
            content.append({
                "type": "text",
                "text": user_prompt
            })
        
        # Add image content
        if request.has_image:
            # Determine image format
            image_bytes = request.get_image_bytes()
            if not image_bytes:
                raise ProviderError("Invalid image data", model_id=self.config.model_id)
            
            # Detect image format
            media_type = "image/jpeg"  # Default
            if image_bytes.startswith(b'\x89PNG'):
                media_type = "image/png"
            elif image_bytes.startswith(b'GIF'):
                media_type = "image/gif"
            elif image_bytes.startswith(b'RIFF') and b'WEBP' in image_bytes[:12]:
                media_type = "image/webp"
            
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": request.image_data
                }
            })
        
        messages.append({
            "role": "user",
            "content": content
        })
        
        # Build system prompt
        system_prompt = self._build_system_prompt(request)
        
        # Build API parameters
        api_params = {
            "model": self.config.model_name or "claude-3-sonnet-20240229",
            "max_tokens": min(self.config.max_tokens, 4000),
            "messages": messages,
            "system": system_prompt,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p
        }
        
        # Add custom parameters
        if self.config.custom_parameters:
            api_params.update(self.config.custom_parameters)
        
        return {
            "api_params": api_params,
            "messages": messages,
            "system": system_prompt
        }
    
    async def _make_inference(self, processed_request: Dict[str, Any]) -> Dict[str, Any]:
        """Make inference call to Anthropic API"""
        try:
            response = await self.client.messages.create(
                **processed_request["api_params"]
            )
            
            return {
                "response": response,
                "raw_content": response.content[0].text if response.content else "",
                "usage": response.usage,
                "model": response.model
            }
        
        except anthropic.RateLimitError as e:
            raise ProviderError(f"Anthropic rate limit exceeded: {str(e)}",
                              model_id=self.config.model_id,
                              error_code="RATE_LIMIT_EXCEEDED")
        
        except anthropic.AuthenticationError as e:
            raise ProviderError(f"Anthropic authentication failed: {str(e)}",
                              model_id=self.config.model_id,
                              error_code="AUTHENTICATION_ERROR")
        
        except anthropic.APIError as e:
            raise ProviderError(f"Anthropic API error: {str(e)}",
                              model_id=self.config.model_id,
                              error_code="API_ERROR")
        
        except Exception as e:
            raise ProviderError(f"Anthropic request failed: {str(e)}",
                              model_id=self.config.model_id,
                              error_code="REQUEST_FAILED")
    
    async def _postprocess_response(self, raw_response: Dict[str, Any], 
                                   original_request: ModelRequest) -> ModelResponse:
        """Postprocess Anthropic response"""
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
            response.metrics.input_tokens = usage.input_tokens
            response.metrics.output_tokens = usage.output_tokens
            response.metrics.total_tokens = usage.input_tokens + usage.output_tokens
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
        
        # Set confidence score (Anthropic doesn't provide this, so we estimate)
        response.metrics.confidence_score = min(response.quality_score + 0.1, 1.0)
        
        # Analyze generated content
        response.detected_elements = self._analyze_elements(content)
        response.detected_patterns = self._analyze_patterns(content)
        response.suggested_improvements = self._generate_suggestions(content, original_request)
        
        return response
    
    async def _stream_inference(self, processed_request: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        """Stream inference call to Anthropic API"""
        try:
            # Add streaming parameter
            api_params = processed_request["api_params"].copy()
            api_params["stream"] = True
            
            stream = await self.client.messages.create(**api_params)
            
            accumulated_content = ""
            
            async for event in stream:
                if event.type == "content_block_delta":
                    if hasattr(event.delta, 'text'):
                        delta_text = event.delta.text
                        accumulated_content += delta_text
                        
                        yield {
                            "type": "content",
                            "content": delta_text,
                            "accumulated": accumulated_content
                        }
                
                elif event.type == "message_stop":
                    # Extract final code blocks
                    code_blocks = self._extract_code_blocks(accumulated_content)
                    
                    yield {
                        "type": "complete",
                        "content": accumulated_content,
                        "code_blocks": code_blocks,
                        "finish_reason": "stop"
                    }
        
        except Exception as e:
            yield {
                "type": "error",
                "error": str(e),
                "error_code": self._get_error_code(e)
            }
    
    def _build_system_prompt(self, request: ModelRequest) -> str:
        """Build system prompt optimized for Claude"""
        framework = request.options.framework.value
        quality = request.options.quality.value
        
        prompt_parts = [
            f"You are Claude, an AI assistant created by Anthropic.",
            f"You are an expert {framework.upper()} developer specializing in creating high-quality, accessible web interfaces.",
            f"Generate {quality} quality code from the provided input.",
            "Focus on clean, semantic code that follows best practices."
        ]
        
        if request.options.include_comments:
            prompt_parts.append("Include helpful comments explaining the code structure and functionality.")
        
        if request.options.responsive_design:
            prompt_parts.append("Ensure the design is responsive and works well on mobile, tablet, and desktop devices.")
        
        if request.options.accessibility_features:
            prompt_parts.append("Implement comprehensive accessibility features following WCAG 2.1 AA guidelines.")
        
        if request.options.use_typescript and framework in ["react", "vue", "angular"]:
            prompt_parts.append("Use TypeScript with proper type definitions.")
        
        if request.options.use_scss:
            prompt_parts.append("Use SCSS for styling with variables and mixins where appropriate.")
        
        # Add Claude-specific instructions
        prompt_parts.extend([
            "Structure your response clearly with separate code blocks for HTML, CSS, and JavaScript.",
            "Provide brief explanations for complex implementations.",
            "Suggest improvements or alternatives when relevant."
        ])
        
        return " ".join(prompt_parts)
    
    def _analyze_elements(self, content: str) -> List[Dict[str, Any]]:
        """Analyze HTML elements in generated code"""
        import re
        
        elements = []
        
        # Find HTML tags with more detailed analysis
        tag_pattern = r'<(\w+)([^>]*)>'
        matches = re.finditer(tag_pattern, content, re.IGNORECASE)
        
        for match in matches:
            tag_name = match.group(1).lower()
            attributes = match.group(2)
            
            element = {
                "tag": tag_name,
                "attributes": {},
                "position": match.start(),
                "semantic": self._is_semantic_element(tag_name),
                "interactive": self._is_interactive_element(tag_name)
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
    
    def _is_semantic_element(self, tag: str) -> bool:
        """Check if element is semantic HTML"""
        semantic_tags = {
            'header', 'nav', 'main', 'section', 'article', 'aside', 
            'footer', 'figure', 'figcaption', 'details', 'summary'
        }
        return tag in semantic_tags
    
    def _is_interactive_element(self, tag: str) -> bool:
        """Check if element is interactive"""
        interactive_tags = {
            'button', 'input', 'select', 'textarea', 'a', 'details', 'summary'
        }
        return tag in interactive_tags
    
    def _analyze_patterns(self, content: str) -> List[str]:
        """Analyze design patterns with Claude-specific insights"""
        patterns = []
        
        content_lower = content.lower()
        
        # Framework patterns
        if "bootstrap" in content_lower or "btn-" in content_lower or "col-" in content_lower:
            patterns.append("Bootstrap Framework")
        
        if "tailwind" in content_lower or any(cls in content_lower for cls in ["w-", "h-", "p-", "m-", "text-"]):
            patterns.append("Tailwind CSS")
        
        # Layout patterns
        if "display: flex" in content_lower or "d-flex" in content_lower:
            patterns.append("Flexbox Layout")
        
        if "display: grid" in content_lower or "grid-template" in content_lower:
            patterns.append("CSS Grid Layout")
        
        # Component patterns
        if "class=" in content_lower:
            if "card" in content_lower:
                patterns.append("Card Component Pattern")
            if "modal" in content_lower:
                patterns.append("Modal Component Pattern")
            if "navbar" in content_lower or "navigation" in content_lower:
                patterns.append("Navigation Component Pattern")
        
        # Design patterns
        if "@media" in content_lower:
            patterns.append("Responsive Design")
        
        if "aria-" in content_lower or "role=" in content_lower:
            patterns.append("Accessibility Features")
        
        if "transition" in content_lower or "animation" in content_lower:
            patterns.append("CSS Animations/Transitions")
        
        # Modern CSS patterns
        if "css custom properties" in content_lower or "--" in content_lower:
            patterns.append("CSS Custom Properties")
        
        if "clamp(" in content_lower or "min(" in content_lower or "max(" in content_lower:
            patterns.append("Modern CSS Functions")
        
        return patterns
    
    def _generate_suggestions(self, content: str, request: ModelRequest) -> List[str]:
        """Generate improvement suggestions optimized for Claude's capabilities"""
        suggestions = []
        
        content_lower = content.lower()
        
        # Structure suggestions
        if "<html" in content_lower and "<!doctype" not in content_lower:
            suggestions.append("Add HTML5 DOCTYPE declaration")
        
        if "<html" in content_lower and "lang=" not in content_lower:
            suggestions.append("Add language attribute to html element for accessibility")
        
        # Meta tag suggestions
        if "<head" in content_lower:
            if "viewport" not in content_lower:
                suggestions.append("Add viewport meta tag for mobile optimization")
            if "charset" not in content_lower:
                suggestions.append("Add charset meta tag for character encoding")
            if "description" not in content_lower:
                suggestions.append("Add meta description for SEO")
        
        # Accessibility suggestions
        if "<img" in content_lower and "alt=" not in content_lower:
            suggestions.append("Add alt attributes to all images for screen readers")
        
        if request.options.accessibility_features:
            if "aria-" not in content_lower and ("form" in content_lower or "button" in content_lower):
                suggestions.append("Add ARIA labels for form elements and interactive components")
            
            if "role=" not in content_lower and "navigation" in content_lower:
                suggestions.append("Add role attributes to improve semantic structure")
        
        # Performance suggestions
        if "style=" in content_lower:
            suggestions.append("Extract inline styles to external CSS for better maintainability")
        
        if "<script" in content_lower and "defer" not in content_lower and "async" not in content_lower:
            suggestions.append("Consider adding defer or async attributes to script tags")
        
        # Security suggestions
        if "href=" in content_lower and "target=\"_blank\"" in content_lower:
            suggestions.append("Add rel=\"noopener noreferrer\" to external links for security")
        
        # Modern CSS suggestions
        if "px" in content_lower and request.options.responsive_design:
            suggestions.append("Consider using relative units (rem, em, %) for better scalability")
        
        # Semantic HTML suggestions
        if "<div" in content_lower and not any(tag in content_lower for tag in ["<header", "<main", "<section", "<article", "<nav"]):
            suggestions.append("Replace generic div elements with semantic HTML5 elements")
        
        return suggestions