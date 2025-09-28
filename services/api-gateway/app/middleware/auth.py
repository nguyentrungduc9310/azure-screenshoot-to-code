"""
Authentication Middleware
JWT token validation and user authentication
"""
import jwt
from typing import Callable, Optional, Dict, Any

from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import Settings
from shared.monitoring.correlation import get_correlation_id

class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware for JWT authentication"""
    
    # Public endpoints that don't require authentication
    PUBLIC_ENDPOINTS = {
        "/",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/health/live",
        "/health/ready"
    }
    
    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self.settings = settings
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip authentication for public endpoints
        if not self.settings.enable_authentication or self._is_public_endpoint(request.url.path):
            return await call_next(request)
        
        # Extract and validate JWT token
        try:
            token = self._extract_token(request)
            if not token:
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            # Validate token and extract user info
            user_info = await self._validate_token(token)
            
            # Add user info to request state
            request.state.user_id = user_info.get("sub")
            request.state.user_email = user_info.get("email")
            request.state.user_roles = user_info.get("roles", [])
            request.state.tenant_id = user_info.get("tenant_id")
            
        except HTTPException:
            raise
        except Exception as e:
            correlation_id = get_correlation_id()
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication token",
                headers={
                    "WWW-Authenticate": "Bearer",
                    "X-Correlation-ID": correlation_id
                }
            )
        
        # Process request
        response = await call_next(request)
        return response
    
    def _is_public_endpoint(self, path: str) -> bool:
        """Check if endpoint is public (doesn't require authentication)"""
        # Remove API prefix for comparison
        clean_path = path.replace(self.settings.api_prefix, "").rstrip("/")
        if not clean_path:
            clean_path = "/"
        
        return clean_path in self.PUBLIC_ENDPOINTS or clean_path.startswith("/health")
    
    def _extract_token(self, request: Request) -> Optional[str]:
        """Extract JWT token from request headers"""
        authorization = request.headers.get("Authorization")
        if not authorization:
            return None
        
        # Check for Bearer token format
        if not authorization.startswith("Bearer "):
            return None
        
        return authorization[7:]  # Remove "Bearer " prefix
    
    async def _validate_token(self, token: str) -> Dict[str, Any]:
        """Validate JWT token and return user information"""
        try:
            # For Azure AD tokens, we might need to validate against Azure AD
            # For now, using simple JWT validation
            payload = jwt.decode(
                token,
                self.settings.jwt_secret,
                algorithms=[self.settings.jwt_algorithm]
            )
            
            # Check token expiration
            current_time = jwt.datetime.datetime.utcnow().timestamp()
            if payload.get("exp", 0) < current_time:
                raise HTTPException(status_code=401, detail="Token expired")
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
        except Exception:
            raise HTTPException(status_code=401, detail="Token validation failed")
    
    async def _validate_azure_ad_token(self, token: str) -> Dict[str, Any]:
        """Validate Azure AD token (future implementation)"""
        # This would integrate with Azure AD for token validation
        # For now, return mock user info for development
        if self.settings.is_development:
            return {
                "sub": "dev-user-123",
                "email": "dev@example.com",
                "roles": ["user"],
                "tenant_id": "dev-tenant"
            }
        
        # In production, implement proper Azure AD validation
        raise HTTPException(status_code=401, detail="Azure AD validation not implemented")