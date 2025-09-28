"""
Dependency Injection for FastAPI
Provides dependencies for security, authentication, and other components
"""
from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.security.advanced_auth import AdvancedAuthManager, AuthContext
from app.security.security_scanner import SecurityScanner
from app.security.compliance import ComplianceManager
from app.security.api_key_manager import AdvancedAPIKeyManager

# Security scheme
security = HTTPBearer(auto_error=False)


def get_auth_manager(request: Request) -> AdvancedAuthManager:
    """Get authentication manager from app state"""
    return request.app.state.auth_manager


def get_security_scanner(request: Request) -> SecurityScanner:
    """Get security scanner from app state"""
    return request.app.state.security_scanner


def get_compliance_manager(request: Request) -> ComplianceManager:
    """Get compliance manager from app state"""
    return request.app.state.compliance_manager


def get_api_key_manager(request: Request) -> AdvancedAPIKeyManager:
    """Get API key manager from app state"""
    return request.app.state.api_key_manager


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    auth_manager: AdvancedAuthManager = Depends(get_auth_manager)
) -> AuthContext:
    """Get current authenticated user"""
    
    # Try to authenticate the request
    auth_context = await auth_manager.authenticate_request(request)
    
    if not auth_context:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return auth_context


async def get_current_active_user(
    auth_context: AuthContext = Depends(get_current_user),
    auth_manager: AdvancedAuthManager = Depends(get_auth_manager)
) -> AuthContext:
    """Get current active user"""
    
    # Get user from auth manager
    user = auth_manager.users.get(auth_context.user_id)
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    return auth_context


async def get_admin_user(
    auth_context: AuthContext = Depends(get_current_active_user),
    auth_manager: AdvancedAuthManager = Depends(get_auth_manager)
) -> AuthContext:
    """Get current user with admin permissions"""
    
    from app.security.advanced_auth import Permission
    
    if not auth_manager.check_permission(auth_context, Permission.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permissions required"
        )
    
    return auth_context


# Add to AdvancedAuthManager for convenience
AdvancedAuthManager.get_current_user = staticmethod(get_current_user)
AdvancedAuthManager.get_current_active_user = staticmethod(get_current_active_user)
AdvancedAuthManager.get_admin_user = staticmethod(get_admin_user)