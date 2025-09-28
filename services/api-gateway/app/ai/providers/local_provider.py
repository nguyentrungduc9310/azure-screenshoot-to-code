"""
Local Model Provider
Implementation for local AI models (Ollama, local inference servers, etc.)
"""
import asyncio
import json
from typing import Dict, List, Optional, Any, AsyncIterator
import base64

from .base_provider import BaseModelProvider, ProviderError
from ..model_types import ModelRequest, ModelResponse, GenerationMetrics

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp = None


class LocalModelProvider(BaseModelProvider):
    """Local model provider implementation for self-hosted models"""
    
    async def _initialize_provider(self):
        """Initialize local model client"""
        if not AIOHTTP_AVAILABLE:
            raise ProviderError("aiohttp library not available. Install with: pip install aiohttp",
                              model_id=self.config.model_id)
        
        if not self.config.api_endpoint:
            # Default to Ollama endpoint
            self.config.api_endpoint = "http://localhost:11434"
        
        # Initialize HTTP session
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds),
            headers={"Content-Type": "application/json"}
        )
        
        # Add API key header if provided
        if self.config.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.config.api_key}"})
        
        # Determine local server type
        self.server_type = self._detect_server_type()
        
        # Test connection
        try:
            await self._test_connection()
        except Exception as e:
            await self.session.close()
            raise ProviderError(f"Failed to connect to local model server: {str(e)}",
                              model_id=self.config.model_id)
    
    async def _cleanup_provider(self):
        """Cleanup local model client"""
        if hasattr(self, 'session') and self.session:
            await self.session.close()
    
    def _detect_server_type(self) -> str:
        """Detect the type of local server"""
        endpoint = self.config.api_endpoint.lower()
        
        if "ollama" in endpoint or ":11434" in endpoint:
            return "ollama"
        elif "text-generation-webui" in endpoint or ":7860" in endpoint:
            return "text_generation_webui"
        elif "vllm" in endpoint or "openai" in endpoint:
            return "vllm"
        elif "llamacpp" in endpoint or "llama.cpp" in endpoint:
            return "llamacpp"
        else:
            return "generic"
    
    async def _test_connection(self):
        """Test connection to local model server"""
        if self.server_type == "ollama":
            # Test Ollama endpoint
            async with self.session.get(f"{self.config.api_endpoint}/api/tags") as response:
                if response.status != 200:
                    raise Exception(f"Ollama server returned status {response.status}")
        
        elif self.server_type == "vllm":
            # Test vLLM OpenAI-compatible endpoint
            async with self.session.get(f"{self.config.api_endpoint}/v1/models") as response:
                if response.status != 200:
                    raise Exception(f"vLLM server returned status {response.status}")
        
        else:
            # Generic test - try to ping the endpoint
            try:
                async with self.session.get(f"{self.config.api_endpoint}/health") as response:
                    pass
            except:
                # If health endpoint doesn't exist, that's ok
                pass
    
    def _validate_provider_request(self, request: ModelRequest):
        """Validate local model-specific request parameters"""
        # Check if model supports vision (depends on local model capabilities)
        if request.has_image:
            vision_models = ["llava", "bakllava", "moondream", "cogvlm"]
            model_name = self.config.model_name.lower()
            
            if not any(vm in model_name for vm in vision_models):
                self.logger.warning("Image input provided but model may not support vision",
                                  model_id=self.config.model_id, model_name=self.config.model_name)
        
        # Check token limits (typically more flexible for local models)
        estimated_tokens = 0
        if request.has_text:
            estimated_tokens += self._estimate_tokens(request.text_prompt)
        
        if request.has_image:
            estimated_tokens += 500  # Conservative estimate
        
        # Local models often have higher token limits
        max_tokens = min(self.config.max_tokens, 8192)
        
        if estimated_tokens > max_tokens:
            self.logger.warning("Request may exceed token limit",
                              estimated=estimated_tokens, max_tokens=max_tokens)
    
    async def _preprocess_request(self, request: ModelRequest) -> Dict[str, Any]:
        """Preprocess request for local model API"""
        if self.server_type == "ollama":
            return await self._preprocess_ollama_request(request)
        elif self.server_type == "vllm":
            return await self._preprocess_vllm_request(request)
        elif self.server_type == "text_generation_webui":
            return await self._preprocess_textgen_request(request)
        else:
            return await self._preprocess_generic_request(request)
    
    async def _preprocess_ollama_request(self, request: ModelRequest) -> Dict[str, Any]:
        """Preprocess request for Ollama"""
        # Build system and user messages
        system_prompt = self._build_system_prompt(request)
        user_prompt = self._build_user_prompt(request)
        
        # Ollama API format
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # Add image if provided
        if request.has_image:
            messages[-1]["images"] = [request.image_data]
        
        api_params = {
            "model": self.config.model_name or "llama2",
            "messages": messages,
            "options": {
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
                "num_predict": min(self.config.max_tokens, 2048)
            }
        }
        
        return {
            "endpoint": "/api/chat",
            "method": "POST",
            "data": api_params
        }
    
    async def _preprocess_vllm_request(self, request: ModelRequest) -> Dict[str, Any]:
        """Preprocess request for vLLM (OpenAI-compatible)"""
        messages = []
        
        # Add system message
        system_prompt = self._build_system_prompt(request)
        messages.append({"role": "system", "content": system_prompt})
        
        # Build user message
        user_content = []
        
        if request.has_text:
            user_prompt = self._build_user_prompt(request)
            user_content.append({"type": "text", "text": user_prompt})
        
        if request.has_image:
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{request.image_data}"}
            })
        
        messages.append({
            "role": "user",
            "content": user_content if len(user_content) > 1 else user_content[0]["text"]
        })
        
        api_params = {
            "model": self.config.model_name or "local-model",
            "messages": messages,
            "max_tokens": min(self.config.max_tokens, 2048),
            "temperature": self.config.temperature,
            "top_p": self.config.top_p
        }
        
        return {
            "endpoint": "/v1/chat/completions",
            "method": "POST",
            "data": api_params
        }
    
    async def _preprocess_textgen_request(self, request: ModelRequest) -> Dict[str, Any]:
        """Preprocess request for text-generation-webui"""
        system_prompt = self._build_system_prompt(request)
        user_prompt = self._build_user_prompt(request)
        
        # Combine prompts
        full_prompt = f"{system_prompt}\n\nUser: {user_prompt}\nAssistant:"
        
        api_params = {
            "prompt": full_prompt,
            "max_new_tokens": min(self.config.max_tokens, 1024),
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "do_sample": True,
            "truncation_length": 4096
        }
        
        return {
            "endpoint": "/api/v1/generate",
            "method": "POST",
            "data": api_params
        }
    
    async def _preprocess_generic_request(self, request: ModelRequest) -> Dict[str, Any]:
        """Preprocess request for generic local server"""
        system_prompt = self._build_system_prompt(request)
        user_prompt = self._build_user_prompt(request)
        
        api_params = {
            "prompt": f"{system_prompt}\n\n{user_prompt}",
            "max_tokens": min(self.config.max_tokens, 1024),
            "temperature": self.config.temperature,
            "top_p": self.config.top_p
        }
        
        # Add image if provided
        if request.has_image:
            api_params["image"] = request.image_data
        
        return {
            "endpoint": "/generate",
            "method": "POST",
            "data": api_params
        }
    
    async def _make_inference(self, processed_request: Dict[str, Any]) -> Dict[str, Any]:
        """Make inference call to local model API"""
        endpoint = processed_request["endpoint"]
        method = processed_request["method"]
        data = processed_request["data"]
        
        url = f"{self.config.api_endpoint}{endpoint}"
        
        try:
            async with self.session.request(method, url, json=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Server returned status {response.status}: {error_text}")
                
                response_data = await response.json()
                
                # Extract content based on server type
                if self.server_type == "ollama":
                    content = response_data.get("message", {}).get("content", "")
                elif self.server_type == "vllm":
                    choices = response_data.get("choices", [])
                    if choices:
                        content = choices[0].get("message", {}).get("content", "")
                    else:
                        content = ""
                elif self.server_type == "text_generation_webui":
                    results = response_data.get("results", [])
                    if results:
                        content = results[0].get("text", "")
                    else:
                        content = ""
                else:
                    # Generic extraction
                    content = response_data.get("response", 
                             response_data.get("text", 
                             response_data.get("content", str(response_data))))
                
                return {
                    "response": response_data,
                    "raw_content": content,
                    "server_type": self.server_type
                }
        
        except asyncio.TimeoutError:
            raise ProviderError("Local model request timed out",
                              model_id=self.config.model_id,
                              error_code="TIMEOUT_ERROR")
        
        except aiohttp.ClientError as e:
            raise ProviderError(f"Local model connection error: {str(e)}",
                              model_id=self.config.model_id,
                              error_code="CONNECTION_ERROR")
        
        except Exception as e:
            raise ProviderError(f"Local model request failed: {str(e)}",
                              model_id=self.config.model_id,
                              error_code="REQUEST_FAILED")
    
    async def _postprocess_response(self, raw_response: Dict[str, Any], 
                                   original_request: ModelRequest) -> ModelResponse:
        """Postprocess local model response"""
        content = raw_response["raw_content"]
        
        # Clean up content
        content = self._clean_local_response(content)
        
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
        
        # Estimate metrics (local models don't provide usage stats)
        response.metrics.input_tokens = self._estimate_tokens(
            str(original_request.text_prompt or "")
        )
        response.metrics.output_tokens = self._estimate_tokens(content)
        response.metrics.total_tokens = response.metrics.input_tokens + response.metrics.output_tokens
        
        # Calculate quality score
        response.quality_score = self._calculate_quality_score(
            response.__dict__, original_request
        )
        
        # Set confidence score (estimate for local models)
        response.metrics.confidence_score = self._estimate_local_confidence(content, original_request)
        
        # Analyze generated content
        response.detected_elements = self._analyze_elements(content)
        response.detected_patterns = self._analyze_patterns(content)
        response.suggested_improvements = self._generate_suggestions(content, original_request)
        
        return response
    
    async def _stream_inference(self, processed_request: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        """Stream inference call to local model API"""
        try:
            endpoint = processed_request["endpoint"]
            data = processed_request["data"]
            url = f"{self.config.api_endpoint}{endpoint}"
            
            # Add streaming parameter
            if self.server_type == "ollama":
                data["stream"] = True
            elif self.server_type == "vllm":
                data["stream"] = True
            elif self.server_type == "text_generation_webui":
                data["stream"] = True
            
            accumulated_content = ""
            
            async with self.session.post(url, json=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Server returned status {response.status}: {error_text}")
                
                async for line in response.content:
                    if line:
                        line_text = line.decode('utf-8').strip()
                        
                        if line_text.startswith('data: '):
                            line_text = line_text[6:]
                        
                        if line_text == '[DONE]':
                            break
                        
                        try:
                            chunk_data = json.loads(line_text)
                            
                            # Extract content based on server type
                            if self.server_type == "ollama":
                                if "message" in chunk_data:
                                    chunk_content = chunk_data["message"].get("content", "")
                                else:
                                    continue
                            elif self.server_type == "vllm":
                                choices = chunk_data.get("choices", [])
                                if choices and "delta" in choices[0]:
                                    chunk_content = choices[0]["delta"].get("content", "")
                                else:
                                    continue
                            else:
                                chunk_content = chunk_data.get("text", "")
                            
                            if chunk_content:
                                accumulated_content += chunk_content
                                
                                yield {
                                    "type": "content",
                                    "content": chunk_content,
                                    "accumulated": accumulated_content
                                }
                        
                        except json.JSONDecodeError:
                            continue
            
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
    
    def _clean_local_response(self, content: str) -> str:
        """Clean up response from local models"""
        content = content.strip()
        
        # Remove common prefixes from local models
        prefixes_to_remove = [
            "Assistant:",
            "AI:",
            "Response:",
            "Output:",
            "Result:"
        ]
        
        for prefix in prefixes_to_remove:
            if content.startswith(prefix):
                content = content[len(prefix):].strip()
        
        # Remove repetitive patterns common in local models
        lines = content.split('\n')
        cleaned_lines = []
        prev_line = ""
        repetition_count = 0
        
        for line in lines:
            if line == prev_line:
                repetition_count += 1
                if repetition_count < 2:  # Allow one repetition
                    cleaned_lines.append(line)
            else:
                repetition_count = 0
                cleaned_lines.append(line)
                prev_line = line
        
        return '\n'.join(cleaned_lines)
    
    def _estimate_local_confidence(self, content: str, request: ModelRequest) -> float:
        """Estimate confidence for local model responses"""
        confidence = 0.4  # Base confidence for local models
        
        # Check content quality indicators
        if len(content) > 50:
            confidence += 0.1
        
        if any(tag in content.lower() for tag in ['<html', '<div', '<p', 'class=', 'style=']):
            confidence += 0.2
        
        # Check for requested features
        if request.options.framework.value.lower() in content.lower():
            confidence += 0.1
        
        if request.options.responsive_design and ('responsive' in content.lower() or '@media' in content.lower()):
            confidence += 0.1
        
        if request.options.accessibility_features and 'aria' in content.lower():
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _build_system_prompt(self, request: ModelRequest) -> str:
        """Build system prompt optimized for local models"""
        framework = request.options.framework.value
        quality = request.options.quality.value
        
        prompt_parts = [
            f"You are an expert web developer specializing in {framework.upper()}.",
            f"Generate {quality} quality, clean, and functional code.",
            "Focus on creating practical, working code that follows best practices."
        ]
        
        if request.options.include_comments:
            prompt_parts.append("Include clear comments explaining the code.")
        
        if request.options.responsive_design:
            prompt_parts.append("Make the design responsive and mobile-friendly.")
        
        if request.options.accessibility_features:
            prompt_parts.append("Include accessibility features like ARIA labels and semantic HTML.")
        
        # Add local model specific instructions
        prompt_parts.extend([
            "Provide complete, ready-to-use code.",
            "Structure the code clearly with proper formatting.",
            "Avoid repetition and keep responses focused."
        ])
        
        return " ".join(prompt_parts)
    
    def _analyze_patterns(self, content: str) -> List[str]:
        """Analyze patterns in local model generated content"""
        patterns = []
        
        content_lower = content.lower()
        
        # Local model specific patterns
        if "localhost" in content_lower or "127.0.0.1" in content_lower:
            patterns.append("Local Development References")
        
        # Standard web patterns
        if "<html" in content_lower:
            patterns.append("HTML Document Structure")
        
        if "css" in content_lower or "style" in content_lower:
            patterns.append("CSS Styling")
        
        if "javascript" in content_lower or "function" in content_lower:
            patterns.append("JavaScript Functionality")
        
        # Framework patterns
        frameworks = ["react", "vue", "angular", "svelte"]
        for fw in frameworks:
            if fw in content_lower:
                patterns.append(f"{fw.title()} Framework")
        
        # Design patterns
        if "responsive" in content_lower or "@media" in content_lower:
            patterns.append("Responsive Design")
        
        if "grid" in content_lower or "flexbox" in content_lower:
            patterns.append("Modern CSS Layout")
        
        return patterns
    
    def _generate_suggestions(self, content: str, request: ModelRequest) -> List[str]:
        """Generate suggestions for local model responses"""
        suggestions = []
        
        content_lower = content.lower()
        
        # Local model specific suggestions
        if len(content) < 100:
            suggestions.append("Response seems brief - consider asking for more detailed code")
        
        if "localhost" in content_lower:
            suggestions.append("Replace localhost references with appropriate production URLs")
        
        # Code quality suggestions
        if "<style" not in content_lower and "class=" in content_lower:
            suggestions.append("Add CSS styles for the defined classes")
        
        if "<img" in content_lower and "alt=" not in content_lower:
            suggestions.append("Add alt attributes to images for accessibility")
        
        if "function" in content_lower and "/*" not in content_lower:
            suggestions.append("Add comments to JavaScript functions for better documentation")
        
        # Framework suggestions
        if request.options.framework.value != "html":
            framework = request.options.framework.value
            if framework.lower() not in content_lower:
                suggestions.append(f"Consider adding {framework}-specific patterns and components")
        
        # Best practices
        if "<!doctype" not in content_lower and "<html" in content_lower:
            suggestions.append("Add HTML5 DOCTYPE declaration")
        
        if "<head" in content_lower and "viewport" not in content_lower:
            suggestions.append("Add viewport meta tag for mobile responsiveness")
        
        return suggestions