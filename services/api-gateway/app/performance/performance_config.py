"""
Performance Optimization Configuration
Centralized configuration for all performance optimization components
"""
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

try:
    from shared.monitoring.structured_logger import StructuredLogger
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger


class OptimizationLevel(Enum):
    """Performance optimization levels"""
    DISABLED = "disabled"
    BASIC = "basic"
    STANDARD = "standard"
    AGGRESSIVE = "aggressive"
    MAXIMUM = "maximum"


@dataclass
class CacheConfig:
    """Cache optimization configuration"""
    enabled: bool = True
    memory_size_mb: int = 100
    default_ttl_seconds: int = 3600
    redis_enabled: bool = False
    redis_url: Optional[str] = None
    auto_eviction: bool = True
    optimization_enabled: bool = True
    
    @classmethod
    def from_env(cls) -> 'CacheConfig':
        """Create cache config from environment variables"""
        return cls(
            enabled=os.getenv("CACHE_ENABLED", "true").lower() == "true",
            memory_size_mb=int(os.getenv("CACHE_MEMORY_SIZE_MB", "100")),
            default_ttl_seconds=int(os.getenv("CACHE_DEFAULT_TTL", "3600")),
            redis_enabled=os.getenv("REDIS_ENABLED", "false").lower() == "true",
            redis_url=os.getenv("REDIS_URL"),
            auto_eviction=os.getenv("CACHE_AUTO_EVICTION", "true").lower() == "true",
            optimization_enabled=os.getenv("CACHE_OPTIMIZATION", "true").lower() == "true"
        )


@dataclass
class ResponseOptimizationConfig:
    """Response optimization configuration"""
    enabled: bool = True
    max_workers: Optional[int] = None
    enable_batching: bool = True
    enable_parallel_processing: bool = True
    enable_streaming: bool = True
    batch_size: int = 10
    batch_wait_time: float = 0.5
    parallel_threshold: int = 3
    
    @classmethod
    def from_env(cls) -> 'ResponseOptimizationConfig':
        """Create response optimization config from environment variables"""
        return cls(
            enabled=os.getenv("RESPONSE_OPTIMIZATION_ENABLED", "true").lower() == "true",
            max_workers=int(os.getenv("RESPONSE_MAX_WORKERS")) if os.getenv("RESPONSE_MAX_WORKERS") else None,
            enable_batching=os.getenv("RESPONSE_BATCHING", "true").lower() == "true",
            enable_parallel_processing=os.getenv("RESPONSE_PARALLEL", "true").lower() == "true",
            enable_streaming=os.getenv("RESPONSE_STREAMING", "true").lower() == "true",
            batch_size=int(os.getenv("RESPONSE_BATCH_SIZE", "10")),
            batch_wait_time=float(os.getenv("RESPONSE_BATCH_WAIT", "0.5")),
            parallel_threshold=int(os.getenv("RESPONSE_PARALLEL_THRESHOLD", "3"))
        )


@dataclass
class ResourceOptimizationConfig:
    """Resource optimization configuration"""
    enabled: bool = True
    monitoring_interval: float = 10.0
    optimization_interval: float = 30.0
    cpu_soft_limit: float = 70.0
    cpu_hard_limit: float = 90.0
    memory_soft_limit: float = 75.0
    memory_hard_limit: float = 90.0
    disk_soft_limit: float = 80.0
    disk_hard_limit: float = 95.0
    auto_scaling_enabled: bool = True
    emergency_mode_threshold: float = 95.0
    
    @classmethod
    def from_env(cls) -> 'ResourceOptimizationConfig':
        """Create resource optimization config from environment variables"""
        return cls(
            enabled=os.getenv("RESOURCE_MONITORING_ENABLED", "true").lower() == "true",
            monitoring_interval=float(os.getenv("RESOURCE_MONITORING_INTERVAL", "10.0")),
            optimization_interval=float(os.getenv("RESOURCE_OPTIMIZATION_INTERVAL", "30.0")),
            cpu_soft_limit=float(os.getenv("CPU_SOFT_LIMIT", "70.0")),
            cpu_hard_limit=float(os.getenv("CPU_HARD_LIMIT", "90.0")),
            memory_soft_limit=float(os.getenv("MEMORY_SOFT_LIMIT", "75.0")),
            memory_hard_limit=float(os.getenv("MEMORY_HARD_LIMIT", "90.0")),
            disk_soft_limit=float(os.getenv("DISK_SOFT_LIMIT", "80.0")),
            disk_hard_limit=float(os.getenv("DISK_HARD_LIMIT", "95.0")),
            auto_scaling_enabled=os.getenv("AUTO_SCALING_ENABLED", "true").lower() == "true",
            emergency_mode_threshold=float(os.getenv("EMERGENCY_MODE_THRESHOLD", "95.0"))
        )


