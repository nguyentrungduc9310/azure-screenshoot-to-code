"""
Image validation middleware for request preprocessing
"""
import time
from fastapi import Request, HTTPException, status
from fastapi.middleware.base import BaseHTTPMiddleware
from typing import Any
import json

class ImageValidationMiddleware(BaseHTTPMiddleware):
    """Middleware for preprocessing and validating image requests"""
    
    # Maximum request size (50MB for image uploads)
    MAX_REQUEST_SIZE = 50 * 1024 * 1024
    
    # Endpoints that handle image data
    IMAGE_ENDPOINTS = ["/api/v1/process", "/api/v1/validate", "/api/v1/analyze", "/api/v1/thumbnail"]
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Check request size for image endpoints
        if request.url.path in self.IMAGE_ENDPOINTS:
            content_length = request.headers.get('content-length')
            if content_length and int(content_length) > self.MAX_REQUEST_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Request size exceeds maximum allowed size of {self.MAX_REQUEST_SIZE} bytes"
                )
            
            # Validate content type
            content_type = request.headers.get('content-type', '')
            if not content_type.startswith('application/json'):
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="Content type must be application/json for image processing endpoints"
                )
        
        # Process request
        response = await call_next(request)
        
        # Add processing time header
        process_time = time.time() - start_time
        response.headers["X-Image-Process-Time"] = str(round(process_time * 1000, 2))
        
        return response