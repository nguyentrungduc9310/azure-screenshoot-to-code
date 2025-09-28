"""
HuggingFace Provider
Implementation for HuggingFace models
"""
import asyncio
import json
from typing import Dict, List, Optional, Any, AsyncIterator
import base64

from .base_provider import BaseModelProvider, ProviderError
from ..model_types import ModelRequest, ModelResponse, GenerationMetrics

try:
    from huggingface_hub import AsyncInferenceClient
    HUGGINGFACE_AVAILABLE = True
except ImportError:
    HUGGINGFACE_AVAILABLE = False
    AsyncInferenceClient = None

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp = None


class HuggingFaceProvider(BaseModelProvider):
    """HuggingFace model provider implementation"""
    
    async def _initialize_provider(self):
        """Initialize HuggingFace client"""
        if not HUGGINGFACE_AVAILABLE:
            raise ProviderError("HuggingFace Hub library not available. Install with: pip install huggingface_hub",
                              model_id=self.config.model_id)
        
        # Initialize HuggingFace client
        self.client = AsyncInferenceClient(
            model=self.config.model_name or "microsoft/DialoGPT-medium",
            token=self.config.api_key,
            timeout=self.config.timeout_seconds
        )
        
        # Initialize HTTP session for custom endpoints
        if AIOHTTP_AVAILABLE:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            )
        
        # Test connection
        try:
            if hasattr(self.client, 'get_model_status'):
                await self.client.get_model_status()
        except Exception as e:
            self.logger.warning("HuggingFace model status check failed",
                              model_id=self.config.model_id, error=str(e))
    
    async def _cleanup_provider(self):
        """Cleanup HuggingFace client"""
        if hasattr(self, 'session') and self.session:
            await self.session.close()
    
    def _validate_provider_request(self, request: ModelRequest):
        """Validate HuggingFace-specific request parameters"""
        model_name = self.config.model_name or ""
        
        # Check if model supports vision
        vision_models = [
            "llava", "blip", "clip", "git", "pix2struct", 
            "instructblip", "kosmos", "flamingo"
        ]
        
        if request.has_image and not any(vm in model_name.lower() for vm in vision_models):
            raise ProviderError(f"Model {model_name} does not support image input",
                              model_id=self.config.model_id)
        
        # Check token limits (varies by model)
        estimated_tokens = 0
        if request.has_text:
            estimated_tokens += self._estimate_tokens(request.text_prompt)
        
        if request.has_image:
            estimated_tokens += 500  # Conservative estimate for image tokens
        
        # HuggingFace models have varying token limits
        max_tokens = min(self.config.max_tokens, 2048)  # Conservative limit
        
        if estimated_tokens > max_tokens:
            raise ProviderError(f"Request exceeds token limit: {estimated_tokens} > {max_tokens}",
                              model_id=self.config.model_id)
    
    async def _preprocess_request(self, request: ModelRequest) -> Dict[str, Any]:
        """Preprocess request for HuggingFace API"""
        model_name = self.config.model_name or ""
        
        # Determine if this is a vision model
        is_vision_model = any(vm in model_name.lower() for vm in [
            "llava", "blip", "clip", "git", "pix2struct", 
            "instructblip", "kosmos", "flamingo"
        ])
        
        if is_vision_model and request.has_image:
            return await self._preprocess_vision_request(request)
        else:
            return await self._preprocess_text_request(request)
    
    async def _preprocess_vision_request(self, request: ModelRequest) -> Dict[str, Any]:
        """Preprocess vision model request"""
        # Build prompt for vision model
        system_prompt = self._build_system_prompt(request)
        user_prompt = self._build_user_prompt(request)
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        # Prepare image data
        image_data = None
        if request.has_image:
            image_data = request.get_image_bytes()
        
        return {
            "inputs": combined_prompt,
            "image": image_data,
            "parameters": {
                "max_new_tokens": min(self.config.max_tokens, 1024),
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
                "do_sample": True if self.config.temperature > 0 else False
            }
        }
    
    async def _preprocess_text_request(self, request: ModelRequest) -> Dict[str, Any]:
        """Preprocess text-only model request"""
        # Build complete prompt
        system_prompt = self._build_system_prompt(request)
        user_prompt = self._build_user_prompt(request)
        
        # For text models, combine system and user prompts
        if request.has_text:
            combined_prompt = f"{system_prompt}\n\nUser: {user_prompt}\nAssistant:"
        else:
            combined_prompt = f"{system_prompt}\n\nAssistant:"
        
        return {
            "inputs": combined_prompt,
            "parameters": {
                "max_new_tokens": min(self.config.max_tokens, 1024),
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
                "do_sample": True if self.config.temperature > 0 else False,
                "return_full_text": False,
                "stop_sequences": ["User:", "\n\nUser:", "<|endoftext|>"]
            }
        }
    
    async def _make_inference(self, processed_request: Dict[str, Any]) -> Dict[str, Any]:
        """Make inference call to HuggingFace API"""
        try:
            model_name = self.config.model_name or ""
            
            # Check if this is a vision model
            is_vision_model = any(vm in model_name.lower() for vm in [
                "llava", "blip", "clip", "git", "pix2struct"
            ])
            
            if is_vision_model and processed_request.get("image"):
                # Use vision-to-text API
                response = await self.client.visual_question_answering(
                    image=processed_request["image"],
                    question=processed_request["inputs"]
                )
                
                # Convert response format
                if isinstance(response, list) and len(response) > 0:
                    generated_text = response[0].get("answer", "")
                else:
                    generated_text = str(response)
                
            else:
                # Use text generation API
                response = await self.client.text_generation(
                    prompt=processed_request["inputs"],
                    **processed_request["parameters"]
                )
                
                # Extract generated text
                if hasattr(response, 'generated_text'):
                    generated_text = response.generated_text
                elif isinstance(response, dict):
                    generated_text = response.get('generated_text', str(response))
                else:
                    generated_text = str(response)
            
            return {
                "response": response,
                "raw_content": generated_text,
                "model": model_name
            }
        
        except Exception as e:
            error_message = str(e)
            
            if "rate limit" in error_message.lower() or "quota" in error_message.lower():
                raise ProviderError(f"HuggingFace rate limit exceeded: {error_message}",
                                  model_id=self.config.model_id,
                                  error_code="RATE_LIMIT_EXCEEDED")
            
            elif "authorization" in error_message.lower() or "token" in error_message.lower():
                raise ProviderError(f"HuggingFace authentication failed: {error_message}",
                                  model_id=self.config.model_id,
                                  error_code="AUTHENTICATION_ERROR")
            
            elif "model" in error_message.lower() and "not found" in error_message.lower():
                raise ProviderError(f"HuggingFace model not found: {error_message}",
                                  model_id=self.config.model_id,
                                  error_code="MODEL_NOT_FOUND")
            
            else:
                raise ProviderError(f"HuggingFace request failed: {error_message}",
                                  model_id=self.config.model_id,
                                  error_code="REQUEST_FAILED")
    
    async def _postprocess_response(self, raw_response: Dict[str, Any], 
                                   original_request: ModelRequest) -> ModelResponse:
        """Postprocess HuggingFace response"""
        content = raw_response["raw_content"]
        
        # Clean up the content
        content = self._clean_generated_text(content)
        
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
        
        # Estimate metrics (HuggingFace doesn't provide usage stats)
        response.metrics.input_tokens = self._estimate_tokens(
            str(original_request.text_prompt or "")
        )
        response.metrics.output_tokens = self._estimate_tokens(content)
        response.metrics.total_tokens = response.metrics.input_tokens + response.metrics.output_tokens
        
        # Calculate quality score
        response.quality_score = self._calculate_quality_score(
            response.__dict__, original_request
        )
        
        # Set confidence score (estimate based on content quality)
        response.metrics.confidence_score = self._estimate_confidence(content, original_request)
        
        # Analyze generated content
        response.detected_elements = self._analyze_elements(content)
        response.detected_patterns = self._analyze_patterns(content)
        response.suggested_improvements = self._generate_suggestions(content, original_request)
        
        return response
    
    async def _stream_inference(self, processed_request: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        """Stream inference call to HuggingFace API"""
        try:
            # Note: Not all HuggingFace models support streaming
            # We'll simulate streaming by chunking the response
            
            response_data = await self._make_inference(processed_request)
            content = response_data["raw_content"]
            
            # Simulate streaming by sending content in chunks
            chunk_size = 50  # characters per chunk
            
            for i in range(0, len(content), chunk_size):
                chunk = content[i:i + chunk_size]
                accumulated = content[:i + len(chunk)]
                
                yield {
                    "type": "content",
                    "content": chunk,
                    "accumulated": accumulated
                }
                
                # Small delay to simulate streaming
                await asyncio.sleep(0.1)
            
            # Extract final code blocks
            code_blocks = self._extract_code_blocks(content)
            
            yield {
                "type": "complete",
                "content": content,
                "code_blocks": code_blocks,
                "finish_reason": "stop"
            }
        
        except Exception as e:
            yield {
                "type": "error",
                "error": str(e),
                "error_code": self._get_error_code(e)
            }
    
    def _clean_generated_text(self, text: str) -> str:
        """Clean up generated text from HuggingFace models"""
        # Remove common artifacts
        text = text.strip()
        
        # Remove repetitive patterns
        lines = text.split('\n')
        cleaned_lines = []
        prev_line = ""
        
        for line in lines:
            # Skip if line is exactly the same as previous
            if line != prev_line:
                cleaned_lines.append(line)
                prev_line = line
        
        cleaned_text = '\n'.join(cleaned_lines)
        
        # Remove trailing incomplete sentences
        if cleaned_text and not cleaned_text.endswith(('.', '>', '}', ';', ')')):
            sentences = cleaned_text.split('.')
            if len(sentences) > 1:
                cleaned_text = '.'.join(sentences[:-1]) + '.'
        
        return cleaned_text
    
    def _estimate_confidence(self, content: str, request: ModelRequest) -> float:
        """Estimate confidence score based on content quality"""
        confidence = 0.5  # Base confidence
        
        # Check for code structure
        if any(tag in content.lower() for tag in ['<html', '<div', '<span', 'class=', 'function']):
            confidence += 0.2
        
        # Check for completeness
        if content.count('<') == content.count('>'):  # Balanced tags
            confidence += 0.1
        
        if len(content) > 100:  # Reasonable length
            confidence += 0.1
        
        # Check for requested features
        if request.options.responsive_design and 'responsive' in content.lower():
            confidence += 0.05
        
        if request.options.accessibility_features and 'aria' in content.lower():
            confidence += 0.05
        
        return min(confidence, 1.0)
    
    def _build_system_prompt(self, request: ModelRequest) -> str:
        """Build system prompt optimized for HuggingFace models"""
        framework = request.options.framework.value
        quality = request.options.quality.value
        
        prompt_parts = [
            f"You are a skilled {framework.upper()} developer.",
            f"Create {quality} quality web code based on the input provided.",
            "Generate clean, functional code that follows best practices."
        ]
        
        if request.options.include_comments:
            prompt_parts.append("Include helpful comments in the code.")
        
        if request.options.responsive_design:
            prompt_parts.append("Make the design responsive for different screen sizes.")
        
        if request.options.accessibility_features:
            prompt_parts.append("Include accessibility features for better usability.")
        
        # Add HuggingFace-specific instructions
        prompt_parts.extend([
            "Structure your code clearly with proper indentation.",
            "Use semantic HTML elements when appropriate.",
            "Provide working, complete code that can be used directly."
        ])
        
        return " ".join(prompt_parts)
    
    def _analyze_elements(self, content: str) -> List[Dict[str, Any]]:
        """Analyze HTML elements in HuggingFace generated content"""
        import re
        
        elements = []
        
        # Simple element analysis
        tag_pattern = r'<(\w+)([^>]*)>'
        matches = re.finditer(tag_pattern, content, re.IGNORECASE)
        
        for match in matches:
            tag_name = match.group(1).lower()
            attributes = match.group(2)
            
            element = {
                "tag": tag_name,
                "attributes": {},
                "position": match.start(),
                "self_closing": match.group(0).endswith('/>'),
                "has_content": self._element_has_content(content, match.end(), tag_name)
            }
            
            # Parse basic attributes
            attr_pattern = r'(\w+)=(["\'])([^"\']*)\2'
            attr_matches = re.finditer(attr_pattern, attributes)
            
            for attr_match in attr_matches:
                attr_name = attr_match.group(1)
                attr_value = attr_match.group(3)
                element["attributes"][attr_name] = attr_value
            
            elements.append(element)
        
        return elements
    
    def _element_has_content(self, content: str, start_pos: int, tag_name: str) -> bool:
        """Check if element has content between opening and closing tags"""
        closing_tag = f"</{tag_name}>"
        closing_pos = content.lower().find(closing_tag.lower(), start_pos)
        
        if closing_pos == -1:
            return False
        
        content_between = content[start_pos:closing_pos].strip()
        return len(content_between) > 0
    
    def _analyze_patterns(self, content: str) -> List[str]:
        """Analyze patterns in HuggingFace generated content"""
        patterns = []
        
        content_lower = content.lower()
        
        # Basic HTML patterns
        if "<html" in content_lower or "<!doctype" in content_lower:
            patterns.append("Complete HTML Document")
        
        if "<head" in content_lower and "<body" in content_lower:
            patterns.append("Structured HTML Layout")
        
        # CSS patterns
        if "style=" in content_lower:
            patterns.append("Inline Styles")
        
        if "<style" in content_lower:
            patterns.append("Embedded CSS")
        
        if "class=" in content_lower:
            patterns.append("CSS Classes")
        
        # JavaScript patterns
        if "<script" in content_lower:
            patterns.append("JavaScript Integration")
        
        if "function" in content_lower:
            patterns.append("JavaScript Functions")
        
        # Framework patterns
        if framework_indicators := [fw for fw in ["react", "vue", "angular"] if fw in content_lower]:
            patterns.extend([f"{fw.title()} Framework" for fw in framework_indicators])
        
        # Responsive patterns
        if "@media" in content_lower or "responsive" in content_lower:
            patterns.append("Responsive Design")
        
        return patterns
    
    def _generate_suggestions(self, content: str, request: ModelRequest) -> List[str]:
        """Generate suggestions for HuggingFace generated content"""
        suggestions = []
        
        content_lower = content.lower()
        
        # Structure suggestions
        if "<html" not in content_lower and "<div" in content_lower:
            suggestions.append("Consider wrapping content in a complete HTML document")
        
        if "<!doctype" not in content_lower and "<html" in content_lower:
            suggestions.append("Add DOCTYPE declaration for HTML5")
        
        # Styling suggestions
        if "style=" in content_lower:
            suggestions.append("Consider moving inline styles to a separate CSS file")
        
        if "<style" not in content_lower and "class=" in content_lower:
            suggestions.append("Add CSS styles for the defined classes")
        
        # Functionality suggestions
        if "<form" in content_lower and "action=" not in content_lower:
            suggestions.append("Add form action attribute for proper form submission")
        
        if "<img" in content_lower and "alt=" not in content_lower:
            suggestions.append("Add alt attributes to images for accessibility")
        
        # Framework-specific suggestions
        if request.options.framework.value != "html":
            framework = request.options.framework.value
            if framework.lower() not in content_lower:
                suggestions.append(f"Consider adding {framework}-specific syntax and patterns")
        
        # Quality improvements
        if len(content) < 200:
            suggestions.append("Content might be too brief - consider adding more detail")
        
        if content.count('<') != content.count('>'):
            suggestions.append("Check for unbalanced HTML tags")
        
        return suggestions