"""
API Gateway Service - Main FastAPI Application
Unified API gateway for orchestrating all Screenshot-to-Code microservices
"""
import asyncio
import logging
from contextual import asynccontextmanager
from typing import List

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from app.core.config import Settings
from app.services.service_client import ServiceClient
from app.routes import health, code_generation, image_generation, websocket, monitoring, copilot_studio, agent_management
from app.api.v1 import security as security_routes
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.logging import LoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.auth import AuthenticationMiddleware
from app.middleware.monitoring import MonitoringMiddleware, BusinessMetricsMiddleware
from app.middleware.caching import CachingMiddleware, SmartCachingMiddleware
from app.middleware.security import SecurityMiddleware, SecurityConfig
from app.middleware.api_security import APISecurityMiddleware
from app.monitoring.prometheus_metrics import PrometheusMetrics
from app.monitoring.opentelemetry_tracing import TracingManager
from app.monitoring.alerting import AlertManager
from app.caching.redis_cache import AdvancedRedisCache, CacheConfig
from app.performance.optimizer import PerformanceOptimizer, OptimizationLevel
from app.security.advanced_auth import AdvancedAuthManager, AuthConfig
from app.security.security_scanner import SecurityScanner
from app.security.compliance import ComplianceManager
from app.security.api_key_manager import AdvancedAPIKeyManager
from shared.monitoring.structured_logger import StructuredLogger
from shared.monitoring.correlation import set_correlation_id, get_correlation_id

# Global settings and services
settings = Settings()
logger = StructuredLogger(
    service_name=settings.service_name,
    environment=settings.environment.value,
    log_level=settings.log_level.value
)
service_client: ServiceClient = None
metrics: PrometheusMetrics = None
tracing: TracingManager = None
alerting: AlertManager = None
cache: AdvancedRedisCache = None
performance_optimizer: PerformanceOptimizer = None
auth_manager: AdvancedAuthManager = None
security_scanner: SecurityScanner = None
compliance_manager: ComplianceManager = None
security_middleware: SecurityMiddleware = None
api_key_manager: AdvancedAPIKeyManager = None
api_security_middleware: APISecurityMiddleware = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global service_client, metrics, tracing, alerting, cache, performance_optimizer, auth_manager, security_scanner, compliance_manager, security_middleware, api_key_manager, api_security_middleware
    
    # Startup
    logger.info("Starting API Gateway service", 
                service=settings.service_name,
                environment=settings.environment.value,
                version="1.0.0")
    
    # Validate configuration
    config_issues = settings.validate_configuration()
    if config_issues:
        logger.error("Configuration validation failed", 
                    issues=config_issues,
                    service=settings.service_name)
        raise RuntimeError(f"Configuration issues: {', '.join(config_issues)}")
    
    # Initialize monitoring components
    logger.info("Initializing monitoring components")
    
    # Initialize Prometheus metrics
    metrics = PrometheusMetrics(settings, logger)
    
    # Initialize OpenTelemetry tracing
    tracing = TracingManager(settings, logger)
    
    # Initialize alerting system
    alerting = AlertManager(settings, logger)
    await alerting.start()
    
    # Initialize caching system
    logger.info("Initializing caching system")
    cache_config = CacheConfig(
        default_ttl=3600,  # 1 hour
        max_memory_mb=100,
        compression_threshold=1024,  # 1KB
        enable_metrics=True,
        key_prefix="apigw"
    )
    cache = AdvancedRedisCache(settings, logger, cache_config)
    await cache.start()
    
    # Initialize performance optimizer
    logger.info("Initializing performance optimizer")
    performance_optimizer = PerformanceOptimizer(
        settings=settings,
        cache=cache,
        logger=logger,
        optimization_level=OptimizationLevel.BALANCED
    )
    await performance_optimizer.start()
    
    # Initialize security components
    logger.info("Initializing security system")
    
    # Initialize authentication manager
    auth_config = AuthConfig(
        jwt_secret_key=settings.jwt_secret_key,
        jwt_algorithm="HS256",
        jwt_access_token_expire_minutes=30,
        password_min_length=8,
        max_login_attempts=5,
        lockout_duration_minutes=15,
        require_mfa=False,
        session_timeout_minutes=60
    )
    auth_manager = AdvancedAuthManager(settings, logger, auth_config)
    
    # Initialize security scanner
    security_scanner = SecurityScanner(logger)
    
    # Initialize compliance manager
    compliance_manager = ComplianceManager(settings, logger)
    await compliance_manager.start()
    
    # Initialize advanced API key manager
    api_key_manager = AdvancedAPIKeyManager(logger)
    
    # Initialize security middleware
    security_config = SecurityConfig(
        enable_threat_detection=True,
        enable_rate_limiting=True,
        enable_ip_blocking=True,
        enable_compliance_logging=True,
        max_requests_per_minute=60,
        max_requests_per_hour=1000,
        auto_block_threshold=10
    )
    
    # Create dummy app for security middleware initialization
    from fastapi import FastAPI as DummyApp
    dummy_app = DummyApp()
    security_middleware = SecurityMiddleware(
        dummy_app,
        auth_manager,
        security_scanner,
        compliance_manager,
        logger,
        security_config
    )
    
    # Initialize API security middleware
    api_security_middleware = APISecurityMiddleware(
        dummy_app,
        logger,
        enable_rate_limiting=True,
        enable_input_validation=True,
        enable_security_headers=True,
        enable_request_sanitization=True
    )
    
    # Initialize service client with advanced features
    service_client = ServiceClient(settings, logger)
    
    # Start advanced components (connection pool, service discovery, circuit breakers)
    await service_client.start()
    logger.info("Advanced service client components started",
                components=["connection_pool", "service_discovery", "circuit_breakers"])
    
    # Health check downstream services
    logger.info("Checking downstream service health")
    for service_name in settings.service_urls.keys():
        is_healthy = await service_client.health_check(service_name)
        if is_healthy:
            logger.info("Downstream service healthy", 
                       service=service_name,
                       url=settings.get_service_url(service_name))
        else:
            logger.warning("Downstream service unhealthy", 
                          service=service_name,
                          url=settings.get_service_url(service_name))
    
    # Store components in app state
    app.state.service_client = service_client
    app.state.settings = settings
    app.state.logger = logger
    app.state.metrics = metrics
    app.state.tracing = tracing
    app.state.alerting = alerting
    app.state.cache = cache
    app.state.performance_optimizer = performance_optimizer
    app.state.auth_manager = auth_manager
    app.state.security_scanner = security_scanner
    app.state.compliance_manager = compliance_manager
    app.state.security_middleware = security_middleware
    app.state.api_key_manager = api_key_manager
    app.state.api_security_middleware = api_security_middleware
    
    logger.info("API Gateway startup completed successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down API Gateway service")
    
    # Shutdown components in reverse order
    if compliance_manager:
        await compliance_manager.stop()
    
    if performance_optimizer:
        await performance_optimizer.stop()
    
    if cache:
        await cache.stop()
    
    if alerting:
        await alerting.stop()
    
    if tracing:
        await tracing.shutdown()
    
    if service_client:
        await service_client.close()
    
    logger.info("API Gateway shutdown completed")

