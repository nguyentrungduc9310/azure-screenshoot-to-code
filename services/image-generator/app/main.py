"""
Image Generator Service - Main FastAPI Application
Microservice for generating images using DALL-E 3 and Flux Schnell
"""
import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

# Shared modules
from shared.auth.azure_ad import setup_azure_ad_auth
from shared.monitoring.app_insights import setup_monitoring
from shared.monitoring.structured_logger import StructuredLogger
from shared.monitoring.correlation import get_correlation_id
from shared.health.health_checker import HealthChecker

# Service modules
from app.routes import image_generation, health
from app.middleware.validation import RequestValidationMiddleware
from app.services.image_provider_manager import ImageProviderManager
from app.services.storage_manager import StorageManager
from app.core.config import Settings

# Initialize settings
settings = Settings()

# Initialize structured logger
logger = StructuredLogger(
    service_name=settings.service_name,
    environment=settings.environment
)

# Initialize health checker
health_checker = HealthChecker(service_name=settings.service_name)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    logger.info("Starting Image Generator service", 
                service_version="1.0", 
                environment=settings.environment)
    
    # Initialize image provider manager
    image_provider_manager = ImageProviderManager(settings=settings, logger=logger)
    await image_provider_manager.initialize()
    
    # Initialize storage manager if enabled
    storage_manager = None
    if settings.enable_image_storage:
        storage_manager = StorageManager(settings=settings, logger=logger)
        await storage_manager.initialize()
    
    # Store in app state
    app.state.image_provider_manager = image_provider_manager
    app.state.storage_manager = storage_manager
    app.state.logger = logger
    app.state.health_checker = health_checker
    
    # Health check startup
    health_checker.startup()
    
    yield
    
    # Cleanup
    logger.info("Shutting down Image Generator service")
    await image_provider_manager.cleanup()
    if storage_manager:
        await storage_manager.cleanup()
    health_checker.shutdown()

def create_application() -> FastAPI:
    """Create and configure FastAPI application"""
    
    app = FastAPI(
        title="Image Generator Service",
        description="Microservice for generating images using DALL-E 3 and Flux Schnell",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    
    # Custom middleware
    app.add_middleware(RequestValidationMiddleware)
    
    # Exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        correlation_id = get_correlation_id()
        
        logger.error("Unhandled exception occurred",
                    error=str(exc),
                    path=request.url.path,
                    method=request.method,
                    correlation_id=correlation_id,
                    exc_info=exc)
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "internal_server_error",
                "message": "An internal server error occurred",
                "correlation_id": correlation_id
            }
        )
    
    # Include routers
    app.include_router(health.router, prefix="/health", tags=["Health"])
    app.include_router(image_generation.router, prefix="/api/v1", tags=["Image Generation"])
    
    return app

# Create app instance
app = create_application()

# Setup authentication if enabled
if settings.enable_authentication:
    setup_azure_ad_auth(app, settings.azure_tenant_id, settings.azure_client_id)

# Setup monitoring
if settings.applicationinsights_connection_string:
    setup_monitoring(
        app, 
        settings.applicationinsights_connection_string,
        service_name=settings.service_name
    )

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "image-generator",
        "version": "1.0.0",
        "status": "operational",
        "description": "Image generation microservice with DALL-E 3 and Flux Schnell support"
    }

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower()
    )