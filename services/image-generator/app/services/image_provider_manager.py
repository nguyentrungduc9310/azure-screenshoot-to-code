"""
Image Provider Manager for handling DALL-E 3 and Flux Schnell
Manages image generation using multiple AI providers
"""
import asyncio
import time
import httpx
import base64
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import openai
from app.core.config import Settings, ImageProvider, ImageSize

from shared.monitoring.structured_logger import StructuredLogger
from shared.monitoring.correlation import get_correlation_id

class GenerationStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class ImageGenerationRequest:
    """Request for image generation"""
    prompt: str
    provider: ImageProvider
    size: ImageSize
    quality: Optional[str] = None
    style: Optional[str] = None
    num_images: int = 1
    seed: Optional[int] = None
    correlation_id: Optional[str] = None

@dataclass
class GeneratedImage:
    """Generated image result"""
    url: Optional[str] = None
    base64_data: Optional[str] = None
    revised_prompt: Optional[str] = None
    size: Optional[str] = None
    provider: Optional[str] = None

@dataclass
class ImageGenerationResult:
    """Result from image generation"""
    images: List[GeneratedImage]
    provider: ImageProvider
    model: str
    duration_seconds: float
    prompt: str
    revised_prompt: Optional[str] = None
    correlation_id: Optional[str] = None
    error: Optional[str] = None
    status: GenerationStatus = GenerationStatus.COMPLETED

