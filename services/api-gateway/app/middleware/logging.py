"""
Logging Middleware
Request/response logging with performance metrics
"""
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from shared.monitoring.structured_logger import StructuredLogger
from shared.monitoring.correlation import get_correlation_id

class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging"""
    
    def __init__(self, app, logger: StructuredLogger):
        super().__init__(app)
        self.logger = logger
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        correlation_id = get_correlation_id()
        
        # Log incoming request
        self.logger.info("Incoming request",
                        method=request.method,
                        path=request.url.path,
                        query_params=str(request.query_params),
                        client_ip=self._get_client_ip(request),
                        user_agent=request.headers.get("User-Agent", ""),
                        correlation_id=correlation_id)
        
        # Process request
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            
            # Log response
            self.logger.info("Request completed",
                           method=request.method,
                           path=request.url.path,
                           status_code=response.status_code,
                           duration_ms=round(duration_ms, 2),
                           correlation_id=correlation_id)
            
            # Add performance headers
            response.headers["X-Response-Time"] = f"{round(duration_ms, 2)}ms"
            
            return response
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            # Log error
            self.logger.error("Request failed",
                            method=request.method,
                            path=request.url.path,
                            error=str(e),
                            error_type=type(e).__name__,
                            duration_ms=round(duration_ms, 2),
                            correlation_id=correlation_id)
            
            raise
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        # Check for forwarded headers (behind proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return "unknown"