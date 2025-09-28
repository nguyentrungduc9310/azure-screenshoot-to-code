"""
Request Validation Middleware
Handles request validation, logging, and correlation tracking for image generation
"""
import time
import json
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

from shared.monitoring.correlation import get_correlation_id, set_correlation_id

class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Middleware for request validation and logging"""
    
    def __init__(self, app, max_request_size: int = 100 * 1024 * 1024):  # 100MB default for images
        super().__init__(app)
        self.max_request_size = max_request_size
        self.logger = structlog.get_logger()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and response"""
        start_time = time.time()
        correlation_id = get_correlation_id()
        set_correlation_id(correlation_id)
        
        # Log incoming request
        self.logger.info("Request received",
                        method=request.method,
                        path=request.url.path,
                        client=request.client.host if request.client else "unknown",
                        correlation_id=correlation_id)
        
        try:
            # Validate request size
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > self.max_request_size:
                self.logger.warning("Request too large",
                                  content_length=content_length,
                                  max_size=self.max_request_size,
                                  correlation_id=correlation_id)
                return JSONResponse(
                    status_code=413,
                    content={
                        "success": False,
                        "error": "request_too_large",
                        "message": f"Request size exceeds {self.max_request_size} bytes",
                        "correlation_id": correlation_id
                    }
                )
            
            # Validate content type for POST/PUT requests (excluding file uploads)
            if request.method in ["POST", "PUT"]:
                content_type = request.headers.get("content-type", "")
                
                # Allow multipart form data for file uploads
                if not (content_type.startswith("application/json") or 
                       content_type.startswith("multipart/form-data")):
                    self.logger.warning("Invalid content type",
                                      content_type=content_type,
                                      correlation_id=correlation_id)
                    return JSONResponse(
                        status_code=415,
                        content={
                            "success": False,
                            "error": "unsupported_media_type",
                            "message": "Content-Type must be application/json or multipart/form-data",
                            "correlation_id": correlation_id
                        }
                    )
            
            # Process request
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-Process-Time"] = str(process_time)
            
            # Log successful response
            self.logger.info("Request completed",
                           method=request.method,
                           path=request.url.path,
                           status_code=response.status_code,
                           process_time_seconds=process_time,
                           correlation_id=correlation_id)
            
            return response
            
        except Exception as e:
            # Calculate processing time for error cases
            process_time = time.time() - start_time
            
            # Log error
            self.logger.error("Request processing failed",
                            method=request.method,
                            path=request.url.path,
                            error=str(e),
                            process_time_seconds=process_time,
                            correlation_id=correlation_id,
                            exc_info=e)
            
            # Return error response
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": "internal_server_error",
                    "message": "An internal server error occurred",
                    "correlation_id": correlation_id
                },
                headers={
                    "X-Correlation-ID": correlation_id,
                    "X-Process-Time": str(process_time)
                }
            )