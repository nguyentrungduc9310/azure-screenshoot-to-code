"""
Provider Manager for handling multiple AI providers
Manages OpenAI, Azure OpenAI, Anthropic Claude, and Google Gemini
"""
import asyncio
import time
from typing import Dict, List, Optional, Any, AsyncGenerator
from dataclasses import dataclass
from enum import Enum

import openai
import anthropic
import google.generativeai as genai
from openai.types.chat import ChatCompletionMessageParam

from app.core.config import Settings, AIProvider
from shared.monitoring.structured_logger import StructuredLogger
from shared.monitoring.correlation import get_correlation_id

class GenerationMode(str, Enum):
    CREATE = "create"
    UPDATE = "update"

@dataclass
class GenerationRequest:
    """Request for code generation"""
    prompt_messages: List[ChatCompletionMessageParam]
    provider: AIProvider
    stack: str
    mode: GenerationMode = GenerationMode.CREATE
    temperature: float = 0.0
    max_tokens: int = 4096
    stream: bool = True
    correlation_id: Optional[str] = None

@dataclass
class GenerationResult:
    """Result from code generation"""
    content: str
    provider: AIProvider
    model: str
    duration_seconds: float
    token_usage: Optional[Dict[str, int]] = None
    correlation_id: Optional[str] = None
    error: Optional[str] = None

