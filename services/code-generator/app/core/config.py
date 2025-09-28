"""
Configuration settings for Code Generator service
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

class AIProvider(str, Enum):
    CLAUDE = "claude"
    OPENAI = "openai"
    GEMINI = "gemini"
    AZURE_OPENAI = "azure_openai"

class CodeStack(str, Enum):
    HTML_TAILWIND = "html_tailwind"
    HTML_CSS = "html_css"
    REACT_TAILWIND = "react_tailwind"
    VUE_TAILWIND = "vue_tailwind"
    BOOTSTRAP = "bootstrap"
    IONIC_TAILWIND = "ionic_tailwind"
    SVG = "svg"

class Settings(BaseSettings):
    """Application settings"""
    
    # Service configuration
    service_name: str = Field(default="code-generator", env="SERVICE_NAME")
    environment: Environment = Field(default=Environment.DEVELOPMENT, env="ENVIRONMENT")
    log_level: LogLevel = Field(default=LogLevel.INFO, env="LOG_LEVEL")
    
    # API configuration
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8002, env="API_PORT")
    
    # Security
    enable_authentication: bool = Field(default=True, env="ENABLE_AUTHENTICATION")
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        env="ALLOWED_ORIGINS"
    )
    
    # Azure AD Configuration
    azure_tenant_id: Optional[str] = Field(default=None, env="AZURE_TENANT_ID")
    azure_client_id: Optional[str] = Field(default=None, env="AZURE_CLIENT_ID")
    
    # AI Provider Configuration
    enabled_providers: List[AIProvider] = Field(
        default=[AIProvider.CLAUDE, AIProvider.OPENAI, AIProvider.GEMINI],
        env="ENABLED_PROVIDERS"
    )
    default_provider: AIProvider = Field(default=AIProvider.CLAUDE, env="DEFAULT_PROVIDER")
    
    # OpenAI Configuration
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    openai_base_url: Optional[str] = Field(default=None, env="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4o-2024-11-20", env="OPENAI_MODEL")
    openai_max_tokens: int = Field(default=4096, env="OPENAI_MAX_TOKENS")
    openai_temperature: float = Field(default=0.0, env="OPENAI_TEMPERATURE")
    
    # Azure OpenAI Configuration
    azure_openai_api_key: Optional[str] = Field(default=None, env="AZURE_OPENAI_API_KEY")
    azure_openai_endpoint: Optional[str] = Field(default=None, env="AZURE_OPENAI_ENDPOINT")
    azure_openai_resource_name: Optional[str] = Field(default=None, env="AZURE_OPENAI_RESOURCE_NAME")
    azure_openai_deployment_name: Optional[str] = Field(default=None, env="AZURE_OPENAI_DEPLOYMENT_NAME")
    azure_openai_api_version: str = Field(default="2024-10-21", env="AZURE_OPENAI_API_VERSION")
    
    # Anthropic Configuration
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-3-5-sonnet-20241022", env="ANTHROPIC_MODEL")
    anthropic_max_tokens: int = Field(default=4096, env="ANTHROPIC_MAX_TOKENS")
    anthropic_temperature: float = Field(default=0.0, env="ANTHROPIC_TEMPERATURE")
    
    # Google Gemini Configuration
    gemini_api_key: Optional[str] = Field(default=None, env="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.0-flash-exp", env="GEMINI_MODEL")
    gemini_max_tokens: int = Field(default=4096, env="GEMINI_MAX_TOKENS")
    gemini_temperature: float = Field(default=0.0, env="GEMINI_TEMPERATURE")
    
    # Code Generation Configuration
    supported_stacks: List[CodeStack] = Field(
        default=[
            CodeStack.HTML_TAILWIND,
            CodeStack.HTML_CSS,
            CodeStack.REACT_TAILWIND,
            CodeStack.VUE_TAILWIND,
            CodeStack.BOOTSTRAP,
            CodeStack.IONIC_TAILWIND,
            CodeStack.SVG
        ],
        env="SUPPORTED_STACKS"
    )
    default_stack: CodeStack = Field(default=CodeStack.HTML_TAILWIND, env="DEFAULT_STACK")
    max_variants: int = Field(default=2, env="MAX_VARIANTS")
    enable_caching: bool = Field(default=True, env="ENABLE_CACHING")
    cache_ttl_seconds: int = Field(default=3600, env="CACHE_TTL_SECONDS")
    
    # Performance Configuration
    request_timeout_seconds: int = Field(default=120, env="REQUEST_TIMEOUT_SECONDS")
    max_concurrent_requests: int = Field(default=10, env="MAX_CONCURRENT_REQUESTS")
    retry_attempts: int = Field(default=3, env="RETRY_ATTEMPTS")
    retry_delay_seconds: float = Field(default=1.0, env="RETRY_DELAY_SECONDS")
    
    # Image Processing
    max_image_size_mb: int = Field(default=20, env="MAX_IMAGE_SIZE_MB")
    supported_image_formats: List[str] = Field(
        default=["PNG", "JPEG", "JPG", "WEBP", "GIF"],
        env="SUPPORTED_IMAGE_FORMATS"
    )
    
    # Monitoring
    applicationinsights_connection_string: Optional[str] = Field(
        default=None, 
        env="APPLICATIONINSIGHTS_CONNECTION_STRING"
    )
    enable_detailed_logging: bool = Field(default=True, env="ENABLE_DETAILED_LOGGING")
    
    # Development/Testing
    mock_ai_response: bool = Field(default=False, env="MOCK_AI_RESPONSE")
    enable_debug_mode: bool = Field(default=False, env="ENABLE_DEBUG_MODE")
    
    @validator("allowed_origins", pre=True)
    def parse_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("enabled_providers", pre=True)
    def parse_providers(cls, v):
        if isinstance(v, str):
            return [AIProvider(provider.strip()) for provider in v.split(",")]
        return v
    
    @validator("supported_stacks", pre=True)
    def parse_stacks(cls, v):
        if isinstance(v, str):
            return [CodeStack(stack.strip()) for stack in v.split(",")]
        return v
    
    @validator("supported_image_formats", pre=True)
    def parse_formats(cls, v):
        if isinstance(v, str):
            return [fmt.strip().upper() for fmt in v.split(",")]
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
    def has_anthropic_config(self) -> bool:
        return bool(self.anthropic_api_key)
    
    @property
    def has_gemini_config(self) -> bool:
        return bool(self.gemini_api_key)
    
    def get_available_providers(self) -> List[AIProvider]:
        """Get list of providers that have valid configuration"""
        available = []
        
        if self.has_openai_config and AIProvider.OPENAI in self.enabled_providers:
            available.append(AIProvider.OPENAI)
        
        if self.has_azure_openai_config and AIProvider.AZURE_OPENAI in self.enabled_providers:
            available.append(AIProvider.AZURE_OPENAI)
        
        if self.has_anthropic_config and AIProvider.CLAUDE in self.enabled_providers:
            available.append(AIProvider.CLAUDE)
        
        if self.has_gemini_config and AIProvider.GEMINI in self.enabled_providers:
            available.append(AIProvider.GEMINI)
        
        return available
    
    def validate_configuration(self) -> List[str]:
        """Validate configuration and return list of issues"""
        issues = []
        
        # Check if at least one provider is configured
        available_providers = self.get_available_providers()
        if not available_providers:
            issues.append("No AI providers are properly configured")
        
        # Check if default provider is available
        if self.default_provider not in available_providers:
            issues.append(f"Default provider {self.default_provider.value} is not configured")
        
        # Check Azure AD configuration if authentication is enabled
        if self.enable_authentication:
            if not self.azure_tenant_id or not self.azure_client_id:
                issues.append("Azure AD configuration is incomplete for authentication")
        
        return issues
    
    class Config:
        env_file = ".env"
        case_sensitive = False