@dataclass
class MiddlewareConfig:
    """Performance middleware configuration"""
    enabled: bool = True
    enable_request_caching: bool = True
    enable_response_compression: bool = True
    enable_performance_headers: bool = True
    cache_ttl_seconds: int = 300
    compression_threshold_bytes: int = 1024
    max_cache_size_mb: int = 50
    
    @classmethod
    def from_env(cls) -> 'MiddlewareConfig':
        """Create middleware config from environment variables"""
        return cls(
            enabled=os.getenv("MIDDLEWARE_ENABLED", "true").lower() == "true",
            enable_request_caching=os.getenv("MIDDLEWARE_CACHING", "true").lower() == "true",
            enable_response_compression=os.getenv("MIDDLEWARE_COMPRESSION", "true").lower() == "true",
            enable_performance_headers=os.getenv("MIDDLEWARE_HEADERS", "true").lower() == "true",
            cache_ttl_seconds=int(os.getenv("MIDDLEWARE_CACHE_TTL", "300")),
            compression_threshold_bytes=int(os.getenv("COMPRESSION_THRESHOLD", "1024")),
            max_cache_size_mb=int(os.getenv("MIDDLEWARE_CACHE_SIZE_MB", "50"))
        )


@dataclass
class PerformanceConfiguration:
    """Comprehensive performance optimization configuration"""
    optimization_level: OptimizationLevel = OptimizationLevel.STANDARD
    performance_target_ms: float = 2000.0
    enable_detailed_logging: bool = False
    cache_config: CacheConfig = field(default_factory=CacheConfig)
    response_config: ResponseOptimizationConfig = field(default_factory=ResponseOptimizationConfig)
    resource_config: ResourceOptimizationConfig = field(default_factory=ResourceOptimizationConfig)
    middleware_config: MiddlewareConfig = field(default_factory=MiddlewareConfig)
    
    @classmethod
    def from_env(cls) -> 'PerformanceConfiguration':
        """Create complete configuration from environment variables"""
        
        # Parse optimization level
        level_str = os.getenv("PERFORMANCE_OPTIMIZATION_LEVEL", "standard").lower()
        try:
            optimization_level = OptimizationLevel(level_str)
        except ValueError:
            optimization_level = OptimizationLevel.STANDARD
        
        config = cls(
            optimization_level=optimization_level,
            performance_target_ms=float(os.getenv("PERFORMANCE_TARGET_MS", "2000.0")),
            enable_detailed_logging=os.getenv("PERFORMANCE_DETAILED_LOGGING", "false").lower() == "true",
            cache_config=CacheConfig.from_env(),
            response_config=ResponseOptimizationConfig.from_env(),
            resource_config=ResourceOptimizationConfig.from_env(),
            middleware_config=MiddlewareConfig.from_env()
        )
        
        # Apply optimization level adjustments
        config._apply_optimization_level()
        
        return config
    
    @classmethod
    def for_optimization_level(cls, level: OptimizationLevel) -> 'PerformanceConfiguration':
        """Create configuration for specific optimization level"""
        config = cls(optimization_level=level)
        config._apply_optimization_level()
        return config
    
    def _apply_optimization_level(self):
        """Apply optimization level-specific adjustments"""
        
        if self.optimization_level == OptimizationLevel.DISABLED:
            # Disable all optimizations
            self.cache_config.enabled = False
            self.response_config.enabled = False
            self.resource_config.enabled = False
            self.middleware_config.enabled = False
            
        elif self.optimization_level == OptimizationLevel.BASIC:
            # Enable only basic optimizations
            self.cache_config.enabled = True
            self.cache_config.memory_size_mb = 50
            self.response_config.enabled = False
            self.resource_config.enabled = False
            self.middleware_config.enable_request_caching = True
            self.middleware_config.enable_response_compression = False
            
        elif self.optimization_level == OptimizationLevel.STANDARD:
            # Standard optimizations (default values)
            pass
            
        elif self.optimization_level == OptimizationLevel.AGGRESSIVE:
            # More aggressive optimizations
            self.cache_config.memory_size_mb = 200
            self.cache_config.default_ttl_seconds = 7200  # 2 hours
            self.response_config.enable_batching = True
            self.response_config.batch_size = 20
            self.resource_config.optimization_interval = 15.0  # More frequent
            self.middleware_config.cache_ttl_seconds = 600  # 10 minutes
            
        elif self.optimization_level == OptimizationLevel.MAXIMUM:
            # Maximum optimizations
            self.cache_config.memory_size_mb = 500
            self.cache_config.default_ttl_seconds = 14400  # 4 hours
            self.response_config.batch_size = 50
            self.response_config.parallel_threshold = 2
            self.resource_config.optimization_interval = 10.0
            self.resource_config.cpu_soft_limit = 60.0
            self.resource_config.memory_soft_limit = 65.0
            self.middleware_config.cache_ttl_seconds = 1800  # 30 minutes
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            "optimization_level": self.optimization_level.value,
            "performance_target_ms": self.performance_target_ms,
            "enable_detailed_logging": self.enable_detailed_logging,
            "cache_config": {
                "enabled": self.cache_config.enabled,
                "memory_size_mb": self.cache_config.memory_size_mb,
                "default_ttl_seconds": self.cache_config.default_ttl_seconds,
                "redis_enabled": self.cache_config.redis_enabled,
                "auto_eviction": self.cache_config.auto_eviction,
                "optimization_enabled": self.cache_config.optimization_enabled
            },
            "response_config": {
                "enabled": self.response_config.enabled,
                "max_workers": self.response_config.max_workers,
                "enable_batching": self.response_config.enable_batching,
                "enable_parallel_processing": self.response_config.enable_parallel_processing,
                "enable_streaming": self.response_config.enable_streaming,
                "batch_size": self.response_config.batch_size,
                "batch_wait_time": self.response_config.batch_wait_time,
                "parallel_threshold": self.response_config.parallel_threshold
            },
            "resource_config": {
                "enabled": self.resource_config.enabled,
                "monitoring_interval": self.resource_config.monitoring_interval,
                "optimization_interval": self.resource_config.optimization_interval,
                "cpu_soft_limit": self.resource_config.cpu_soft_limit,
                "cpu_hard_limit": self.resource_config.cpu_hard_limit,
                "memory_soft_limit": self.resource_config.memory_soft_limit,
                "memory_hard_limit": self.resource_config.memory_hard_limit,
                "auto_scaling_enabled": self.resource_config.auto_scaling_enabled
            },
            "middleware_config": {
                "enabled": self.middleware_config.enabled,
                "enable_request_caching": self.middleware_config.enable_request_caching,
                "enable_response_compression": self.middleware_config.enable_response_compression,
                "enable_performance_headers": self.middleware_config.enable_performance_headers,
                "cache_ttl_seconds": self.middleware_config.cache_ttl_seconds,
                "compression_threshold_bytes": self.middleware_config.compression_threshold_bytes
            }
        }
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of issues"""
        issues = []
        
        # Validate performance target
        if self.performance_target_ms <= 0:
            issues.append("Performance target must be positive")
        
        # Validate cache configuration
        if self.cache_config.enabled:
            if self.cache_config.memory_size_mb <= 0:
                issues.append("Cache memory size must be positive")
            
            if self.cache_config.default_ttl_seconds <= 0:
                issues.append("Cache TTL must be positive")
        
        # Validate response optimization
        if self.response_config.enabled:
            if self.response_config.batch_size <= 0:
                issues.append("Batch size must be positive")
            
            if self.response_config.batch_wait_time < 0:
                issues.append("Batch wait time cannot be negative")
            
            if self.response_config.parallel_threshold <= 0:
                issues.append("Parallel threshold must be positive")
        
        # Validate resource optimization
        if self.resource_config.enabled:
            if self.resource_config.monitoring_interval <= 0:
                issues.append("Monitoring interval must be positive")
            
            if self.resource_config.cpu_soft_limit >= self.resource_config.cpu_hard_limit:
                issues.append("CPU soft limit must be less than hard limit")
            
            if self.resource_config.memory_soft_limit >= self.resource_config.memory_hard_limit:
                issues.append("Memory soft limit must be less than hard limit")
        
        # Validate middleware configuration
        if self.middleware_config.enabled:
            if self.middleware_config.cache_ttl_seconds <= 0:
                issues.append("Middleware cache TTL must be positive")
            
            if self.middleware_config.compression_threshold_bytes < 0:
                issues.append("Compression threshold cannot be negative")
        
        return issues
    
    def log_configuration(self, logger: StructuredLogger):
        """Log current configuration"""
        
        validation_issues = self.validate()
        if validation_issues:
            logger.warning(
                "Performance configuration validation issues",
                issues=validation_issues
            )
        
        logger.info(
            "Performance optimization configuration loaded",
            optimization_level=self.optimization_level.value,
            performance_target_ms=self.performance_target_ms,
            cache_enabled=self.cache_config.enabled,
            response_optimization_enabled=self.response_config.enabled,
            resource_monitoring_enabled=self.resource_config.enabled,
            middleware_enabled=self.middleware_config.enabled
        )
        
        if self.enable_detailed_logging:
            logger.info(
                "Detailed performance configuration",
                full_config=self.to_dict()
            )


# Environment-specific configuration presets
DEVELOPMENT_CONFIG = PerformanceConfiguration.for_optimization_level(OptimizationLevel.BASIC)
TESTING_CONFIG = PerformanceConfiguration.for_optimization_level(OptimizationLevel.STANDARD)
PRODUCTION_CONFIG = PerformanceConfiguration.for_optimization_level(OptimizationLevel.AGGRESSIVE)


def get_performance_config() -> PerformanceConfiguration:
    """Get performance configuration based on environment"""
    
    environment = os.getenv("ENVIRONMENT", "development").lower()
    
    if environment == "production":
        return PRODUCTION_CONFIG
    elif environment == "testing":
        return TESTING_CONFIG
    elif environment == "development":
        return DEVELOPMENT_CONFIG
    else:
        # Load from environment variables
        return PerformanceConfiguration.from_env()


def create_redis_client(cache_config: CacheConfig):
    """Create Redis client if Redis is enabled"""
    
    if not cache_config.redis_enabled or not cache_config.redis_url:
        return None
    
    try:
        import redis.asyncio as redis
        
        client = redis.from_url(
            cache_config.redis_url,
            encoding="utf-8",
            decode_responses=False,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30
        )
        
        return client
        
    except ImportError:
        logger = StructuredLogger()
        logger.warning(
            "Redis client requested but redis library not available",
            redis_url=cache_config.redis_url
        )
        return None
    
    except Exception as e:
        logger = StructuredLogger()
        logger.error(
            "Failed to create Redis client",
            redis_url=cache_config.redis_url,
            error=str(e)
        )
        return None