"""
Configuration settings for Image Generator service
"""
import os
from typing import List, Optional
from pydantic import BaseSettings, Field, validator
from enum import Enum

class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

class ImageProvider(str, Enum):
    DALLE3 = "dalle3"
    FLUX_SCHNELL = "flux_schnell"

class ImageSize(str, Enum):
    # DALL-E 3 sizes
    DALLE3_1024x1024 = "1024x1024"
    DALLE3_1792x1024 = "1792x1024"
    DALLE3_1024x1792 = "1024x1792"
    
    # Flux Schnell sizes (standard sizes)
    FLUX_512x512 = "512x512"
    FLUX_768x768 = "768x768"
    FLUX_1024x1024 = "1024x1024"
    FLUX_1536x1024 = "1536x1024"
    FLUX_1024x1536 = "1024x1536"

class ImageQuality(str, Enum):
    STANDARD = "standard"
    HD = "hd"

class ImageStyle(str, Enum):
    VIVID = "vivid"
    NATURAL = "natural"

class Settings(BaseSettings):
    """Application settings"""
    
    # Service configuration
    service_name: str = Field(default="image-generator", env="SERVICE_NAME")
    environment: Environment = Field(default=Environment.DEVELOPMENT, env="ENVIRONMENT")
    log_level: LogLevel = Field(default=LogLevel.INFO, env="LOG_LEVEL")
    
    # API configuration
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8003, env="API_PORT")
    
    # Security
    enable_authentication: bool = Field(default=True, env="ENABLE_AUTHENTICATION")
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        env="ALLOWED_ORIGINS"
    )
    
    # Azure AD Configuration
    azure_tenant_id: Optional[str] = Field(default=None, env="AZURE_TENANT_ID")
    azure_client_id: Optional[str] = Field(default=None, env="AZURE_CLIENT_ID")
    
    # Image Provider Configuration
    enabled_providers: List[ImageProvider] = Field(
        default=[ImageProvider.DALLE3, ImageProvider.FLUX_SCHNELL],
        env="ENABLED_PROVIDERS"
    )
    default_provider: ImageProvider = Field(default=ImageProvider.DALLE3, env="DEFAULT_PROVIDER")
    
    # DALL-E 3 Configuration
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    openai_base_url: Optional[str] = Field(default=None, env="OPENAI_BASE_URL")
    dalle3_model: str = Field(default="dall-e-3", env="DALLE3_MODEL")
    dalle3_default_size: ImageSize = Field(default=ImageSize.DALLE3_1024x1024, env="DALLE3_DEFAULT_SIZE")
    dalle3_default_quality: ImageQuality = Field(default=ImageQuality.STANDARD, env="DALLE3_DEFAULT_QUALITY")
    dalle3_default_style: ImageStyle = Field(default=ImageStyle.VIVID, env="DALLE3_DEFAULT_STYLE")
    
    # Azure OpenAI Configuration (for DALL-E 3)
    azure_openai_api_key: Optional[str] = Field(default=None, env="AZURE_OPENAI_API_KEY")
    azure_openai_endpoint: Optional[str] = Field(default=None, env="AZURE_OPENAI_ENDPOINT")
    azure_openai_deployment_name: Optional[str] = Field(default=None, env="AZURE_OPENAI_DEPLOYMENT_NAME")
    azure_openai_api_version: str = Field(default="2024-10-21", env="AZURE_OPENAI_API_VERSION")
    
    # Flux Schnell Configuration
    flux_api_key: Optional[str] = Field(default=None, env="FLUX_API_KEY")
    flux_base_url: str = Field(default="https://api.bfl.ml", env="FLUX_BASE_URL")
    flux_model: str = Field(default="flux-schnell", env="FLUX_MODEL")
    flux_default_size: ImageSize = Field(default=ImageSize.FLUX_1024x1024, env="FLUX_DEFAULT_SIZE")
    flux_seed: Optional[int] = Field(default=None, env="FLUX_SEED")
    
    # Image Generation Configuration
    max_images_per_request: int = Field(default=4, env="MAX_IMAGES_PER_REQUEST")
    default_images_count: int = Field(default=1, env="DEFAULT_IMAGES_COUNT")
    enable_prompt_enhancement: bool = Field(default=True, env="ENABLE_PROMPT_ENHANCEMENT")
    max_prompt_length: int = Field(default=4000, env="MAX_PROMPT_LENGTH")
    
    # Performance Configuration
    request_timeout_seconds: int = Field(default=300, env="REQUEST_TIMEOUT_SECONDS")  # 5 minutes for image generation
    max_concurrent_requests: int = Field(default=5, env="MAX_CONCURRENT_REQUESTS")
    retry_attempts: int = Field(default=3, env="RETRY_ATTEMPTS")
    retry_delay_seconds: float = Field(default=2.0, env="RETRY_DELAY_SECONDS")
    
    # Image Storage Configuration
    enable_image_storage: bool = Field(default=True, env="ENABLE_IMAGE_STORAGE")
    storage_backend: str = Field(default="local", env="STORAGE_BACKEND")  # local, azure_blob, s3
    local_storage_path: str = Field(default="./generated_images", env="LOCAL_STORAGE_PATH")
    
    # Azure Blob Storage Configuration
    azure_storage_connection_string: Optional[str] = Field(default=None, env="AZURE_STORAGE_CONNECTION_STRING")
    azure_storage_container: str = Field(default="generated-images", env="AZURE_STORAGE_CONTAINER")
    
    # AWS S3 Configuration
    aws_access_key_id: Optional[str] = Field(default=None, env="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = Field(default=None, env="AWS_SECRET_ACCESS_KEY")
    aws_region: str = Field(default="us-east-1", env="AWS_REGION")
    aws_s3_bucket: str = Field(default="screenshot-to-code-images", env="AWS_S3_BUCKET")
    
    # Content Moderation
    enable_content_moderation: bool = Field(default=True, env="ENABLE_CONTENT_MODERATION")
    blocked_words: List[str] = Field(default=[], env="BLOCKED_WORDS")
    
    # Monitoring
    applicationinsights_connection_string: Optional[str] = Field(
        default=None, 
        env="APPLICATIONINSIGHTS_CONNECTION_STRING"
    )
    enable_detailed_logging: bool = Field(default=True, env="ENABLE_DETAILED_LOGGING")
    
    # Development/Testing
    mock_image_generation: bool = Field(default=False, env="MOCK_IMAGE_GENERATION")
    enable_debug_mode: bool = Field(default=False, env="ENABLE_DEBUG_MODE")
    
    @validator("allowed_origins", pre=True)
    def parse_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("enabled_providers", pre=True)
    def parse_providers(cls, v):
        if isinstance(v, str):
            return [ImageProvider(provider.strip()) for provider in v.split(",")]
        return v
    
    @validator("blocked_words", pre=True)
    def parse_blocked_words(cls, v):
        if isinstance(v, str):
            return [word.strip().lower() for word in v.split(",")]
        return v
    
    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION
    
    @property
    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT
    
    @property
    def has_openai_config(self) -> bool:
        return bool(self.openai_api_key)
    
    @property
    def has_azure_openai_config(self) -> bool:
        return bool(
            self.azure_openai_api_key and 
            self.azure_openai_endpoint and 
            self.azure_openai_deployment_name
        )
    
    @property
    def has_flux_config(self) -> bool:
        return bool(self.flux_api_key)
    
    @property
    def has_azure_storage_config(self) -> bool:
        return bool(self.azure_storage_connection_string)
    
    @property
    def has_s3_config(self) -> bool:
        return bool(self.aws_access_key_id and self.aws_secret_access_key)
    
    def get_available_providers(self) -> List[ImageProvider]:
        """Get list of providers that have valid configuration"""
        available = []
        
        if (self.has_openai_config or self.has_azure_openai_config) and ImageProvider.DALLE3 in self.enabled_providers:
            available.append(ImageProvider.DALLE3)
        
        if self.has_flux_config and ImageProvider.FLUX_SCHNELL in self.enabled_providers:
            available.append(ImageProvider.FLUX_SCHNELL)
        
        return available
    
    def get_supported_sizes(self, provider: ImageProvider) -> List[ImageSize]:
        """Get supported image sizes for a provider"""
        if provider == ImageProvider.DALLE3:
            return [ImageSize.DALLE3_1024x1024, ImageSize.DALLE3_1792x1024, ImageSize.DALLE3_1024x1792]
        elif provider == ImageProvider.FLUX_SCHNELL:
            return [
                ImageSize.FLUX_512x512,
                ImageSize.FLUX_768x768,
                ImageSize.FLUX_1024x1024,
                ImageSize.FLUX_1536x1024,
                ImageSize.FLUX_1024x1536
            ]
        return []
    
    def validate_configuration(self) -> List[str]:
        """Validate configuration and return list of issues"""
        issues = []
        
        # Check if at least one provider is configured
        available_providers = self.get_available_providers()
        if not available_providers:
            issues.append("No image providers are properly configured")
        
        # Check if default provider is available
        if self.default_provider not in available_providers:
            issues.append(f"Default provider {self.default_provider.value} is not configured")
        
        # Check Azure AD configuration if authentication is enabled
        if self.enable_authentication:
            if not self.azure_tenant_id or not self.azure_client_id:
                issues.append("Azure AD configuration is incomplete for authentication")
        
        # Check storage configuration if enabled
        if self.enable_image_storage:
            if self.storage_backend == "azure_blob" and not self.has_azure_storage_config:
                issues.append("Azure Blob Storage configuration is incomplete")
            elif self.storage_backend == "s3" and not self.has_s3_config:
                issues.append("AWS S3 configuration is incomplete")
        
        return issues
    
    class Config:
        env_file = ".env"
        case_sensitive = False