class ImageProviderManager:
    """Manages multiple image providers for image generation"""
    
    def __init__(self, settings: Settings, logger: StructuredLogger):
        self.settings = settings
        self.logger = logger
        self.providers: Dict[ImageProvider, Any] = {}
        self.available_providers: List[ImageProvider] = []
        self.http_client = httpx.AsyncClient(timeout=settings.request_timeout_seconds)
        
        # Provider configurations
        self.provider_configs = {
            ImageProvider.DALLE3: {
                "model": settings.dalle3_model,
                "default_size": settings.dalle3_default_size,
                "default_quality": settings.dalle3_default_quality,
                "default_style": settings.dalle3_default_style
            },
            ImageProvider.FLUX_SCHNELL: {
                "model": settings.flux_model,
                "default_size": settings.flux_default_size,
                "base_url": settings.flux_base_url,
                "seed": settings.flux_seed
            }
        }
    
    async def initialize(self):
        """Initialize all configured providers"""
        self.logger.info("Initializing image providers")
        
        # Initialize DALL-E 3 (OpenAI)
        if self.settings.has_openai_config and ImageProvider.DALLE3 in self.settings.enabled_providers:
            try:
                client = openai.AsyncOpenAI(
                    api_key=self.settings.openai_api_key,
                    base_url=self.settings.openai_base_url
                )
                self.providers[ImageProvider.DALLE3] = client
                self.available_providers.append(ImageProvider.DALLE3)
                self.logger.info("DALL-E 3 (OpenAI) provider initialized")
            except Exception as e:
                self.logger.error("Failed to initialize DALL-E 3 (OpenAI) provider", error=str(e))
        
        # Initialize DALL-E 3 (Azure OpenAI)
        if self.settings.has_azure_openai_config and ImageProvider.DALLE3 in self.settings.enabled_providers:
            try:
                client = openai.AsyncOpenAI(
                    api_key=self.settings.azure_openai_api_key,
                    azure_endpoint=self.settings.azure_openai_endpoint,
                    api_version=self.settings.azure_openai_api_version
                )
                # If OpenAI is not already configured, use Azure OpenAI for DALL-E 3
                if ImageProvider.DALLE3 not in self.providers:
                    self.providers[ImageProvider.DALLE3] = client
                    self.available_providers.append(ImageProvider.DALLE3)
                    self.logger.info("DALL-E 3 (Azure OpenAI) provider initialized")
            except Exception as e:
                self.logger.error("Failed to initialize DALL-E 3 (Azure OpenAI) provider", error=str(e))
        
        # Initialize Flux Schnell
        if self.settings.has_flux_config and ImageProvider.FLUX_SCHNELL in self.settings.enabled_providers:
            try:
                # Flux Schnell uses HTTP API, so we just store the configuration
                self.providers[ImageProvider.FLUX_SCHNELL] = {
                    "api_key": self.settings.flux_api_key,
                    "base_url": self.settings.flux_base_url,
                    "model": self.settings.flux_model
                }
                self.available_providers.append(ImageProvider.FLUX_SCHNELL)
                self.logger.info("Flux Schnell provider initialized")
            except Exception as e:
                self.logger.error("Failed to initialize Flux Schnell provider", error=str(e))
        
        if not self.available_providers:
            raise RuntimeError("No image providers were successfully initialized")
        
        self.logger.info("Provider initialization complete", 
                        available_providers=[p.value for p in self.available_providers])
    
    async def cleanup(self):
        """Cleanup provider connections"""
        if hasattr(self, 'http_client'):
            await self.http_client.aclose()
        
        for provider, client in self.providers.items():
            if hasattr(client, 'close'):
                try:
                    await client.close()
                except Exception as e:
                    self.logger.warning(f"Error closing {provider.value} client", error=str(e))
        
        self.providers.clear()
        self.available_providers.clear()
        self.logger.info("Provider cleanup complete")
    
    def get_available_providers(self) -> List[ImageProvider]:
        """Get list of available providers"""
        return self.available_providers.copy()
    
    def is_provider_available(self, provider: ImageProvider) -> bool:
        """Check if provider is available"""
        return provider in self.available_providers
    
    def get_default_provider(self) -> ImageProvider:
        """Get default provider, falling back to first available"""
        if self.settings.default_provider in self.available_providers:
            return self.settings.default_provider
        return self.available_providers[0] if self.available_providers else None
    
    async def generate_images(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """Generate images using specified provider"""
        if not self.is_provider_available(request.provider):
            raise ValueError(f"Provider {request.provider.value} is not available")
        
        correlation_id = request.correlation_id or get_correlation_id()
        start_time = time.time()
        
        try:
            if request.provider == ImageProvider.DALLE3:
                result = await self._generate_dalle3(request, correlation_id)
            elif request.provider == ImageProvider.FLUX_SCHNELL:
                result = await self._generate_flux_schnell(request, correlation_id)
            else:
                raise ValueError(f"Unsupported provider: {request.provider.value}")
            
            duration = time.time() - start_time
            result.duration_seconds = duration
            result.correlation_id = correlation_id
            
            self.logger.info("Image generation completed",
                            provider=request.provider.value,
                            num_images=len(result.images),
                            duration_seconds=duration,
                            correlation_id=correlation_id)
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error("Image generation failed",
                             provider=request.provider.value,
                             error=str(e),
                             duration_seconds=duration,
                             correlation_id=correlation_id)
            
            return ImageGenerationResult(
                images=[],
                provider=request.provider,
                model=self.provider_configs[request.provider].get("model", "unknown"),
                duration_seconds=duration,
                prompt=request.prompt,
                correlation_id=correlation_id,
                error=str(e),
                status=GenerationStatus.FAILED
            )
    
    async def _generate_dalle3(self, request: ImageGenerationRequest, correlation_id: str) -> ImageGenerationResult:
        """Generate images using DALL-E 3"""
        client = self.providers[ImageProvider.DALLE3]
        config = self.provider_configs[ImageProvider.DALLE3]
        
        # Prepare parameters
        dalle3_params = {
            "model": config["model"],
            "prompt": request.prompt,
            "size": request.size.value,
            "n": min(request.num_images, 1),  # DALL-E 3 only supports 1 image at a time
            "response_format": "url"  # Can be "url" or "b64_json"
        }
        
        # Add optional parameters
        if request.quality:
            dalle3_params["quality"] = request.quality
        if request.style:
            dalle3_params["style"] = request.style
        
        # Use Azure OpenAI deployment name if configured
        if self.settings.has_azure_openai_config:
            dalle3_params["model"] = self.settings.azure_openai_deployment_name
        
        response = await client.images.generate(**dalle3_params)
        
        images = []
        for image_data in response.data:
            images.append(GeneratedImage(
                url=image_data.url,
                revised_prompt=image_data.revised_prompt,
                size=request.size.value,
                provider=ImageProvider.DALLE3.value
            ))
        
        return ImageGenerationResult(
            images=images,
            provider=ImageProvider.DALLE3,
            model=config["model"],
            duration_seconds=0,  # Will be set by caller
            prompt=request.prompt,
            revised_prompt=response.data[0].revised_prompt if response.data else None
        )
    
    async def _generate_flux_schnell(self, request: ImageGenerationRequest, correlation_id: str) -> ImageGenerationResult:
        """Generate images using Flux Schnell"""
        config = self.providers[ImageProvider.FLUX_SCHNELL]
        
        # Parse size for Flux Schnell
        width, height = map(int, request.size.value.split('x'))
        
        # Prepare request payload
        flux_payload = {
            "prompt": request.prompt,
            "width": width,
            "height": height,
            "num_inference_steps": 4,  # Flux Schnell is optimized for 4 steps
            "guidance_scale": 1.0,     # Flux Schnell works best with guidance_scale = 1.0
            "num_images": min(request.num_images, 4),  # Flux Schnell supports up to 4 images
        }
        
        # Add seed if provided
        if request.seed is not None:
            flux_payload["seed"] = request.seed
        elif self.settings.flux_seed is not None:
            flux_payload["seed"] = self.settings.flux_seed
        
        # Make API request to Flux Schnell
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
            "User-Agent": "Screenshot-to-Code/1.0"
        }
        
        endpoint = f"{config['base_url']}/v1/flux-schnell"
        
        response = await self.http_client.post(
            endpoint,
            json=flux_payload,
            headers=headers
        )
        
        if response.status_code != 200:
            error_detail = response.text
            try:
                error_json = response.json()
                error_detail = error_json.get("error", {}).get("message", error_detail)
            except:
                pass
            raise Exception(f"Flux Schnell API error: {error_detail}")
        
        result_data = response.json()
        
        images = []
        # Flux Schnell returns base64 encoded images
        if "images" in result_data:
            for i, image_b64 in enumerate(result_data["images"]):
                images.append(GeneratedImage(
                    base64_data=image_b64,
                    size=request.size.value,
                    provider=ImageProvider.FLUX_SCHNELL.value
                ))
        
        return ImageGenerationResult(
            images=images,
            provider=ImageProvider.FLUX_SCHNELL,
            model=config["model"],
            duration_seconds=0,  # Will be set by caller
            prompt=request.prompt
        )
    
    def validate_request(self, request: ImageGenerationRequest) -> List[str]:
        """Validate image generation request"""
        issues = []
        
        # Check provider availability
        if not self.is_provider_available(request.provider):
            issues.append(f"Provider {request.provider.value} is not available")
        
        # Check prompt length
        if len(request.prompt.strip()) == 0:
            issues.append("Prompt cannot be empty")
        
        if len(request.prompt) > self.settings.max_prompt_length:
            issues.append(f"Prompt exceeds maximum length of {self.settings.max_prompt_length} characters")
        
        # Check number of images
        if request.num_images < 1 or request.num_images > self.settings.max_images_per_request:
            issues.append(f"Number of images must be between 1 and {self.settings.max_images_per_request}")
        
        # Provider-specific validation
        if request.provider == ImageProvider.DALLE3:
            if request.num_images > 1:
                issues.append("DALL-E 3 only supports generating 1 image at a time")
            
            supported_sizes = self.settings.get_supported_sizes(ImageProvider.DALLE3)
            if request.size not in supported_sizes:
                issues.append(f"Size {request.size.value} is not supported by DALL-E 3")
        
        elif request.provider == ImageProvider.FLUX_SCHNELL:
            if request.num_images > 4:
                issues.append("Flux Schnell supports maximum 4 images per request")
            
            supported_sizes = self.settings.get_supported_sizes(ImageProvider.FLUX_SCHNELL)
            if request.size not in supported_sizes:
                issues.append(f"Size {request.size.value} is not supported by Flux Schnell")
        
        # Content moderation (basic keyword check)
        if self.settings.enable_content_moderation:
            prompt_lower = request.prompt.lower()
            for blocked_word in self.settings.blocked_words:
                if blocked_word in prompt_lower:
                    issues.append(f"Prompt contains blocked content")
                    break
        
        return issues
    
    def get_provider_info(self, provider: ImageProvider) -> Dict[str, Any]:
        """Get information about a provider"""
        if provider == ImageProvider.DALLE3:
            return {
                "id": provider.value,
                "name": "DALL-E 3",
                "description": "OpenAI's advanced image generation model",
                "supported_sizes": [size.value for size in self.settings.get_supported_sizes(provider)],
                "max_images": 1,
                "supports_quality": True,
                "supports_style": True,
                "typical_generation_time": "10-30 seconds"
            }
        elif provider == ImageProvider.FLUX_SCHNELL:
            return {
                "id": provider.value,
                "name": "Flux Schnell",
                "description": "Fast image generation model optimized for speed",
                "supported_sizes": [size.value for size in self.settings.get_supported_sizes(provider)],
                "max_images": 4,
                "supports_quality": False,
                "supports_style": False,
                "supports_seed": True,
                "typical_generation_time": "2-8 seconds"
            }
        return {}