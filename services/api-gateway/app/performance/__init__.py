"""
Performance Optimization Package
Comprehensive performance optimization suite for the API Gateway
"""
import asyncio
from typing import Optional

try:
    from shared.monitoring.structured_logger import StructuredLogger
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger

# Import all performance optimization components
from .cache_optimization import (
    AdvancedCacheManager,
    CacheLevel,
    CacheStrategy,
    get_cache_manager,
    initialize_cache_manager
)
from .response_optimization import (
    ResponseOptimizer,
    OptimizationStrategy,
    ProcessingPriority,
    get_response_optimizer,
    initialize_response_optimizer
)
from .resource_optimization import (
    ResourceOptimizer,
    ResourceType,
    OptimizationAction,
    get_resource_optimizer,
    initialize_resource_optimizer
)
from .performance_integration import (
    PerformanceIntegrationManager,
    PerformanceConfig as IntegrationConfig,
    get_performance_manager,
    initialize_performance_manager,
    shutdown_performance_manager
)
from .performance_middleware import (
    PerformanceOptimizationMiddleware,
    PerformanceMetricsEndpoint,
    create_performance_middleware,
    add_performance_routes
)
from .performance_config import (
    PerformanceConfiguration,
    OptimizationLevel,
    CacheConfig,
    ResponseOptimizationConfig,
    ResourceOptimizationConfig,
    MiddlewareConfig,
    get_performance_config,
    create_redis_client,
    DEVELOPMENT_CONFIG,
    TESTING_CONFIG,
    PRODUCTION_CONFIG
)

# Package version
__version__ = "1.0.0"

# Export main components
__all__ = [
    # Cache optimization
    "AdvancedCacheManager",
    "CacheLevel",
    "CacheStrategy",
    "get_cache_manager",
    "initialize_cache_manager",
    
    # Response optimization
    "ResponseOptimizer",
    "OptimizationStrategy",
    "ProcessingPriority",
    "get_response_optimizer",
    "initialize_response_optimizer",
    
    # Resource optimization
    "ResourceOptimizer",
    "ResourceType",
    "OptimizationAction",
    "get_resource_optimizer",
    "initialize_resource_optimizer",
    
    # Integration
    "PerformanceIntegrationManager",
    "IntegrationConfig",
    "get_performance_manager",
    "initialize_performance_manager",
    "shutdown_performance_manager",
    
    # Middleware
    "PerformanceOptimizationMiddleware",
    "PerformanceMetricsEndpoint",
    "create_performance_middleware",
    "add_performance_routes",
    
    # Configuration
    "PerformanceConfiguration",
    "OptimizationLevel",
    "CacheConfig",
    "ResponseOptimizationConfig",
    "ResourceOptimizationConfig",
    "MiddlewareConfig",
    "get_performance_config",
    "create_redis_client",
    "DEVELOPMENT_CONFIG",
    "TESTING_CONFIG",
    "PRODUCTION_CONFIG",
    
    # Main functions
    "initialize_performance_optimization",
    "shutdown_performance_optimization",
    "setup_fastapi_performance"
]


async def initialize_performance_optimization(
    config: Optional[PerformanceConfiguration] = None,
    logger: Optional[StructuredLogger] = None
) -> PerformanceIntegrationManager:
    """
    Initialize complete performance optimization system
    
    Args:
        config: Performance configuration (uses environment-based config if None)
        logger: Logger instance (creates new one if None)
    
    Returns:
        Initialized performance integration manager
    """
    
    if config is None:
        config = get_performance_config()
    
    if logger is None:
        logger = StructuredLogger()
    
    # Validate configuration
    validation_issues = config.validate()
    if validation_issues:
        logger.warning(
            "Performance configuration validation issues",
            issues=validation_issues
        )
    
    # Log configuration
    config.log_configuration(logger)
    
    try:
        # Create Redis client if needed
        redis_client = None
        if config.cache_config.redis_enabled:
            redis_client = create_redis_client(config.cache_config)
            if redis_client:
                logger.info("Redis client created successfully")
            else:
                logger.warning("Redis client creation failed, using memory-only cache")
        
        # Initialize cache manager
        if config.cache_config.enabled:
            cache_manager = initialize_cache_manager(
                redis_client=redis_client,
                max_memory_size=config.cache_config.memory_size_mb * 1024 * 1024
            )
            logger.info(
                "Cache manager initialized",
                memory_size_mb=config.cache_config.memory_size_mb,
                redis_enabled=redis_client is not None
            )
        
        # Initialize response optimizer
        if config.response_config.enabled:
            response_optimizer = initialize_response_optimizer(
                max_workers=config.response_config.max_workers,
                enable_batching=config.response_config.enable_batching,
                enable_parallel_processing=config.response_config.enable_parallel_processing
            )
            logger.info(
                "Response optimizer initialized",
                max_workers=config.response_config.max_workers,
                batching_enabled=config.response_config.enable_batching,
                parallel_enabled=config.response_config.enable_parallel_processing
            )
        
        # Initialize resource optimizer
        if config.resource_config.enabled:
            resource_optimizer = await initialize_resource_optimizer(
                monitoring_interval=config.resource_config.monitoring_interval,
                optimization_interval=config.resource_config.optimization_interval
            )
            logger.info(
                "Resource optimizer initialized",
                monitoring_interval=config.resource_config.monitoring_interval,
                optimization_interval=config.resource_config.optimization_interval
            )
        
        # Initialize performance integration manager
        integration_config = IntegrationConfig(
            enable_caching=config.cache_config.enabled,
            enable_response_optimization=config.response_config.enabled,
            enable_resource_monitoring=config.resource_config.enabled,
            cache_memory_size_mb=config.cache_config.memory_size_mb,
            max_workers=config.response_config.max_workers,
            monitoring_interval=config.resource_config.monitoring_interval,
            optimization_interval=config.resource_config.optimization_interval,
            performance_target_ms=config.performance_target_ms
        )
        
        performance_manager = await initialize_performance_manager(integration_config)
        
        logger.info(
            "Performance optimization system initialized successfully",
            optimization_level=config.optimization_level.value,
            components_enabled={
                "cache": config.cache_config.enabled,
                "response_optimization": config.response_config.enabled,  
                "resource_monitoring": config.resource_config.enabled,
                "middleware": config.middleware_config.enabled
            }
        )
        
        return performance_manager
        
    except Exception as e:
        logger.error(
            "Performance optimization initialization failed",
            error=str(e),
            config_level=config.optimization_level.value
        )
        raise


