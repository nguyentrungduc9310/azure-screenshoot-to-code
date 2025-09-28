"""
Configuration settings for API Gateway service
"""
import os
from typing import List, Optional, Dict, Any
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

class LoadBalancingStrategy(str, Enum):
    ROUND_ROBIN = "round_robin"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LEAST_CONNECTIONS = "least_connections"
    RANDOM = "random"

class Settings(BaseSettings):
    """Application settings"""
    
    # Service configuration
    service_name: str = Field(default="api-gateway", env="SERVICE_NAME")
    environment: Environment = Field(default=Environment.DEVELOPMENT, env="ENVIRONMENT")
    log_level: LogLevel = Field(default=LogLevel.INFO, env="LOG_LEVEL")
    
    # API configuration
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")
    api_prefix: str = Field(default="/api/v1", env="API_PREFIX")
    
    # Security
    enable_authentication: bool = Field(default=True, env="ENABLE_AUTHENTICATION")
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173", "http://localhost:8000"],
        env="ALLOWED_ORIGINS"
    )
    
    # Azure AD Configuration
    azure_tenant_id: Optional[str] = Field(default=None, env="AZURE_TENANT_ID")
    azure_client_id: Optional[str] = Field(default=None, env="AZURE_CLIENT_ID")
    
    # JWT Configuration
    jwt_secret: str = Field(default="your-super-secret-jwt-key", env="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=1440, env="JWT_EXPIRE_MINUTES")  # 24 hours
    
    # Service Discovery - Downstream Services
    code_generator_service_url: str = Field(default="http://localhost:8002", env="CODE_GENERATOR_SERVICE_URL")
    image_generator_service_url: str = Field(default="http://localhost:8003", env="IMAGE_GENERATOR_SERVICE_URL")
    
    # Load Balancing
    load_balancing_strategy: LoadBalancingStrategy = Field(
        default=LoadBalancingStrategy.ROUND_ROBIN, 
        env="LOAD_BALANCING_STRATEGY"
    )
    
    # Circuit Breaker Configuration
    circuit_breaker_enabled: bool = Field(default=True, env="CIRCUIT_BREAKER_ENABLED")
    circuit_breaker_failure_threshold: int = Field(default=5, env="CIRCUIT_BREAKER_FAILURE_THRESHOLD")
    circuit_breaker_timeout_seconds: int = Field(default=60, env="CIRCUIT_BREAKER_TIMEOUT_SECONDS")
    circuit_breaker_retry_timeout: int = Field(default=30, env="CIRCUIT_BREAKER_RETRY_TIMEOUT")
    
    # Rate Limiting
    enable_rate_limiting: bool = Field(default=True, env="ENABLE_RATE_LIMITING")
    rate_limit_requests: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    rate_limit_window_seconds: int = Field(default=60, env="RATE_LIMIT_WINDOW_SECONDS")
    
    # Request/Response Configuration
    request_timeout_seconds: int = Field(default=120, env="REQUEST_TIMEOUT_SECONDS")
    max_request_size: int = Field(default=100 * 1024 * 1024, env="MAX_REQUEST_SIZE")  # 100MB
    enable_request_logging: bool = Field(default=True, env="ENABLE_REQUEST_LOGGING")
    enable_response_compression: bool = Field(default=True, env="ENABLE_RESPONSE_COMPRESSION")
    
    # Retry Configuration
    enable_retries: bool = Field(default=True, env="ENABLE_RETRIES")
    max_retries: int = Field(default=3, env="MAX_RETRIES")
    retry_delay_seconds: float = Field(default=1.0, env="RETRY_DELAY_SECONDS")
    retry_backoff_multiplier: float = Field(default=2.0, env="RETRY_BACKOFF_MULTIPLIER")
    
    # Health Check Configuration
    health_check_interval_seconds: int = Field(default=30, env="HEALTH_CHECK_INTERVAL_SECONDS")
    health_check_timeout_seconds: int = Field(default=10, env="HEALTH_CHECK_TIMEOUT_SECONDS")
    
    # Monitoring
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    metrics_port: int = Field(default=9090, env="METRICS_PORT")
    applicationinsights_connection_string: Optional[str] = Field(
        default=None, 
        env="APPLICATIONINSIGHTS_CONNECTION_STRING"
    )
    enable_detailed_logging: bool = Field(default=True, env="ENABLE_DETAILED_LOGGING")
    
    # API Gateway Features
    enable_api_versioning: bool = Field(default=True, env="ENABLE_API_VERSIONING")
    enable_request_id_header: bool = Field(default=True, env="ENABLE_REQUEST_ID_HEADER")
    enable_cors: bool = Field(default=True, env="ENABLE_CORS")
    enable_gzip_compression: bool = Field(default=True, env="ENABLE_GZIP_COMPRESSION")
    
    # WebSocket Configuration
    enable_websocket: bool = Field(default=True, env="ENABLE_WEBSOCKET")
    websocket_ping_interval: int = Field(default=20, env="WEBSOCKET_PING_INTERVAL")
    websocket_ping_timeout: int = Field(default=10, env="WEBSOCKET_PING_TIMEOUT")
    
    # Security Configuration
    jwt_secret_key: str = Field(default="your-secret-key-here-change-in-production", env="JWT_SECRET_KEY")
    enable_security_scanning: bool = Field(default=True, env="ENABLE_SECURITY_SCANNING")
    enable_compliance_monitoring: bool = Field(default=True, env="ENABLE_COMPLIANCE_MONITORING")
    security_log_level: str = Field(default="info", env="SECURITY_LOG_LEVEL")
    
    # Service Mesh Configuration
    service_mesh_enabled: bool = Field(default=False, env="SERVICE_MESH_ENABLED")
    service_mesh_config: Dict[str, Any] = Field(default_factory=dict, env="SERVICE_MESH_CONFIG")
    
    # Development/Testing
    mock_services: bool = Field(default=False, env="MOCK_SERVICES")
    enable_debug_mode: bool = Field(default=False, env="ENABLE_DEBUG_MODE")
    enable_swagger_ui: bool = Field(default=True, env="ENABLE_SWAGGER_UI")
    
    @validator("allowed_origins", pre=True)
    def parse_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("service_mesh_config", pre=True)
    def parse_service_mesh_config(cls, v):
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        return v
    
    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION
    
    @property
    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT
    
    @property
    def is_testing(self) -> bool:
        return self.environment == Environment.TESTING
    
    @property
    def service_urls(self) -> Dict[str, str]:
        """Get all downstream service URLs"""
        return {
            "code_generator": self.code_generator_service_url,
            "image_generator": self.image_generator_service_url
        }
    
    def get_service_url(self, service_name: str) -> Optional[str]:
        """Get URL for a specific service"""
        return self.service_urls.get(service_name)
    
    def validate_configuration(self) -> List[str]:
        """Validate configuration and return list of issues"""
        issues = []
        
        # Check downstream services
        if not self.code_generator_service_url:
            issues.append("Code Generator service URL is required")
            
        if not self.image_generator_service_url:
            issues.append("Image Generator service URL is required")
        
        # Check Azure AD configuration if authentication is enabled
        if self.enable_authentication:
            if not self.azure_tenant_id or not self.azure_client_id:
                issues.append("Azure AD configuration is incomplete for authentication")
        
        # Check JWT secret in production
        if self.is_production and self.jwt_secret == "your-super-secret-jwt-key":
            issues.append("JWT_SECRET must be changed in production")
        
        # Check circuit breaker configuration
        if self.circuit_breaker_enabled:
            if self.circuit_breaker_failure_threshold <= 0:
                issues.append("Circuit breaker failure threshold must be positive")
            if self.circuit_breaker_timeout_seconds <= 0:
                issues.append("Circuit breaker timeout must be positive")
        
        # Check rate limiting configuration
        if self.enable_rate_limiting:
            if self.rate_limit_requests <= 0:
                issues.append("Rate limit requests must be positive")
            if self.rate_limit_window_seconds <= 0:
                issues.append("Rate limit window must be positive")
        
        return issues
    
    def get_circuit_breaker_config(self, service_name: str) -> Dict[str, Any]:
        """Get circuit breaker configuration for a service"""
        return {
            "failure_threshold": self.circuit_breaker_failure_threshold,
            "timeout_seconds": self.circuit_breaker_timeout_seconds,
            "retry_timeout": self.circuit_breaker_retry_timeout,
            "enabled": self.circuit_breaker_enabled
        }
    
    def get_retry_config(self) -> Dict[str, Any]:
        """Get retry configuration"""
        return {
            "enabled": self.enable_retries,
            "max_retries": self.max_retries,
            "delay_seconds": self.retry_delay_seconds,
            "backoff_multiplier": self.retry_backoff_multiplier
        }
    
    def get_rate_limit_config(self) -> Dict[str, Any]:
        """Get rate limiting configuration"""
        return {
            "enabled": self.enable_rate_limiting,
            "requests": self.rate_limit_requests,
            "window_seconds": self.rate_limit_window_seconds
        }
    
    class Config:
        env_file = ".env"
        case_sensitive = False