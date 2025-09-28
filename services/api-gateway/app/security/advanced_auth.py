"""
Advanced Authentication and Authorization System
Multi-layer security with JWT, OAuth2, API keys, and role-based access control
"""
import time
import hashlib
import secrets
import hmac
from typing import Optional, Dict, List, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import jwt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from passlib.context import CryptContext
from passlib.hash import bcrypt

from app.core.config import Settings
from shared.monitoring.structured_logger import StructuredLogger

class AuthMethod(str, Enum):
    """Authentication methods"""
    JWT = "jwt"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    CERTIFICATE = "certificate"
    MULTI_FACTOR = "mfa"

class UserRole(str, Enum):
    """User roles for RBAC"""
    ADMIN = "admin"
    USER = "user"
    SERVICE = "service"
    GUEST = "guest"
    DEVELOPER = "developer"
    ANALYST = "analyst"

class Permission(str, Enum):
    """System permissions"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    EXECUTE = "execute"
    MONITOR = "monitor"
    CONFIG = "config"

class SecurityLevel(str, Enum):
    """Security levels for different operations"""
    PUBLIC = "public"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class AuthConfig:
    """Authentication configuration"""
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    api_key_length: int = 32
    password_min_length: int = 8
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15
    require_mfa: bool = False
    session_timeout_minutes: int = 60
    enable_password_rotation: bool = True
    password_rotation_days: int = 90

@dataclass
class User:
    """User model for authentication"""
    user_id: str
    username: str
    email: str
    hashed_password: str
    roles: List[UserRole] = field(default_factory=list)
    permissions: List[Permission] = field(default_factory=list)
    is_active: bool = True
    is_verified: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    login_attempts: int = 0
    locked_until: Optional[datetime] = None
    mfa_enabled: bool = False
    mfa_secret: Optional[str] = None
    api_keys: List[str] = field(default_factory=list)

@dataclass
class APIKey:
    """API Key model"""
    key_id: str
    key_hash: str
    name: str
    user_id: str
    scopes: List[str] = field(default_factory=list)
    rate_limit: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    is_active: bool = True

@dataclass
class AuthContext:
    """Authentication context for requests"""
    user_id: str
    username: str
    roles: List[UserRole]
    permissions: List[Permission]
    auth_method: AuthMethod
    session_id: Optional[str] = None
    api_key_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    authenticated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None

class AdvancedAuthManager:
    """Advanced authentication and authorization manager"""
    
    def __init__(self, settings: Settings, logger: StructuredLogger, config: Optional[AuthConfig] = None):
        self.settings = settings
        self.logger = logger
        self.config = config or AuthConfig(jwt_secret_key=settings.jwt_secret_key)
        
        # Password hashing
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        # JWT security
        self.security = HTTPBearer(auto_error=False)
        self.api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
        
        # In-memory stores (in production, use proper database)
        self.users: Dict[str, User] = {}
        self.api_keys: Dict[str, APIKey] = {}
        self.active_sessions: Dict[str, AuthContext] = {}
        self.revoked_tokens: set = set()
        
        # Rate limiting and security
        self.login_attempts: Dict[str, List[datetime]] = {}
        self.failed_attempts: Dict[str, int] = {}
        
        # Role-based permissions
        self.role_permissions = self._initialize_role_permissions()
        
        self.logger.info("Advanced authentication manager initialized",
                        jwt_algorithm=self.config.jwt_algorithm,
                        mfa_required=self.config.require_mfa)
    
    def _initialize_role_permissions(self) -> Dict[UserRole, List[Permission]]:
        """Initialize default role-based permissions"""
        return {
            UserRole.ADMIN: [
                Permission.READ, Permission.WRITE, Permission.DELETE,
                Permission.ADMIN, Permission.EXECUTE, Permission.MONITOR, Permission.CONFIG
            ],
            UserRole.DEVELOPER: [
                Permission.READ, Permission.WRITE, Permission.EXECUTE, Permission.MONITOR
            ],
            UserRole.ANALYST: [
                Permission.READ, Permission.MONITOR
            ],
            UserRole.USER: [
                Permission.READ, Permission.WRITE
            ],
            UserRole.SERVICE: [
                Permission.READ, Permission.WRITE, Permission.EXECUTE
            ],
            UserRole.GUEST: [
                Permission.READ
            ]
        }
    
    # Password Management
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        return self.pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def validate_password_strength(self, password: str) -> Tuple[bool, List[str]]:
        """Validate password strength"""
        issues = []
        
        if len(password) < self.config.password_min_length:
            issues.append(f"Password must be at least {self.config.password_min_length} characters long")
        
        if not any(c.isupper() for c in password):
            issues.append("Password must contain at least one uppercase letter")
        
        if not any(c.islower() for c in password):
            issues.append("Password must contain at least one lowercase letter")
        
        if not any(c.isdigit() for c in password):
            issues.append("Password must contain at least one number")
        
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            issues.append("Password must contain at least one special character")
        
        return len(issues) == 0, issues
    
    # User Management
    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        roles: List[UserRole] = None,
        require_verification: bool = True
    ) -> User:
        """Create new user with validation"""
        roles = roles or [UserRole.USER]
        
        # Validate password strength
        is_strong, issues = self.validate_password_strength(password)
        if not is_strong:
            raise HTTPException(status_code=400, detail=f"Password validation failed: {', '.join(issues)}")
        
        # Check if user already exists
        if any(u.username == username or u.email == email for u in self.users.values()):
            raise HTTPException(status_code=400, detail="User already exists")
        
        # Create user
        user_id = secrets.token_urlsafe(16)
        hashed_password = self.hash_password(password)
        
        # Get permissions from roles
        permissions = list(set(
            perm for role in roles 
            for perm in self.role_permissions.get(role, [])
        ))
        
        user = User(
            user_id=user_id,
            username=username,
            email=email,
            hashed_password=hashed_password,
            roles=roles,
            permissions=permissions,
            is_verified=not require_verification
        )
        
        self.users[user_id] = user
        
        self.logger.info("User created",
                        user_id=user_id,
                        username=username,
                        roles=[r.value for r in roles])
        
        return user
    
    async def authenticate_user(self, username: str, password: str, ip_address: str = None) -> Optional[User]:
        """Authenticate user with rate limiting and lockout"""
        
        # Check rate limiting
        current_time = datetime.utcnow()
        user_key = f"{username}:{ip_address}" if ip_address else username
        
        # Clean old attempts
        if user_key in self.login_attempts:
            self.login_attempts[user_key] = [
                attempt for attempt in self.login_attempts[user_key]
                if current_time - attempt < timedelta(hours=1)
            ]
        
        # Check if too many attempts
        recent_attempts = self.login_attempts.get(user_key, [])
        if len(recent_attempts) >= self.config.max_login_attempts:
            raise HTTPException(
                status_code=429,
                detail=f"Too many login attempts. Try again in {self.config.lockout_duration_minutes} minutes"
            )
        
        # Find user
        user = None
        for u in self.users.values():
            if u.username == username or u.email == username:
                user = u
                break
        
        if not user:
            # Record failed attempt
            if user_key not in self.login_attempts:
                self.login_attempts[user_key] = []
            self.login_attempts[user_key].append(current_time)
            
            self.logger.warning("Authentication failed - user not found",
                              username=username,
                              ip_address=ip_address)
            return None
        
        # Check if user is locked
        if user.locked_until and current_time < user.locked_until:
            raise HTTPException(
                status_code=423,
                detail=f"Account is locked until {user.locked_until}"
            )
        
        # Verify password
        if not self.verify_password(password, user.hashed_password):
            # Record failed attempt
            if user_key not in self.login_attempts:
                self.login_attempts[user_key] = []
            self.login_attempts[user_key].append(current_time)
            
            user.login_attempts += 1
            
            # Lock user if too many attempts
            if user.login_attempts >= self.config.max_login_attempts:
                user.locked_until = current_time + timedelta(minutes=self.config.lockout_duration_minutes)
                self.logger.warning("User account locked due to failed attempts",
                                  user_id=user.user_id,
                                  username=username)
            
            self.logger.warning("Authentication failed - invalid password",
                              user_id=user.user_id,
                              username=username,
                              ip_address=ip_address)
            return None
        
        # Check if user is active and verified
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account is disabled")
        
        if not user.is_verified:
            raise HTTPException(status_code=403, detail="Account is not verified")
        
        # Successful authentication
        user.last_login = current_time
        user.login_attempts = 0
        user.locked_until = None
        
        # Clear failed attempts
        if user_key in self.login_attempts:
            del self.login_attempts[user_key]
        
        self.logger.info("User authenticated successfully",
                        user_id=user.user_id,
                        username=username,
                        ip_address=ip_address)
        
        return user
    
    # JWT Token Management
    def create_access_token(self, user: User, additional_claims: Dict[str, Any] = None) -> str:
        """Create JWT access token"""
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=self.config.jwt_access_token_expire_minutes)
        
        payload = {
            "sub": user.user_id,
            "username": user.username,
            "email": user.email,
            "roles": [role.value for role in user.roles],
            "permissions": [perm.value for perm in user.permissions],
            "iat": now.timestamp(),
            "exp": expires_at.timestamp(),
            "type": "access"
        }
        
        if additional_claims:
            payload.update(additional_claims)
        
        token = jwt.encode(payload, self.config.jwt_secret_key, algorithm=self.config.jwt_algorithm)
        
        self.logger.debug("Access token created",
                         user_id=user.user_id,
                         expires_at=expires_at.isoformat())
        
        return token
    
    def create_refresh_token(self, user: User) -> str:
        """Create JWT refresh token"""
        now = datetime.utcnow()
        expires_at = now + timedelta(days=self.config.jwt_refresh_token_expire_days)
        
        payload = {
            "sub": user.user_id,
            "iat": now.timestamp(),
            "exp": expires_at.timestamp(),
            "type": "refresh"
        }
        
        token = jwt.encode(payload, self.config.jwt_secret_key, algorithm=self.config.jwt_algorithm)
        
        self.logger.debug("Refresh token created",
                         user_id=user.user_id,
                         expires_at=expires_at.isoformat())
        
        return token
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode JWT token"""
        try:
            # Check if token is revoked
            if token in self.revoked_tokens:
                self.logger.warning("Attempt to use revoked token")
                return None
            
            payload = jwt.decode(
                token,
                self.config.jwt_secret_key,
                algorithms=[self.config.jwt_algorithm]
            )
            
            return payload
            
        except jwt.ExpiredSignatureError:
            self.logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            self.logger.warning("Invalid token", error=str(e))
            return None
    
    def revoke_token(self, token: str):
        """Revoke a token"""
        self.revoked_tokens.add(token)
        self.logger.info("Token revoked")
    
    # API Key Management
    def generate_api_key(self, user_id: str, name: str, scopes: List[str] = None, expires_in_days: int = None) -> APIKey:
        """Generate new API key"""
        key_id = secrets.token_urlsafe(16)
        raw_key = secrets.token_urlsafe(self.config.api_key_length)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            name=name,
            user_id=user_id,
            scopes=scopes or [],
            expires_at=expires_at
        )
        
        self.api_keys[key_id] = api_key
        
        # Add to user's API keys
        if user_id in self.users:
            self.users[user_id].api_keys.append(key_id)
        
        self.logger.info("API key generated",
                        key_id=key_id,
                        user_id=user_id,
                        name=name,
                        scopes=scopes)
        
        # Return the raw key only once
        api_key.raw_key = raw_key
        return api_key
    
    def verify_api_key(self, raw_key: str) -> Optional[APIKey]:
        """Verify API key"""
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        for api_key in self.api_keys.values():
            if api_key.key_hash == key_hash and api_key.is_active:
                # Check expiration
                if api_key.expires_at and datetime.utcnow() > api_key.expires_at:
                    self.logger.warning("API key expired", key_id=api_key.key_id)
                    return None
                
                # Update last used
                api_key.last_used = datetime.utcnow()
                
                self.logger.debug("API key verified", key_id=api_key.key_id)
                return api_key
        
        self.logger.warning("Invalid API key attempted")
        return None
    
    # Authorization
    def check_permission(self, auth_context: AuthContext, required_permission: Permission) -> bool:
        """Check if user has required permission"""
        return required_permission in auth_context.permissions
    
    def check_role(self, auth_context: AuthContext, required_role: UserRole) -> bool:
        """Check if user has required role"""
        return required_role in auth_context.roles
    
    def check_scope(self, api_key: APIKey, required_scope: str) -> bool:
        """Check if API key has required scope"""
        return required_scope in api_key.scopes
    
    # Request Authentication
    async def authenticate_request(self, request: Request) -> Optional[AuthContext]:
        """Authenticate incoming request"""
        # Try JWT authentication first
        auth_context = await self._authenticate_jwt(request)
        if auth_context:
            return auth_context
        
        # Try API key authentication
        auth_context = await self._authenticate_api_key(request)
        if auth_context:
            return auth_context
        
        return None
    
    async def _authenticate_jwt(self, request: Request) -> Optional[AuthContext]:
        """Authenticate request using JWT"""
        try:
            credentials: HTTPAuthorizationCredentials = await self.security(request)
            if not credentials:
                return None
            
            token = credentials.credentials
            payload = self.verify_token(token)
            if not payload:
                return None
            
            # Get user
            user_id = payload.get("sub")
            user = self.users.get(user_id)
            if not user or not user.is_active:
                return None
            
            # Create auth context
            auth_context = AuthContext(
                user_id=user.user_id,
                username=user.username,
                roles=[UserRole(role) for role in payload.get("roles", [])],
                permissions=[Permission(perm) for perm in payload.get("permissions", [])],
                auth_method=AuthMethod.JWT,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                expires_at=datetime.fromtimestamp(payload.get("exp", 0))
            )
            
            return auth_context
            
        except Exception as e:
            self.logger.warning("JWT authentication failed", error=str(e))
            return None
    
    async def _authenticate_api_key(self, request: Request) -> Optional[AuthContext]:
        """Authenticate request using API key"""
        try:
            api_key_value = await self.api_key_header(request)
            if not api_key_value:
                return None
            
            api_key = self.verify_api_key(api_key_value)
            if not api_key:
                return None
            
            # Get user
            user = self.users.get(api_key.user_id)
            if not user or not user.is_active:
                return None
            
            # Create auth context
            auth_context = AuthContext(
                user_id=user.user_id,
                username=user.username,
                roles=user.roles,
                permissions=user.permissions,
                auth_method=AuthMethod.API_KEY,
                api_key_id=api_key.key_id,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent")
            )
            
            return auth_context
            
        except Exception as e:
            self.logger.warning("API key authentication failed", error=str(e))
            return None
    
    # Security Utilities
    def generate_secure_token(self, length: int = 32) -> str:
        """Generate cryptographically secure token"""
        return secrets.token_urlsafe(length)
    
    def constant_time_compare(self, a: str, b: str) -> bool:
        """Constant time string comparison to prevent timing attacks"""
        return hmac.compare_digest(a.encode(), b.encode())
    
    def get_password_reset_token(self, user_id: str) -> str:
        """Generate password reset token"""
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=1)  # 1 hour expiry
        
        payload = {
            "sub": user_id,
            "type": "password_reset",
            "iat": now.timestamp(),
            "exp": expires_at.timestamp()
        }
        
        token = jwt.encode(payload, self.config.jwt_secret_key, algorithm=self.config.jwt_algorithm)
        
        self.logger.info("Password reset token generated", user_id=user_id)
        return token
    
    def verify_password_reset_token(self, token: str) -> Optional[str]:
        """Verify password reset token and return user_id"""
        try:
            payload = jwt.decode(
                token,
                self.config.jwt_secret_key,
                algorithms=[self.config.jwt_algorithm]
            )
            
            if payload.get("type") != "password_reset":
                return None
            
            return payload.get("sub")
        except jwt.InvalidTokenError:
            return None
    
    async def change_password(self, user_id: str, old_password: str, new_password: str) -> bool:
        """Change user password with validation"""
        user = self.users.get(user_id)
        if not user:
            return False
        
        # Verify old password
        if not self.verify_password(old_password, user.hashed_password):
            self.logger.warning("Password change failed - invalid old password", user_id=user_id)
            return False
        
        # Validate new password strength
        is_strong, issues = self.validate_password_strength(new_password)
        if not is_strong:
            raise HTTPException(status_code=400, detail=f"Password validation failed: {', '.join(issues)}")
        
        # Update password
        user.hashed_password = self.hash_password(new_password)
        
        self.logger.info("Password changed successfully", user_id=user_id)
        return True
    
    # Session Management
    def create_session(self, auth_context: AuthContext) -> str:
        """Create authenticated session"""
        session_id = secrets.token_urlsafe(32)
        auth_context.session_id = session_id
        auth_context.expires_at = datetime.utcnow() + timedelta(minutes=self.config.session_timeout_minutes)
        
        self.active_sessions[session_id] = auth_context
        
        self.logger.info("Session created",
                        session_id=session_id,
                        user_id=auth_context.user_id)
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[AuthContext]:
        """Get active session"""
        session = self.active_sessions.get(session_id)
        if not session:
            return None
        
        # Check expiration
        if session.expires_at and datetime.utcnow() > session.expires_at:
            self.revoke_session(session_id)
            return None
        
        return session
    
    def revoke_session(self, session_id: str):
        """Revoke session"""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            del self.active_sessions[session_id]
            
            self.logger.info("Session revoked",
                           session_id=session_id,
                           user_id=session.user_id)
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        current_time = datetime.utcnow()
        expired_sessions = [
            session_id for session_id, session in self.active_sessions.items()
            if session.expires_at and current_time > session.expires_at
        ]
        
        for session_id in expired_sessions:
            self.revoke_session(session_id)
        
        if expired_sessions:
            self.logger.info("Expired sessions cleaned up", count=len(expired_sessions))


# Dependency injection for FastAPI
def get_auth_manager():
    """Get authentication manager instance"""
    # This would be injected via dependency injection in real application
    pass

# Security decorators and dependencies will be implemented in separate files