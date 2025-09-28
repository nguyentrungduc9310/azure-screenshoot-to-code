"""
Azure Provider
Implementation for Azure OpenAI models
"""
import asyncio
import json
from typing import Dict, List, Optional, Any, AsyncIterator

from .base_provider import BaseModelProvider, ProviderError
from ..model_types import ModelRequest, ModelResponse, GenerationMetrics

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None


class AzureProvider(BaseModelProvider):
    """Azure OpenAI model provider implementation"""
    
    async def _initialize_provider(self):
        """Initialize Azure OpenAI client"""
        if not OPENAI_AVAILABLE:
            raise ProviderError("OpenAI library not available. Install with: pip install openai",
                              model_id=self.config.model_id)
        
        if not self.config.api_key:
            raise ProviderError("Azure OpenAI API key not configured",
                              model_id=self.config.model_id)
        
        if not self.config.api_endpoint:
            raise ProviderError("Azure OpenAI endpoint not configured",
                              model_id=self.config.model_id)
        
        # Initialize Azure OpenAI client
        self.client = openai.AsyncAzureOpenAI(
            api_key=self.config.api_key,
            api_version="2024-02-15-preview",  # Latest API version
            azure_endpoint=self.config.api_endpoint,
            timeout=self.config.timeout_seconds
        )
        
        # Test connection
        try:
            deployments = await self.client.deployments.list()
        except Exception as e:
            raise ProviderError(f"Failed to connect to Azure OpenAI: {str(e)}",
                              model_id=self.config.model_id)
    
    async def _cleanup_provider(self):
        """Cleanup Azure OpenAI client"""
        if hasattr(self, 'client'):
            await self.client.close()
    
    def _validate_provider_request(self, request: ModelRequest):
        """Validate Azure OpenAI-specific request parameters"""
        # Check deployment name is configured
        deployment_name = self.config.custom_parameters.get('deployment_name')
        if not deployment_name:
            raise ProviderError("Azure deployment name not configured",
                              model_id=self.config.model_id)
        
        # Check model capabilities
        if request.has_image and "gpt-4" not in deployment_name.lower():
            raise ProviderError("Image input requires GPT-4V deployment",
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
        """Preprocess request for Azure OpenAI API"""
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
        deployment_name = self.config.custom_parameters.get('deployment_name', 'gpt-4-vision')
        
        api_params = {
            "model": deployment_name,  # Azure uses deployment name as model
            "messages": messages,
            "max_tokens": min(self.config.max_tokens, 4000),
            "temperature": self.config.temperature,
            "top_p": self.config.top_p
        }
        
        # Add Azure-specific parameters
        if 'seed' in self.config.custom_parameters:
            api_params['seed'] = self.config.custom_parameters['seed']
        
        if 'response_format' in self.config.custom_parameters:
            api_params['response_format'] = self.config.custom_parameters['response_format']
        
        return {
            "api_params": api_params,
            "messages": messages,
            "deployment_name": deployment_name
        }
    
    async def _make_inference(self, processed_request: Dict[str, Any]) -> Dict[str, Any]:
        """Make inference call to Azure OpenAI API"""
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
            raise ProviderError(f"Azure OpenAI rate limit exceeded: {str(e)}",
                              model_id=self.config.model_id,
                              error_code="RATE_LIMIT_EXCEEDED")
        
        except openai.AuthenticationError as e:
            raise ProviderError(f"Azure OpenAI authentication failed: {str(e)}",
                              model_id=self.config.model_id,
                              error_code="AUTHENTICATION_ERROR")
        
        except openai.APIError as e:
            raise ProviderError(f"Azure OpenAI API error: {str(e)}",
                              model_id=self.config.model_id,
                              error_code="API_ERROR")
        
        except Exception as e:
            raise ProviderError(f"Azure OpenAI request failed: {str(e)}",
                              model_id=self.config.model_id,
                              error_code="REQUEST_FAILED")
    
    async def _postprocess_response(self, raw_response: Dict[str, Any], 
                                   original_request: ModelRequest) -> ModelResponse:
        """Postprocess Azure OpenAI response"""
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
        
        # Set confidence score
        response.metrics.confidence_score = min(response.quality_score + 0.2, 1.0)
        
        # Analyze generated content
        response.detected_elements = self._analyze_elements(content)
        response.detected_patterns = self._analyze_patterns(content)
        response.suggested_improvements = self._generate_suggestions(content, original_request)
        
        return response
    
    async def _stream_inference(self, processed_request: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        """Stream inference call to Azure OpenAI API"""
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
    
    def _build_system_prompt(self, request: ModelRequest) -> str:
        """Build system prompt optimized for Azure OpenAI"""
        framework = request.options.framework.value
        quality = request.options.quality.value
        
        prompt_parts = [
            f"You are an expert {framework.upper()} developer using Azure OpenAI.",
            f"Generate {quality} quality, enterprise-ready code from the provided input.",
            "Focus on clean, scalable, and maintainable code that follows enterprise best practices."
        ]
        
        if request.options.include_comments:
            prompt_parts.append("Include comprehensive comments and documentation.")
        
        if request.options.responsive_design:
            prompt_parts.append("Ensure responsive design for all device types.")
        
        if request.options.accessibility_features:
            prompt_parts.append("Implement comprehensive accessibility features for compliance.")
        
        if request.options.use_typescript and framework in ["react", "vue", "angular"]:
            prompt_parts.append("Use TypeScript with strict type checking.")
        
        if request.options.use_scss:
            prompt_parts.append("Use SCSS with organized structure and variables.")
        
        # Add Azure-specific enterprise considerations
        prompt_parts.extend([
            "Consider security, scalability, and maintainability in enterprise environments.",
            "Structure code for easy testing and deployment in Azure environments.",
            "Follow Microsoft's recommended patterns and practices."
        ])
        
        return " ".join(prompt_parts)
    
    def _analyze_elements(self, content: str) -> List[Dict[str, Any]]:
        """Analyze HTML elements with Azure enterprise focus"""
        import re
        
        elements = []
        
        # Find HTML tags with enterprise analysis
        tag_pattern = r'<(\w+)([^>]*)>'
        matches = re.finditer(tag_pattern, content, re.IGNORECASE)
        
        for match in matches:
            tag_name = match.group(1).lower()
            attributes = match.group(2)
            
            element = {
                "tag": tag_name,
                "attributes": {},
                "position": match.start(),
                "enterprise_ready": self._is_enterprise_ready(tag_name, attributes),
                "security_considerations": self._get_security_considerations(tag_name, attributes),
                "scalability_impact": self._assess_scalability_impact(tag_name)
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
    
    def _is_enterprise_ready(self, tag: str, attributes: str) -> bool:
        """Check if element follows enterprise patterns"""
        enterprise_indicators = [
            'data-testid=',  # Testing ready
            'aria-',         # Accessibility ready
            'role=',         # Semantic ready
            'id=',           # Identifiable
            'class='         # Styled/themeable
        ]
        
        return any(indicator in attributes.lower() for indicator in enterprise_indicators)
    
    def _get_security_considerations(self, tag: str, attributes: str) -> List[str]:
        """Get security considerations for element"""
        considerations = []
        
        if tag == 'form':
            if 'csrf' not in attributes.lower():
                considerations.append("Consider CSRF protection")
            if 'novalidate' in attributes.lower():
                considerations.append("Client-side validation disabled")
        
        elif tag == 'a' and 'href=' in attributes:
            if 'target="_blank"' in attributes and 'rel=' not in attributes:
                considerations.append("Missing rel='noopener noreferrer' for external links")
        
        elif tag == 'input':
            if 'type="password"' in attributes and 'autocomplete=' not in attributes:
                considerations.append("Consider autocomplete settings for password fields")
        
        elif tag == 'iframe':
            if 'sandbox=' not in attributes:
                considerations.append("Consider iframe sandboxing")
        
        return considerations
    
    def _assess_scalability_impact(self, tag: str) -> str:
        """Assess scalability impact of element"""
        high_impact_tags = ['video', 'canvas', 'iframe', 'object', 'embed']
        medium_impact_tags = ['img', 'audio', 'svg']
        
        if tag in high_impact_tags:
            return "high"
        elif tag in medium_impact_tags:
            return "medium"
        else:
            return "low"
    
    def _analyze_patterns(self, content: str) -> List[str]:
        """Analyze patterns with enterprise focus"""
        patterns = []
        
        content_lower = content.lower()
        
        # Enterprise framework patterns
        if "azure" in content_lower or "microsoft" in content_lower:
            patterns.append("Azure/Microsoft Integration")
        
        if "oauth" in content_lower or "msal" in content_lower:
            patterns.append("Microsoft Authentication")
        
        # Security patterns
        if "csp" in content_lower or "content-security-policy" in content_lower:
            patterns.append("Content Security Policy")
        
        if "csrf" in content_lower or "xsrf" in content_lower:
            patterns.append("CSRF Protection")
        
        # Performance patterns
        if "cdn" in content_lower:
            patterns.append("CDN Integration")
        
        if "lazy" in content_lower or 'loading="lazy"' in content_lower:
            patterns.append("Lazy Loading")
        
        # Enterprise UI patterns
        if "fluent" in content_lower or "fabric" in content_lower:
            patterns.append("Microsoft Fluent UI")
        
        if "theme" in content_lower and "dark" in content_lower:
            patterns.append("Dark Mode Support")
        
        # Monitoring patterns
        if "application insights" in content_lower or "telemetry" in content_lower:
            patterns.append("Application Insights Integration")
        
        return patterns
    
    def _generate_suggestions(self, content: str, request: ModelRequest) -> List[str]:
        """Generate enterprise-focused suggestions"""
        suggestions = []
        
        content_lower = content.lower()
        
        # Enterprise security suggestions
        if "<form" in content_lower and "csrf" not in content_lower:
            suggestions.append("Add CSRF protection to forms for enterprise security")
        
        if "api" in content_lower and "authentication" not in content_lower:
            suggestions.append("Consider implementing Azure AD authentication for API calls")
        
        # Performance suggestions for enterprise scale
        if "<img" in content_lower and "cdn" not in content_lower:
            suggestions.append("Consider using Azure CDN for image assets in production")
        
        if "fetch(" in content_lower or "xhr" in content_lower:
            suggestions.append("Implement retry logic and circuit breakers for API calls")
        
        # Monitoring suggestions
        if "<html" in content_lower and "application insights" not in content_lower:
            suggestions.append("Consider integrating Azure Application Insights for monitoring")
        
        # Accessibility for enterprise compliance
        if request.options.accessibility_features and "aria-live" not in content_lower:
            suggestions.append("Add aria-live regions for dynamic content to meet enterprise accessibility standards")
        
        # Scalability suggestions
        if "style=" in content_lower:
            suggestions.append("Extract inline styles to CSS files for better caching and scalability")
        
        if "console.log" in content_lower:
            suggestions.append("Replace console.log with proper logging service for production")
        
        # Azure-specific suggestions
        if "storage" in content_lower:
            suggestions.append("Consider Azure Blob Storage for file uploads and static assets")
        
        if "database" in content_lower or "data" in content_lower:
            suggestions.append("Consider Azure Cosmos DB or SQL Database for data persistence")
        
        return suggestions