class ProviderManager:
    """Manages multiple AI providers for code generation"""
    
    def __init__(self, settings: Settings, logger: StructuredLogger):
        self.settings = settings
        self.logger = logger
        self.providers: Dict[AIProvider, Any] = {}
        self.available_providers: List[AIProvider] = []
        
        # Provider configurations
        self.provider_configs = {
            AIProvider.OPENAI: {
                "model": settings.openai_model,
                "max_tokens": settings.openai_max_tokens,
                "temperature": settings.openai_temperature
            },
            AIProvider.AZURE_OPENAI: {
                "model": settings.openai_model,  # Use same model for Azure
                "max_tokens": settings.openai_max_tokens,
                "temperature": settings.openai_temperature
            },
            AIProvider.CLAUDE: {
                "model": settings.anthropic_model,
                "max_tokens": settings.anthropic_max_tokens,
                "temperature": settings.anthropic_temperature
            },
            AIProvider.GEMINI: {
                "model": settings.gemini_model,
                "max_tokens": settings.gemini_max_tokens,
                "temperature": settings.gemini_temperature
            }
        }
    
    async def initialize(self):
        """Initialize all configured providers"""
        self.logger.info("Initializing AI providers")
        
        # Initialize OpenAI
        if self.settings.has_openai_config and AIProvider.OPENAI in self.settings.enabled_providers:
            try:
                client = openai.AsyncOpenAI(
                    api_key=self.settings.openai_api_key,
                    base_url=self.settings.openai_base_url
                )
                self.providers[AIProvider.OPENAI] = client
                self.available_providers.append(AIProvider.OPENAI)
                self.logger.info("OpenAI provider initialized")
            except Exception as e:
                self.logger.error("Failed to initialize OpenAI provider", error=str(e))
        
        # Initialize Azure OpenAI
        if self.settings.has_azure_openai_config and AIProvider.AZURE_OPENAI in self.settings.enabled_providers:
            try:
                client = openai.AsyncOpenAI(
                    api_key=self.settings.azure_openai_api_key,
                    azure_endpoint=self.settings.azure_openai_endpoint,
                    api_version=self.settings.azure_openai_api_version
                )
                self.providers[AIProvider.AZURE_OPENAI] = client
                self.available_providers.append(AIProvider.AZURE_OPENAI)
                self.logger.info("Azure OpenAI provider initialized")
            except Exception as e:
                self.logger.error("Failed to initialize Azure OpenAI provider", error=str(e))
        
        # Initialize Anthropic Claude
        if self.settings.has_anthropic_config and AIProvider.CLAUDE in self.settings.enabled_providers:
            try:
                client = anthropic.AsyncAnthropic(api_key=self.settings.anthropic_api_key)
                self.providers[AIProvider.CLAUDE] = client
                self.available_providers.append(AIProvider.CLAUDE)
                self.logger.info("Anthropic Claude provider initialized")
            except Exception as e:
                self.logger.error("Failed to initialize Anthropic provider", error=str(e))
        
        # Initialize Google Gemini
        if self.settings.has_gemini_config and AIProvider.GEMINI in self.settings.enabled_providers:
            try:
                genai.configure(api_key=self.settings.gemini_api_key)
                model = genai.GenerativeModel(self.settings.gemini_model)
                self.providers[AIProvider.GEMINI] = model
                self.available_providers.append(AIProvider.GEMINI)
                self.logger.info("Google Gemini provider initialized")
            except Exception as e:
                self.logger.error("Failed to initialize Gemini provider", error=str(e))
        
        if not self.available_providers:
            raise RuntimeError("No AI providers were successfully initialized")
        
        self.logger.info("Provider initialization complete", 
                        available_providers=[p.value for p in self.available_providers])
    
    async def cleanup(self):
        """Cleanup provider connections"""
        for provider, client in self.providers.items():
            if hasattr(client, 'close'):
                try:
                    await client.close()
                except Exception as e:
                    self.logger.warning(f"Error closing {provider.value} client", error=str(e))
        
        self.providers.clear()
        self.available_providers.clear()
        self.logger.info("Provider cleanup complete")
    
    def get_available_providers(self) -> List[AIProvider]:
        """Get list of available providers"""
        return self.available_providers.copy()
    
    def is_provider_available(self, provider: AIProvider) -> bool:
        """Check if provider is available"""
        return provider in self.available_providers
    
    def get_default_provider(self) -> AIProvider:
        """Get default provider, falling back to first available"""
        if self.settings.default_provider in self.available_providers:
            return self.settings.default_provider
        return self.available_providers[0] if self.available_providers else None
    
    async def generate_code(self, request: GenerationRequest) -> GenerationResult:
        """Generate code using specified provider"""
        if not self.is_provider_available(request.provider):
            raise ValueError(f"Provider {request.provider.value} is not available")
        
        correlation_id = request.correlation_id or get_correlation_id()
        start_time = time.time()
        
        try:
            if request.provider == AIProvider.OPENAI:
                result = await self._generate_openai(request, correlation_id)
            elif request.provider == AIProvider.AZURE_OPENAI:
                result = await self._generate_azure_openai(request, correlation_id)
            elif request.provider == AIProvider.CLAUDE:
                result = await self._generate_claude(request, correlation_id)
            elif request.provider == AIProvider.GEMINI:
                result = await self._generate_gemini(request, correlation_id)
            else:
                raise ValueError(f"Unsupported provider: {request.provider.value}")
            
            duration = time.time() - start_time
            result.duration_seconds = duration
            result.correlation_id = correlation_id
            
            self.logger.info("Code generation completed",
                            provider=request.provider.value,
                            duration_seconds=duration,
                            correlation_id=correlation_id)
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error("Code generation failed",
                             provider=request.provider.value,
                             error=str(e),
                             duration_seconds=duration,
                             correlation_id=correlation_id)
            
            return GenerationResult(
                content="",
                provider=request.provider,
                model=self.provider_configs[request.provider]["model"],
                duration_seconds=duration,
                correlation_id=correlation_id,
                error=str(e)
            )
    
    async def stream_code_generation(self, request: GenerationRequest) -> AsyncGenerator[str, None]:
        """Stream code generation from specified provider"""
        if not self.is_provider_available(request.provider):
            raise ValueError(f"Provider {request.provider.value} is not available")
        
        correlation_id = request.correlation_id or get_correlation_id()
        
        try:
            if request.provider == AIProvider.OPENAI:
                async for chunk in self._stream_openai(request, correlation_id):
                    yield chunk
            elif request.provider == AIProvider.AZURE_OPENAI:
                async for chunk in self._stream_azure_openai(request, correlation_id):
                    yield chunk
            elif request.provider == AIProvider.CLAUDE:
                async for chunk in self._stream_claude(request, correlation_id):
                    yield chunk
            elif request.provider == AIProvider.GEMINI:
                async for chunk in self._stream_gemini(request, correlation_id):
                    yield chunk
            else:
                raise ValueError(f"Streaming not supported for provider: {request.provider.value}")
                
        except Exception as e:
            self.logger.error("Streaming generation failed",
                             provider=request.provider.value,
                             error=str(e),
                             correlation_id=correlation_id)
            raise
    
    async def _generate_openai(self, request: GenerationRequest, correlation_id: str) -> GenerationResult:
        """Generate code using OpenAI"""
        client = self.providers[AIProvider.OPENAI]
        config = self.provider_configs[AIProvider.OPENAI]
        
        response = await client.chat.completions.create(
            model=config["model"],
            messages=request.prompt_messages,
            max_tokens=request.max_tokens or config["max_tokens"],
            temperature=request.temperature or config["temperature"],
            stream=False
        )
        
        return GenerationResult(
            content=response.choices[0].message.content,
            provider=AIProvider.OPENAI,
            model=config["model"],
            duration_seconds=0,  # Will be set by caller
            token_usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        )
    
    async def _stream_openai(self, request: GenerationRequest, correlation_id: str) -> AsyncGenerator[str, None]:
        """Stream code generation from OpenAI"""
        client = self.providers[AIProvider.OPENAI]
        config = self.provider_configs[AIProvider.OPENAI]
        
        response = await client.chat.completions.create(
            model=config["model"],
            messages=request.prompt_messages,
            max_tokens=request.max_tokens or config["max_tokens"],
            temperature=request.temperature or config["temperature"],
            stream=True
        )
        
        async for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    async def _generate_azure_openai(self, request: GenerationRequest, correlation_id: str) -> GenerationResult:
        """Generate code using Azure OpenAI"""
        client = self.providers[AIProvider.AZURE_OPENAI]
        config = self.provider_configs[AIProvider.AZURE_OPENAI]
        
        response = await client.chat.completions.create(
            model=self.settings.azure_openai_deployment_name,  # Use deployment name for Azure
            messages=request.prompt_messages,
            max_tokens=request.max_tokens or config["max_tokens"],
            temperature=request.temperature or config["temperature"],
            stream=False
        )
        
        return GenerationResult(
            content=response.choices[0].message.content,
            provider=AIProvider.AZURE_OPENAI,
            model=config["model"],
            duration_seconds=0,
            token_usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        )
    
    async def _stream_azure_openai(self, request: GenerationRequest, correlation_id: str) -> AsyncGenerator[str, None]:
        """Stream code generation from Azure OpenAI"""
        client = self.providers[AIProvider.AZURE_OPENAI]
        config = self.provider_configs[AIProvider.AZURE_OPENAI]
        
        response = await client.chat.completions.create(
            model=self.settings.azure_openai_deployment_name,
            messages=request.prompt_messages,
            max_tokens=request.max_tokens or config["max_tokens"],
            temperature=request.temperature or config["temperature"],
            stream=True
        )
        
        async for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    async def _generate_claude(self, request: GenerationRequest, correlation_id: str) -> GenerationResult:
        """Generate code using Anthropic Claude"""
        client = self.providers[AIProvider.CLAUDE]
        config = self.provider_configs[AIProvider.CLAUDE]
        
        # Convert OpenAI format to Claude format
        claude_messages = self._convert_to_claude_format(request.prompt_messages)
        
        response = await client.messages.create(
            model=config["model"],
            messages=claude_messages["messages"],
            system=claude_messages.get("system", ""),
            max_tokens=request.max_tokens or config["max_tokens"],
            temperature=request.temperature or config["temperature"]
        )
        
        return GenerationResult(
            content=response.content[0].text,
            provider=AIProvider.CLAUDE,
            model=config["model"],
            duration_seconds=0,
            token_usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
            }
        )
    
    async def _stream_claude(self, request: GenerationRequest, correlation_id: str) -> AsyncGenerator[str, None]:
        """Stream code generation from Claude"""
        client = self.providers[AIProvider.CLAUDE]
        config = self.provider_configs[AIProvider.CLAUDE]
        
        claude_messages = self._convert_to_claude_format(request.prompt_messages)
        
        response = await client.messages.create(
            model=config["model"],
            messages=claude_messages["messages"],
            system=claude_messages.get("system", ""),
            max_tokens=request.max_tokens or config["max_tokens"],
            temperature=request.temperature or config["temperature"],
            stream=True
        )
        
        async for chunk in response:
            if chunk.type == "content_block_delta" and chunk.delta.type == "text_delta":
                yield chunk.delta.text
    
    async def _generate_gemini(self, request: GenerationRequest, correlation_id: str) -> GenerationResult:
        """Generate code using Google Gemini"""
        model = self.providers[AIProvider.GEMINI]
        config = self.provider_configs[AIProvider.GEMINI]
        
        # Convert OpenAI format to Gemini format
        gemini_contents = self._convert_to_gemini_format(request.prompt_messages)
        
        response = await model.generate_content_async(
            contents=gemini_contents,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=request.max_tokens or config["max_tokens"],
                temperature=request.temperature or config["temperature"]
            )
        )
        
        return GenerationResult(
            content=response.text,
            provider=AIProvider.GEMINI,
            model=config["model"],
            duration_seconds=0,
            token_usage={
                "prompt_tokens": response.usage_metadata.prompt_token_count,
                "completion_tokens": response.usage_metadata.candidates_token_count,
                "total_tokens": response.usage_metadata.total_token_count
            } if response.usage_metadata else None
        )
    
    async def _stream_gemini(self, request: GenerationRequest, correlation_id: str) -> AsyncGenerator[str, None]:
        """Stream code generation from Gemini"""
        model = self.providers[AIProvider.GEMINI]
        config = self.provider_configs[AIProvider.GEMINI]
        
        gemini_contents = self._convert_to_gemini_format(request.prompt_messages)
        
        response = await model.generate_content_async(
            contents=gemini_contents,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=request.max_tokens or config["max_tokens"],
                temperature=request.temperature or config["temperature"]
            ),
            stream=True
        )
        
        async for chunk in response:
            if chunk.text:
                yield chunk.text
    
    def _convert_to_claude_format(self, messages: List[ChatCompletionMessageParam]) -> Dict[str, Any]:
        """Convert OpenAI messages to Claude format"""
        system_message = ""
        claude_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            elif msg["role"] in ["user", "assistant"]:
                # Handle both text and image content
                if isinstance(msg["content"], list):
                    # Multi-modal message
                    claude_content = []
                    for part in msg["content"]:
                        if part["type"] == "text":
                            claude_content.append({"type": "text", "text": part["text"]})
                        elif part["type"] == "image_url":
                            # Convert image URL to Claude format
                            image_data = part["image_url"]["url"]
                            if image_data.startswith("data:image/"):
                                media_type, base64_data = image_data.split(",", 1)
                                image_format = media_type.split(";")[0].split("/")[1]
                                claude_content.append({
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": f"image/{image_format}",
                                        "data": base64_data
                                    }
                                })
                    claude_messages.append({"role": msg["role"], "content": claude_content})
                else:
                    # Text-only message
                    claude_messages.append({"role": msg["role"], "content": msg["content"]})
        
        return {"system": system_message, "messages": claude_messages}
    
    def _convert_to_gemini_format(self, messages: List[ChatCompletionMessageParam]) -> List[Dict[str, Any]]:
        """Convert OpenAI messages to Gemini format"""
        gemini_contents = []
        
        for msg in messages:
            if msg["role"] == "system":
                # Gemini doesn't have system role, prepend to first user message
                continue
            elif msg["role"] == "user":
                role = "user"
            elif msg["role"] == "assistant":
                role = "model"
            else:
                continue
            
            if isinstance(msg["content"], list):
                # Multi-modal message
                parts = []
                for part in msg["content"]:
                    if part["type"] == "text":
                        parts.append({"text": part["text"]})
                    elif part["type"] == "image_url":
                        # Gemini expects image data differently
                        image_data = part["image_url"]["url"]
                        if image_data.startswith("data:image/"):
                            media_type, base64_data = image_data.split(",", 1)
                            import base64
                            image_bytes = base64.b64decode(base64_data)
                            parts.append({
                                "inline_data": {
                                    "mime_type": media_type.split(";")[0],
                                    "data": base64_data
                                }
                            })
                gemini_contents.append({"role": role, "parts": parts})
            else:
                # Text-only message
                gemini_contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        
        return gemini_contents