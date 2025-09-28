"""
Google Provider
Implementation for Google AI models (Gemini, etc.)
"""
import asyncio
import json
from typing import Dict, List, Optional, Any, AsyncIterator
import base64

from .base_provider import BaseModelProvider, ProviderError
from ..model_types import ModelRequest, ModelResponse, GenerationMetrics

try:
    import google.generativeai as genai
    GOOGLE_AI_AVAILABLE = True
except ImportError:
    GOOGLE_AI_AVAILABLE = False
    genai = None


class GoogleProvider(BaseModelProvider):
    """Google AI model provider implementation"""
    
    async def _initialize_provider(self):
        """Initialize Google AI client"""
        if not GOOGLE_AI_AVAILABLE:
            raise ProviderError("Google AI library not available. Install with: pip install google-generativeai",
                              model_id=self.config.model_id)
        
        if not self.config.api_key:
            raise ProviderError("Google AI API key not configured",
                              model_id=self.config.model_id)
        
        # Configure Google AI
        genai.configure(api_key=self.config.api_key)
        
        # Initialize model
        model_name = self.config.model_name or "gemini-pro-vision"
        
        try:
            self.model = genai.GenerativeModel(model_name)
            
            # Test connection
            test_response = await self.model.generate_content_async("Hello")
            if not test_response:
                raise Exception("Empty response from model")
                
        except Exception as e:
            raise ProviderError(f"Failed to initialize Google AI model: {str(e)}",
                              model_id=self.config.model_id)
    
    async def _cleanup_provider(self):
        """Cleanup Google AI resources"""
        # Google AI client doesn't require explicit cleanup
        pass
    
    def _validate_provider_request(self, request: ModelRequest):
        """Validate Google AI-specific request parameters"""
        model_name = self.config.model_name or "gemini-pro-vision"
        
        # Check model capabilities
        if request.has_image and "vision" not in model_name.lower():
            raise ProviderError("Image input requires Gemini Pro Vision model",
                              model_id=self.config.model_id)
        
        # Check token limits
        estimated_tokens = 0
        if request.has_text:
            estimated_tokens += self._estimate_tokens(request.text_prompt)
        
        if request.has_image:
            estimated_tokens += 1000  # Rough estimate for image tokens
        
        # Gemini has different token limits
        max_tokens = min(self.config.max_tokens, 30000)  # Gemini limit
        
        if estimated_tokens > max_tokens:
            raise ProviderError(f"Request exceeds token limit: {estimated_tokens} > {max_tokens}",
                              model_id=self.config.model_id)
    
    async def _preprocess_request(self, request: ModelRequest) -> Dict[str, Any]:
        """Preprocess request for Google AI API"""
        content_parts = []
        
        # Add text content
        if request.has_text:
            system_prompt = self._build_system_prompt(request)
            user_prompt = self._build_user_prompt(request)
            combined_prompt = f"{system_prompt}\n\n{user_prompt}"
            content_parts.append(combined_prompt)
        
        # Add image content
        if request.has_image:
            try:
                # Decode image data
                image_bytes = request.get_image_bytes()
                if not image_bytes:
                    raise ProviderError("Invalid image data", model_id=self.config.model_id)
                
                # Create image part
                import PIL.Image
                import io
                
                image = PIL.Image.open(io.BytesIO(image_bytes))
                content_parts.append(image)
                
            except Exception as e:
                raise ProviderError(f"Failed to process image: {str(e)}",
                                  model_id=self.config.model_id)
        
        # Build generation config
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=min(self.config.max_tokens, 2048),
            temperature=self.config.temperature,
            top_p=self.config.top_p
        )
        
        # Add safety settings
        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            }
        ]
        
        return {
            "content_parts": content_parts,
            "generation_config": generation_config,
            "safety_settings": safety_settings
        }
    
    async def _make_inference(self, processed_request: Dict[str, Any]) -> Dict[str, Any]:
        """Make inference call to Google AI API"""
        try:
            response = await self.model.generate_content_async(
                contents=processed_request["content_parts"],
                generation_config=processed_request["generation_config"],
                safety_settings=processed_request["safety_settings"]
            )
            
            # Check if response was blocked
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                if response.prompt_feedback.block_reason:
                    raise ProviderError(f"Content blocked: {response.prompt_feedback.block_reason}",
                                      model_id=self.config.model_id,
                                      error_code="CONTENT_BLOCKED")
            
            if not response.text:
                raise ProviderError("Empty response from Google AI",
                                  model_id=self.config.model_id,
                                  error_code="EMPTY_RESPONSE")
            
            return {
                "response": response,
                "raw_content": response.text,
                "usage": getattr(response, 'usage_metadata', None),
                "safety_ratings": getattr(response, 'safety_ratings', [])
            }
        
        except Exception as e:
            error_message = str(e)
            
            if "quota" in error_message.lower() or "rate limit" in error_message.lower():
                raise ProviderError(f"Google AI rate limit exceeded: {error_message}",
                                  model_id=self.config.model_id,
                                  error_code="RATE_LIMIT_EXCEEDED")
            
            elif "api key" in error_message.lower() or "authentication" in error_message.lower():
                raise ProviderError(f"Google AI authentication failed: {error_message}",
                                  model_id=self.config.model_id,
                                  error_code="AUTHENTICATION_ERROR")
            
            else:
                raise ProviderError(f"Google AI request failed: {error_message}",
                                  model_id=self.config.model_id,
                                  error_code="REQUEST_FAILED")
    
    async def _postprocess_response(self, raw_response: Dict[str, Any], 
                                   original_request: ModelRequest) -> ModelResponse:
        """Postprocess Google AI response"""
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
            response.metrics.input_tokens = getattr(usage, 'prompt_token_count', 0)
            response.metrics.output_tokens = getattr(usage, 'candidates_token_count', 0)
            response.metrics.total_tokens = getattr(usage, 'total_token_count', 0)
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
        
        # Set confidence score (Google AI doesn't provide this directly)
        response.metrics.confidence_score = min(response.quality_score + 0.15, 1.0)
        
        # Analyze generated content
        response.detected_elements = self._analyze_elements(content)
        response.detected_patterns = self._analyze_patterns(content)
        response.suggested_improvements = self._generate_suggestions(content, original_request)
        
        # Add safety ratings to metadata
        safety_ratings = raw_response.get("safety_ratings", [])
        if safety_ratings:
            response.validation_results["safety_ratings"] = [
                {
                    "category": rating.category.name,
                    "probability": rating.probability.name
                }
                for rating in safety_ratings
            ]
        
        return response
    
    async def _stream_inference(self, processed_request: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        """Stream inference call to Google AI API"""
        try:
            # Google AI streaming (note: may not be available for all models)
            response_stream = await self.model.generate_content_async(
                contents=processed_request["content_parts"],
                generation_config=processed_request["generation_config"],
                safety_settings=processed_request["safety_settings"],
                stream=True
            )
            
            accumulated_content = ""
            
            async for chunk in response_stream:
                if hasattr(chunk, 'text') and chunk.text:
                    accumulated_content += chunk.text
                    
                    yield {
                        "type": "content",
                        "content": chunk.text,
                        "accumulated": accumulated_content
                    }
            
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
        """Build system prompt optimized for Gemini"""
        framework = request.options.framework.value
        quality = request.options.quality.value
        
        prompt_parts = [
            f"You are Gemini, Google's advanced AI assistant.",
            f"You are an expert {framework.upper()} developer with deep knowledge of modern web development.",
            f"Generate {quality} quality, production-ready code from the provided input.",
            "Focus on clean, efficient, and maintainable code that follows current best practices."
        ]
        
        if request.options.include_comments:
            prompt_parts.append("Include clear, helpful comments that explain the code logic and structure.")
        
        if request.options.responsive_design:
            prompt_parts.append("Create responsive designs that work seamlessly across all device sizes.")
        
        if request.options.accessibility_features:
            prompt_parts.append("Implement comprehensive accessibility features following WCAG 2.1 AA standards.")
        
        if request.options.use_typescript and framework in ["react", "vue", "angular"]:
            prompt_parts.append("Use TypeScript with strong typing and interfaces.")
        
        if request.options.use_scss:
            prompt_parts.append("Use SCSS with variables, mixins, and nested selectors for maintainable styles.")
        
        # Add Gemini-specific instructions
        prompt_parts.extend([
            "Organize your response with clear code blocks for HTML, CSS, and JavaScript.",
            "Provide explanations for complex implementations or design decisions.",
            "Include suggestions for further improvements or optimizations when applicable."
        ])
        
        return " ".join(prompt_parts)
    
    def _analyze_elements(self, content: str) -> List[Dict[str, Any]]:
        """Analyze HTML elements with Google AI insights"""
        import re
        
        elements = []
        
        # Find HTML tags with Google-specific analysis
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
                "accessibility_ready": self._has_accessibility_features(attributes),
                "performance_impact": self._assess_performance_impact(tag_name, attributes)
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
            'footer', 'figure', 'figcaption', 'details', 'summary',
            'mark', 'time', 'address'
        }
        return tag in semantic_tags
    
    def _has_accessibility_features(self, attributes: str) -> bool:
        """Check if element has accessibility features"""
        accessibility_attrs = ['aria-', 'role=', 'alt=', 'title=', 'tabindex=']
        return any(attr in attributes.lower() for attr in accessibility_attrs)
    
    def _assess_performance_impact(self, tag: str, attributes: str) -> str:
        """Assess performance impact of element"""
        if tag in ['img', 'video', 'iframe']:
            if 'loading="lazy"' in attributes:
                return "optimized"
            else:
                return "high"
        elif tag in ['script', 'link']:
            if any(attr in attributes for attr in ['defer', 'async', 'preload']):
                return "optimized"
            else:
                return "medium"
        else:
            return "low"
    
    def _analyze_patterns(self, content: str) -> List[str]:
        """Analyze design patterns with Google AI insights"""
        patterns = []
        
        content_lower = content.lower()
        
        # Modern framework patterns
        if "material" in content_lower or "mdc-" in content_lower:
            patterns.append("Material Design Components")
        
        if "bootstrap" in content_lower or "btn-" in content_lower:
            patterns.append("Bootstrap Framework")
        
        if "tailwind" in content_lower or any(cls in content_lower for cls in ["w-", "h-", "p-", "m-", "text-", "bg-"]):
            patterns.append("Tailwind CSS")
        
        # Layout patterns
        if "display: flex" in content_lower or "flexbox" in content_lower:
            patterns.append("Flexbox Layout")
        
        if "display: grid" in content_lower or "grid-template" in content_lower:
            patterns.append("CSS Grid Layout")
        
        if "display: subgrid" in content_lower:
            patterns.append("CSS Subgrid")
        
        # Modern CSS patterns
        if "container queries" in content_lower or "@container" in content_lower:
            patterns.append("Container Queries")
        
        if "css custom properties" in content_lower or "--" in content_lower:
            patterns.append("CSS Custom Properties")
        
        if any(func in content_lower for func in ["clamp(", "min(", "max(", "minmax("]):
            patterns.append("Modern CSS Functions")
        
        # Component patterns
        if "web components" in content_lower or "custom elements" in content_lower:
            patterns.append("Web Components")
        
        # Progressive enhancement patterns
        if "progressive enhancement" in content_lower or "feature detection" in content_lower:
            patterns.append("Progressive Enhancement")
        
        # Performance patterns
        if "lazy loading" in content_lower or 'loading="lazy"' in content_lower:
            patterns.append("Lazy Loading")
        
        if "service worker" in content_lower or "pwa" in content_lower:
            patterns.append("Progressive Web App")
        
        return patterns
    
    def _generate_suggestions(self, content: str, request: ModelRequest) -> List[str]:
        """Generate improvement suggestions with Google AI insights"""
        suggestions = []
        
        content_lower = content.lower()
        
        # Performance suggestions
        if "<img" in content_lower and 'loading="lazy"' not in content_lower:
            suggestions.append("Add lazy loading to images for better performance")
        
        if "<script" in content_lower and not any(attr in content_lower for attr in ["defer", "async"]):
            suggestions.append("Add defer or async attributes to script tags for better loading performance")
        
        # Modern CSS suggestions
        if "px" in content_lower and request.options.responsive_design:
            suggestions.append("Consider using CSS custom properties and relative units for better scalability")
        
        if "media queries" not in content_lower and request.options.responsive_design:
            suggestions.append("Add media queries or container queries for responsive design")
        
        # Accessibility suggestions
        if "<img" in content_lower and "alt=" not in content_lower:
            suggestions.append("Add descriptive alt text to all images for screen readers")
        
        if request.options.accessibility_features:
            if "focus-visible" not in content_lower:
                suggestions.append("Add focus-visible styles for better keyboard navigation")
            
            if "aria-live" not in content_lower and ("dynamic" in content_lower or "update" in content_lower):
                suggestions.append("Consider aria-live regions for dynamic content updates")
        
        # SEO suggestions
        if "<head" in content_lower:
            if "meta name=\"description\"" not in content_lower:
                suggestions.append("Add meta description for better SEO")
            
            if "meta property=\"og:" not in content_lower:
                suggestions.append("Add Open Graph meta tags for social media sharing")
        
        # Security suggestions
        if "target=\"_blank\"" in content_lower and "rel=" not in content_lower:
            suggestions.append("Add rel=\"noopener noreferrer\" to external links for security")
        
        # Progressive Web App suggestions
        if "<html" in content_lower and "manifest" not in content_lower:
            suggestions.append("Consider adding a web app manifest for PWA capabilities")
        
        # Modern web platform suggestions
        if "viewport" in content_lower and "user-scalable=no" in content_lower:
            suggestions.append("Allow user scaling for better accessibility (remove user-scalable=no)")
        
        return suggestions