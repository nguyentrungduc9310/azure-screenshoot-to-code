"""
Image Processor Service - Main FastAPI application entry point
Extracts and processes images for Screenshot-to-Code application
"""
import os
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.routes import health, image_processing
from app.middleware.image_validation import ImageValidationMiddleware
from shared.middleware.correlation import setup_correlation_middleware
from shared.security.gateway_security import setup_api_gateway_security
from shared.monitoring.app_insights import setup_monitoring
from shared.auth.azure_ad import setup_authentication
from shared.config.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    app.logger.info("Image Processor Service starting up...")
    
    # Initialize image processing capabilities
    await initialize_image_processors()
    
    yield
    
    # Shutdown
    app.logger.info("Image Processor Service shutting down...")
    
    # Cleanup resources
    await cleanup_image_processors()


async def initialize_image_processors():
    """Initialize image processing components"""
    # Initialize PIL optimizations
    try:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None  # Remove PIL size limit for large images
    except ImportError:
        pass


async def cleanup_image_processors():
    """Cleanup image processing resources"""
    # Cleanup temporary files, connections, etc.
    pass


def create_application() -> FastAPI:
    """Create and configure FastAPI application"""
    
    app = FastAPI(
        title="Screenshot-to-Code Image Processor",
        description="Microservice for image processing and validation operations",
        version="1.0.0",
        docs_url="/docs" if settings.environment == "development" else None,
        redoc_url="/redoc" if settings.environment == "development" else None,
        lifespan=lifespan
    )
    
    # Setup middleware (order matters!)
    setup_api_gateway_security(app, redis_client=None)  # Will implement Redis later
    app.add_middleware(ImageValidationMiddleware)
    setup_correlation_middleware(app)
    
    # Setup CORS for image processing service
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:8000",  # API Gateway
            "https://copilotstudio.microsoft.com"
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )
    
    # Setup monitoring and authentication
    setup_monitoring(app, "image-processor")
    setup_authentication(app)
    
    # Include routers
    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(image_processing.router, prefix="/api/v1", tags=["image-processing"])
    
    return app


# Create application instance
app = create_application()


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,  # Image processor runs on port 8001
        reload=settings.environment == "development",
        log_level=settings.log_level.lower()
    )