def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    
    # Create FastAPI application
    app = FastAPI(
        title="Screenshot to Code API Gateway",
        description="Unified API gateway for orchestrating all Screenshot-to-Code microservices",
        version="1.0.0",
        docs_url="/docs" if settings.enable_swagger_ui else None,
        redoc_url="/redoc" if settings.enable_swagger_ui else None,
        lifespan=lifespan
    )
    
    # Add trusted host middleware (security)
    if settings.is_production:
        allowed_hosts = ["*"]  # Configure with your domain
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    
    # Add CORS middleware
    if settings.enable_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    # Add GZip compression middleware
    if settings.enable_gzip_compression:
        app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Add API security middleware first (for API-specific hardening)
    app.add_middleware(
        APISecurityMiddleware,
        logger=logger,
        enable_rate_limiting=True,
        enable_input_validation=True,
        enable_security_headers=True,
        enable_request_sanitization=True
    )
    
    # Add security middleware second (for comprehensive protection)
    app.add_middleware(
        SecurityMiddleware,
        auth_manager=auth_manager,
        security_scanner=security_scanner,
        compliance_manager=compliance_manager,
        logger=logger,
        config=SecurityConfig(
            enable_threat_detection=True,
            enable_rate_limiting=True,
            enable_ip_blocking=True,
            enable_compliance_logging=True,
            max_requests_per_minute=60,
            max_requests_per_hour=1000,
            auto_block_threshold=10
        )
    )
    
    # Add monitoring middleware second (for comprehensive tracking)
    app.add_middleware(
        MonitoringMiddleware,
        metrics=metrics,
        tracing=tracing,
        alerting=alerting,
        logger=logger
    )
    
    # Add caching middleware (smart caching with performance optimization)
    app.add_middleware(
        SmartCachingMiddleware,
        cache=cache,
        optimizer=performance_optimizer,
        logger=logger
    )
    
    # Add business metrics middleware
    app.add_middleware(BusinessMetricsMiddleware, metrics=metrics, logger=logger)
    
    # Add other custom middleware
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(LoggingMiddleware, logger=logger)
    
    if settings.enable_rate_limiting:
        app.add_middleware(RateLimitMiddleware, settings=settings)
    
    if settings.enable_authentication:
        app.add_middleware(AuthenticationMiddleware, settings=settings)
    
    # Include routers
    app.include_router(health.router, prefix=settings.api_prefix, tags=["health"])
    app.include_router(code_generation.router, prefix=settings.api_prefix, tags=["code-generation"])
    app.include_router(image_generation.router, prefix=settings.api_prefix, tags=["image-generation"])
    app.include_router(monitoring.router, prefix=settings.api_prefix, tags=["monitoring"])
    app.include_router(security_routes.router, prefix=settings.api_prefix, tags=["security"])
    app.include_router(copilot_studio.router, prefix=settings.api_prefix, tags=["copilot-studio"])
    app.include_router(agent_management.router, prefix=settings.api_prefix, tags=["agent-management"])
    
    if settings.enable_websocket:
        app.include_router(websocket.router, prefix=settings.api_prefix, tags=["websocket"])
    
    # Global exception handler
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        correlation_id = get_correlation_id()
        
        logger.error("HTTP exception occurred",
                    status_code=exc.status_code,
                    detail=exc.detail,
                    path=request.url.path,
                    method=request.method,
                    correlation_id=correlation_id)
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "status_code": exc.status_code,
                "correlation_id": correlation_id,
                "timestamp": logger._get_timestamp()
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        correlation_id = get_correlation_id()
        
        logger.error("Unhandled exception occurred",
                    error=str(exc),
                    error_type=type(exc).__name__,
                    path=request.url.path,
                    method=request.method,
                    correlation_id=correlation_id)
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "status_code": 500,
                "correlation_id": correlation_id,
                "timestamp": logger._get_timestamp()
            }
        )
    
    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "service": settings.service_name,
            "version": "1.0.0",
            "environment": settings.environment.value,
            "status": "operational",
            "docs_url": "/docs" if settings.enable_swagger_ui else None,
            "health_url": f"{settings.api_prefix}/health"
        }
    
    return app

# Create the application
app = create_app()

if __name__ == "__main__":
    # Development server
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.is_development,
        log_level=settings.log_level.value.lower(),
        access_log=settings.enable_request_logging
    )