"""
Health Check Routes
Provides health status and readiness checks for the Image Generator service
"""
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.image_provider_manager import ImageProviderManager
from app.services.storage_manager import StorageManager
from shared.health.health_checker import HealthChecker
from shared.monitoring.structured_logger import StructuredLogger

router = APIRouter()

class HealthResponse(BaseModel):
    """Health check response model"""
    status: str
    service: str
    version: str
    timestamp: str
    checks: Dict[str, Any]

class ReadinessResponse(BaseModel):
    """Readiness check response model"""
    ready: bool
    service: str
    checks: Dict[str, Any]

# Dependency injection
async def get_health_checker(request) -> HealthChecker:
    """Get health checker from app state"""
    return request.app.state.health_checker

async def get_image_provider_manager(request) -> ImageProviderManager:
    """Get image provider manager from app state"""
    return request.app.state.image_provider_manager

async def get_storage_manager(request) -> StorageManager:
    """Get storage manager from app state"""
    return request.app.state.storage_manager

async def get_logger(request) -> StructuredLogger:
    """Get logger from app state"""
    return request.app.state.logger

@router.get("/", response_model=HealthResponse)
async def health_check(
    health_checker: HealthChecker = Depends(get_health_checker),
    provider_manager: ImageProviderManager = Depends(get_image_provider_manager),
    storage_manager: StorageManager = Depends(get_storage_manager),
    logger: StructuredLogger = Depends(get_logger)
):
    """
    Health check endpoint
    Returns overall service health status
    """
    try:
        # Get basic health status
        health_status = health_checker.get_health_status()
        
        # Check provider availability
        available_providers = provider_manager.get_available_providers()
        provider_status = "healthy" if available_providers else "unhealthy"
        
        # Check storage backend
        storage_status = "healthy"  # Assume healthy if storage manager exists
        if storage_manager is None:
            storage_status = "disabled"
        
        # Check service components
        checks = {
            "service": health_status["status"],
            "providers": {
                "status": provider_status,
                "available_count": len(available_providers),
                "providers": [p.value for p in available_providers]
            },
            "storage": {
                "status": storage_status,
                "backend": storage_manager.backend.value if storage_manager else "none"
            },
            "uptime_seconds": health_status["uptime_seconds"],
            "start_time": health_status["start_time"]
        }
        
        # Determine overall status
        overall_status = "healthy"
        if health_status["status"] != "healthy" or provider_status != "healthy":
            overall_status = "unhealthy"
        
        return HealthResponse(
            status=overall_status,
            service="image-generator",
            version="1.0.0",
            timestamp=health_status["timestamp"],
            checks=checks
        )
        
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "status": "unhealthy",
                "error": "health_check_failed",
                "message": str(e)
            }
        )

@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check(
    provider_manager: ImageProviderManager = Depends(get_image_provider_manager),
    storage_manager: StorageManager = Depends(get_storage_manager),
    logger: StructuredLogger = Depends(get_logger)
):
    """
    Readiness check endpoint
    Returns whether the service is ready to accept requests
    """
    try:
        # Check if at least one provider is available
        available_providers = provider_manager.get_available_providers()
        providers_ready = len(available_providers) > 0
        
        # Check default provider availability
        default_provider = provider_manager.get_default_provider()
        default_provider_ready = default_provider in available_providers if default_provider else False
        
        # Check storage readiness (if enabled)
        storage_ready = True
        if storage_manager:
            # Storage is ready if manager was initialized successfully
            storage_ready = True
        
        checks = {
            "providers": {
                "ready": providers_ready,
                "available_count": len(available_providers),
                "default_provider_ready": default_provider_ready,
                "default_provider": default_provider.value if default_provider else None
            },
            "storage": {
                "ready": storage_ready,
                "backend": storage_manager.backend.value if storage_manager else "disabled"
            }
        }
        
        # Service is ready if at least one provider is available
        service_ready = providers_ready and storage_ready
        
        if not service_ready:
            # Return 503 Service Unavailable if not ready
            raise HTTPException(
                status_code=503,
                detail=ReadinessResponse(
                    ready=False,
                    service="image-generator",
                    checks=checks
                ).dict()
            )
        
        return ReadinessResponse(
            ready=True,
            service="image-generator", 
            checks=checks
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "ready": False,
                "error": "readiness_check_failed",
                "message": str(e)
            }
        )

@router.get("/live")
async def liveness_check():
    """
    Liveness check endpoint
    Simple endpoint to verify the service is alive
    """
    return {
        "status": "alive",
        "service": "image-generator"
    }