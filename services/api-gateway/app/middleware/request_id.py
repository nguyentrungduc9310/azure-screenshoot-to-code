"""
Request ID Middleware
Generates and tracks unique request IDs for correlation
"""
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from shared.monitoring.correlation import set_correlation_id, get_correlation_id

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to generate and track request IDs"""
    
    def __init__(self, app):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get or generate correlation ID
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        
        # Set correlation ID for this request context
        set_correlation_id(correlation_id)
        
        # Add correlation ID to request state
        request.state.correlation_id = correlation_id
        
        # Process request
        response = await call_next(request)
        
        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id
        
        return response