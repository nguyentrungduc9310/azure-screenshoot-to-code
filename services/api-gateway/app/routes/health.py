"""
Health Check Routes
Service health monitoring and diagnostics
"""
from typing import Dict, Any

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

from app.services.service_client import ServiceClient
from shared.monitoring.correlation import get_correlation_id

router = APIRouter()

def get_service_client(request: Request) -> ServiceClient:
    """Dependency to get service client from app state"""
    return request.app.state.service_client

def get_logger(request: Request):
    """Dependency to get logger from app state"""
    return request.app.state.logger

@router.get("/health")
async def health_check(
    request: Request,
    service_client: ServiceClient = Depends(get_service_client),
    logger = Depends(get_logger)
) -> JSONResponse:
    """Basic health check endpoint"""
    correlation_id = get_correlation_id()
    
    try:
        # Check downstream services
        service_health = await service_client.get_service_health()
        circuit_breaker_status = await service_client.get_circuit_breaker_status()
        
        # Determine overall health
        overall_health = all(
            status.value == "healthy" 
            for status in service_health.values()
        )
        
        response_data = {
            "status": "healthy" if overall_health else "degraded",
            "timestamp": logger._get_timestamp(),
            "correlation_id": correlation_id,
            "service": request.app.state.settings.service_name,
            "version": "1.0.0",
            "environment": request.app.state.settings.environment.value,
            "downstream_services": {
                name: status.value 
                for name, status in service_health.items()
            },
            "circuit_breakers": circuit_breaker_status
        }
        
        status_code = 200 if overall_health else 503
        return JSONResponse(content=response_data, status_code=status_code)
        
    except Exception as e:
        logger.error("Health check failed", 
                    error=str(e),
                    correlation_id=correlation_id)
        
        return JSONResponse(
            content={
                "status": "unhealthy",
                "error": "Health check failed",
                "timestamp": logger._get_timestamp(),
                "correlation_id": correlation_id
            },
            status_code=503
        )

@router.get("/health/live")
async def liveness_check(request: Request) -> JSONResponse:
    """Kubernetes liveness probe endpoint"""
    return JSONResponse(
        content={
            "status": "alive",
            "timestamp": request.app.state.logger._get_timestamp(),
            "service": request.app.state.settings.service_name
        }
    )

@router.get("/health/ready")
async def readiness_check(
    request: Request,
    service_client: ServiceClient = Depends(get_service_client)
) -> JSONResponse:
    """Kubernetes readiness probe endpoint"""
    try:
        # Check if downstream services are available
        code_gen_healthy = await service_client.health_check("code_generator")
        image_gen_healthy = await service_client.health_check("image_generator")
        
        is_ready = code_gen_healthy and image_gen_healthy
        
        return JSONResponse(
            content={
                "status": "ready" if is_ready else "not_ready",
                "timestamp": request.app.state.logger._get_timestamp(),
                "service": request.app.state.settings.service_name,
                "dependencies": {
                    "code_generator": "healthy" if code_gen_healthy else "unhealthy",
                    "image_generator": "healthy" if image_gen_healthy else "unhealthy"
                }
            },
            status_code=200 if is_ready else 503
        )
        
    except Exception as e:
        return JSONResponse(
            content={
                "status": "not_ready",
                "error": str(e),
                "timestamp": request.app.state.logger._get_timestamp(),
                "service": request.app.state.settings.service_name
            },
            status_code=503
        )

@router.get("/health/detailed")
async def detailed_health_check(
    request: Request,
    service_client: ServiceClient = Depends(get_service_client),
    logger = Depends(get_logger)
) -> JSONResponse:
    """Detailed health check with metrics and diagnostics"""
    correlation_id = get_correlation_id()
    
    try:
        # Get service health
        service_health = await service_client.get_service_health()
        circuit_breaker_status = await service_client.get_circuit_breaker_status()
        
        # Get system information
        settings = request.app.state.settings
        
        response_data = {
            "status": "healthy",
            "timestamp": logger._get_timestamp(),
            "correlation_id": correlation_id,
            "service_info": {
                "name": settings.service_name,
                "version": "1.0.0",
                "environment": settings.environment.value,
                "api_prefix": settings.api_prefix,
                "load_balancing_strategy": settings.load_balancing_strategy.value
            },
            "configuration": {
                "authentication_enabled": settings.enable_authentication,
                "rate_limiting_enabled": settings.enable_rate_limiting,
                "circuit_breaker_enabled": settings.circuit_breaker_enabled,
                "websocket_enabled": settings.enable_websocket,
                "cors_enabled": settings.enable_cors
            },
            "downstream_services": {
                name: {
                    "status": status.value,
                    "url": settings.get_service_url(name)
                }
                for name, status in service_health.items()
            },
            "circuit_breakers": circuit_breaker_status,
            "load_balancing": {
                "strategy": settings.load_balancing_strategy.value,
                "health_check_interval": f"{settings.health_check_interval_seconds}s",
                "timeout": f"{settings.health_check_timeout_seconds}s"
            },
            "rate_limiting": {
                "enabled": settings.enable_rate_limiting,
                "requests_per_window": settings.rate_limit_requests,
                "window_seconds": settings.rate_limit_window_seconds
            } if settings.enable_rate_limiting else None
        }
        
        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error("Detailed health check failed",
                    error=str(e),
                    correlation_id=correlation_id)
        
        return JSONResponse(
            content={
                "status": "error",
                "error": "Detailed health check failed",
                "timestamp": logger._get_timestamp(),
                "correlation_id": correlation_id
            },
            status_code=500
        )

@router.get("/health/stats")
async def service_statistics(
    request: Request,
    service_client: ServiceClient = Depends(get_service_client),
    logger = Depends(get_logger)
) -> JSONResponse:
    """Advanced service statistics from connection pools, circuit breakers, and service discovery"""
    correlation_id = get_correlation_id()
    
    try:
        # Get comprehensive statistics from enhanced service client
        comprehensive_stats = await service_client.get_comprehensive_stats()
        
        response_data = {
            "timestamp": logger._get_timestamp(),
            "correlation_id": correlation_id,
            "service": request.app.state.settings.service_name,
            "statistics": comprehensive_stats
        }
        
        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error("Failed to retrieve service statistics",
                    error=str(e),
                    correlation_id=correlation_id)
        
        return JSONResponse(
            content={
                "status": "error",
                "error": "Failed to retrieve service statistics",
                "timestamp": logger._get_timestamp(),
                "correlation_id": correlation_id
            },
            status_code=500
        )