async def shutdown_performance_optimization(logger: Optional[StructuredLogger] = None):
    """
    Shutdown performance optimization system gracefully
    
    Args:
        logger: Logger instance (creates new one if None)
    """
    
    if logger is None:
        logger = StructuredLogger()
    
    try:
        await shutdown_performance_manager()
        logger.info("Performance optimization system shutdown completed")
        
    except Exception as e:
        logger.error(
            "Performance optimization shutdown error",
            error=str(e)
        )


def setup_fastapi_performance(
    app,
    config: Optional[PerformanceConfiguration] = None,
    performance_manager: Optional[PerformanceIntegrationManager] = None,
    logger: Optional[StructuredLogger] = None
) -> PerformanceOptimizationMiddleware:
    """
    Set up performance optimization for FastAPI application
    
    Args:
        app: FastAPI application instance
        config: Performance configuration (uses environment-based config if None)
        performance_manager: Performance manager instance (uses global if None)
        logger: Logger instance (creates new one if None)
    
    Returns:
        Configured performance optimization middleware
    """
    
    if config is None:
        config = get_performance_config()
    
    if logger is None:
        logger = StructuredLogger()
    
    if performance_manager is None:
        performance_manager = get_performance_manager()
    
    # Create and add middleware
    if config.middleware_config.enabled:
        middleware = create_performance_middleware(
            app=app,
            performance_manager=performance_manager,
            enable_request_caching=config.middleware_config.enable_request_caching,
            enable_response_compression=config.middleware_config.enable_response_compression,
            enable_performance_headers=config.middleware_config.enable_performance_headers,
            cache_ttl_seconds=config.middleware_config.cache_ttl_seconds
        )
        
        app.add_middleware(PerformanceOptimizationMiddleware, **middleware.__dict__)
        
        logger.info(
            "Performance middleware added to FastAPI application",
            request_caching=config.middleware_config.enable_request_caching,
            response_compression=config.middleware_config.enable_response_compression,
            performance_headers=config.middleware_config.enable_performance_headers
        )
        
        # Add performance monitoring routes
        add_performance_routes(
            app=app,
            performance_manager=performance_manager,
            middleware=middleware  
        )
        
        logger.info("Performance monitoring routes added")
        
        return middleware
    
    else:
        logger.info("Performance middleware disabled by configuration")
        return None


# Convenience function for quick setup
async def quick_setup(
    app,
    optimization_level: OptimizationLevel = OptimizationLevel.STANDARD,
    logger: Optional[StructuredLogger] = None
) -> tuple[PerformanceIntegrationManager, Optional[PerformanceOptimizationMiddleware]]:
    """
    Quick setup for performance optimization with minimal configuration
    
    Args:
        app: FastAPI application instance
        optimization_level: Optimization level to use
        logger: Logger instance (creates new one if None)
    
    Returns:
        Tuple of (performance_manager, middleware)
    """
    
    if logger is None:
        logger = StructuredLogger()
    
    # Create configuration for optimization level
    config = PerformanceConfiguration.for_optimization_level(optimization_level)
    
    # Initialize performance optimization
    performance_manager = await initialize_performance_optimization(config, logger)
    
    # Setup FastAPI performance
    middleware = setup_fastapi_performance(app, config, performance_manager, logger)
    
    logger.info(
        "Performance optimization quick setup completed",
        optimization_level=optimization_level.value,
        middleware_enabled=middleware is not None
    )
    
    return performance_manager, middleware


# Default configuration for different environments
def get_development_setup():
    """Get development environment setup"""
    return DEVELOPMENT_CONFIG


def get_testing_setup():
    """Get testing environment setup"""
    return TESTING_CONFIG


def get_production_setup():
    """Get production environment setup"""
    return PRODUCTION_CONFIG