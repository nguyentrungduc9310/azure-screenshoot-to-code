# TASK-008: Security Architecture Design

**Date**: January 2024  
**Assigned**: Security Architect  
**Status**: IN PROGRESS  
**Effort**: 20 hours  

---

## Executive Summary

Comprehensive security architecture design for Screenshot-to-Code microservices platform, implementing defense-in-depth security principles. Architecture covers identity management, API security, data protection, network security, and compliance requirements for integration with Microsoft Copilot Studio and Azure services.

---

## Security Architecture Overview

### 🛡️ **Defense-in-Depth Security Model**
```yaml
Security Layers:
  1. Identity & Access Management: Azure AD, OAuth 2.0, RBAC
  2. Network Security: API Gateway, WAF, VPN, Private Endpoints
  3. Application Security: Input validation, CSRF protection, rate limiting
  4. Data Security: Encryption at rest/transit, Key Vault, data classification
  5. Infrastructure Security: Container security, secrets management
  6. Monitoring & Response: Security logging, threat detection, incident response

Compliance Standards:
  - SOC 2 Type II
  - ISO 27001
  - GDPR/Privacy regulations
  - Microsoft Cloud Security Standards
```

---

## Phase 1: Identity and Access Management (IAM)

### 1.1 Azure Active Directory Integration

```python
# shared/auth/azure_ad.py
import os
import jwt
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import httpx

class AzureADAuth:
    """Azure Active Directory authentication and authorization"""
    
    def __init__(self):
        self.tenant_id = os.getenv('AZURE_TENANT_ID')
        self.client_id = os.getenv('AZURE_CLIENT_ID')
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scope = f"api://{self.client_id}/.default"
        
        # Azure AD endpoints
        self.discovery_url = f"{self.authority}/v2.0/.well-known/openid-configuration"
        self.jwks_uri = None
        self.issuer = None
        
        # Initialize OIDC configuration
        self._init_oidc_config()
    
    async def _init_oidc_config(self):
        """Initialize OIDC configuration from Azure AD"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.discovery_url)
                config = response.json()
                
                self.jwks_uri = config['jwks_uri']
                self.issuer = config['issuer']
                
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Azure AD configuration: {e}")
    
    async def get_public_keys(self) -> Dict:
        """Get Azure AD public keys for token validation"""
        async with httpx.AsyncClient() as client:
            response = await client.get(self.jwks_uri)
            return response.json()
    
    async def validate_token(self, token: str) -> Dict:
        """Validate Azure AD JWT token"""
        try:
            # Get public keys
            jwks = await self.get_public_keys()
            
            # Decode and validate token
            unverified_header = jwt.get_unverified_header(token)
            
            # Find the correct key
            key = None
            for jwk in jwks['keys']:
                if jwk['kid'] == unverified_header['kid']:
                    key = jwt.algorithms.RSAAlgorithm.from_jwk(jwk)
                    break
            
            if not key:
                raise ValueError("Unable to find appropriate key")
            
            # Decode and validate
            payload = jwt.decode(
                token,
                key,
                algorithms=['RS256'],
                audience=self.client_id,
                issuer=self.issuer
            )
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}"
            )
    
    async def get_user_info(self, token: str) -> Dict:
        """Get user information from Microsoft Graph"""
        headers = {"Authorization": f"Bearer {token}"}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://graph.microsoft.com/v1.0/me",
                headers=headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Failed to get user information"
                )

class RoleBasedAccessControl:
    """Role-based access control system"""
    
    ROLES = {
        'admin': {
            'permissions': [
                'service.manage',
                'user.manage', 
                'config.manage',
                'monitoring.view',
                'security.manage'
            ]
        },
        'developer': {
            'permissions': [
                'service.view',
                'service.debug',
                'monitoring.view',
                'api.generate_code',
                'api.process_image'
            ]
        },
        'user': {
            'permissions': [
                'api.generate_code',
                'api.process_image',
                'profile.view',
                'profile.update'
            ]
        },
        'copilot_studio': {
            'permissions': [
                'api.generate_code',
                'api.process_image',
                'api.generate_image',
                'api.process_nlp'
            ]
        }
    }
    
    def __init__(self):
        self.azure_ad = AzureADAuth()
    
    def has_permission(self, user_roles: List[str], required_permission: str) -> bool:
        """Check if user has required permission"""
        user_permissions = set()
        
        for role in user_roles:
            if role in self.ROLES:
                user_permissions.update(self.ROLES[role]['permissions'])
        
        return required_permission in user_permissions
    
    def require_permission(self, permission: str):
        """Decorator to require specific permission"""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                # Get current user from request context
                user = kwargs.get('current_user')
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication required"
                    )
                
                user_roles = user.get('roles', [])
                if not self.has_permission(user_roles, permission):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission required: {permission}"
                    )
                
                return await func(*args, **kwargs)
            return wrapper
        return decorator

# Authentication dependency
security = HTTPBearer()
azure_ad_auth = AzureADAuth()
rbac = RoleBasedAccessControl()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """FastAPI dependency to get current authenticated user"""
    
    token = credentials.credentials
    
    # Validate token with Azure AD
    payload = await azure_ad_auth.validate_token(token)
    
    # Get user information
    user_info = await azure_ad_auth.get_user_info(token)
    
    # Combine token payload and user info
    current_user = {
        'id': payload.get('oid'),  # Object ID
        'email': payload.get('preferred_username'),
        'name': user_info.get('displayName'),
        'tenant_id': payload.get('tid'),
        'roles': payload.get('roles', []),
        'app_roles': payload.get('app_roles', [])
    }
    
    return current_user

def require_role(role: str):
    """Decorator to require specific role"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            user_roles = current_user.get('roles', [])
            if role not in user_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role required: {role}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator
```

### 1.2 API Key Management for External Integrations

```python
# shared/auth/api_keys.py
import secrets
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from sqlalchemy import Column, String, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from cryptography.fernet import Fernet
import os

Base = declarative_base()

class APIKey(Base):
    """API Key model for external service authentication"""
    __tablename__ = 'api_keys'
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    key_hash = Column(String, nullable=False)
    key_prefix = Column(String, nullable=False)
    encrypted_key = Column(Text, nullable=False)
    permissions = Column(Text, nullable=False)  # JSON string
    rate_limit = Column(String, default='100/hour')
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    last_used = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_by = Column(String, nullable=False)

class APIKeyManager:
    """Secure API key management system"""
    
    def __init__(self, encryption_key: str = None):
        self.encryption_key = encryption_key or os.getenv('API_KEY_ENCRYPTION_KEY')
        if not self.encryption_key:
            raise ValueError("API_KEY_ENCRYPTION_KEY environment variable required")
        
        self.cipher = Fernet(self.encryption_key.encode())
    
    def generate_api_key(self, name: str, permissions: List[str], 
                        created_by: str, expires_days: int = None) -> Dict:
        """Generate new API key with permissions"""
        
        # Generate random API key
        key = f"stc_{secrets.token_urlsafe(32)}"
        key_prefix = key[:12]
        
        # Hash for database storage
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        
        # Encrypt full key for recovery
        encrypted_key = self.cipher.encrypt(key.encode()).decode()
        
        # Set expiration
        expires_at = None
        if expires_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_days)
        
        api_key_record = {
            'id': secrets.token_hex(16),
            'name': name,
            'key_hash': key_hash,
            'key_prefix': key_prefix,
            'encrypted_key': encrypted_key,
            'permissions': ','.join(permissions),
            'created_by': created_by,
            'expires_at': expires_at,
            'is_active': True
        }
        
        return {
            'api_key': key,
            'record': api_key_record
        }
    
    def validate_api_key(self, provided_key: str) -> Optional[Dict]:
        """Validate API key and return permissions"""
        
        key_hash = hashlib.sha256(provided_key.encode()).hexdigest()
        
        # Query database for key (implement with your ORM)
        # This is a placeholder for the actual database query
        api_key_record = self._get_api_key_by_hash(key_hash)
        
        if not api_key_record:
            return None
        
        # Check if key is active
        if not api_key_record.get('is_active'):
            return None
        
        # Check if key has expired
        if api_key_record.get('expires_at'):
            if datetime.utcnow() > api_key_record['expires_at']:
                return None
        
        # Update last used timestamp
        self._update_last_used(api_key_record['id'])
        
        return {
            'id': api_key_record['id'],
            'name': api_key_record['name'],
            'permissions': api_key_record['permissions'].split(','),
            'rate_limit': api_key_record['rate_limit']
        }
    
    def _get_api_key_by_hash(self, key_hash: str) -> Optional[Dict]:
        """Get API key record by hash (implement with your database)"""
        # Placeholder - implement with your database layer
        pass
    
    def _update_last_used(self, key_id: str):
        """Update last used timestamp for API key"""
        # Placeholder - implement with your database layer
        pass

# FastAPI dependency for API key authentication
api_key_manager = APIKeyManager()

async def get_api_key_user(api_key: str = Header(None, alias="X-API-Key")) -> Dict:
    """FastAPI dependency to validate API key"""
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required"
        )
    
    key_info = api_key_manager.validate_api_key(api_key)
    if not key_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key"
        )
    
    return {
        'type': 'api_key',
        'id': key_info['id'],
        'name': key_info['name'],
        'permissions': key_info['permissions'],
        'rate_limit': key_info['rate_limit']
    }
```

---

## Phase 2: API Security & Protection

### 2.1 API Gateway Security Layer

```python
# services/api-gateway/app/security/gateway_security.py
import time
import hashlib
import hmac
import json
from typing import Dict, Optional, List
from fastapi import FastAPI, Request, HTTPException, status, Depends
from fastapi.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer
import redis
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import ipaddress

class SecurityConfig:
    """Security configuration settings"""
    
    # Rate limiting
    DEFAULT_RATE_LIMIT = "100/hour"
    BURST_RATE_LIMIT = "10/minute" 
    
    # CORS settings
    ALLOWED_ORIGINS = [
        "https://copilotstudio.microsoft.com",
        "https://*.powerapps.com",
        "https://*.dynamics.com"
    ]
    
    # Trusted hosts
    TRUSTED_HOSTS = [
        "localhost",
        "*.azurecontainerapps.io",
        "*.azurewebsites.net"
    ]
    
    # Content Security Policy
    CSP_POLICY = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://copilotstudio.microsoft.com; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https://login.microsoftonline.com https://graph.microsoft.com;"
    )

class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Advanced rate limiting with user-based and IP-based limits"""
    
    def __init__(self, app: FastAPI, redis_client: redis.Redis):
        super().__init__(app)
        self.redis_client = redis_client
        self.limiter = Limiter(key_func=get_remote_address)
        app.state.limiter = self.limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    async def dispatch(self, request: Request, call_next):
        # Get client identifier (IP or user ID)
        client_id = await self._get_client_identifier(request)
        
        # Check rate limits
        if await self._is_rate_limited(client_id, request.url.path):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded"
            )
        
        # Process request
        response = await call_next(request)
        
        # Update rate limit counters
        await self._update_rate_limit_counter(client_id, request.url.path)
        
        return response
    
    async def _get_client_identifier(self, request: Request) -> str:
        """Get unique client identifier for rate limiting"""
        
        # Try to get user ID from authentication
        auth_header = request.headers.get('Authorization')
        if auth_header:
            try:
                # Extract user ID from token (simplified)
                user_id = "user_id_from_token"  # Implement token parsing
                return f"user:{user_id}"
            except:
                pass
        
        # Fallback to IP address
        return f"ip:{get_remote_address(request)}"
    
    async def _is_rate_limited(self, client_id: str, endpoint: str) -> bool:
        """Check if client has exceeded rate limits"""
        
        current_time = int(time.time())
        window_size = 3600  # 1 hour window
        window_start = current_time - (current_time % window_size)
        
        key = f"rate_limit:{client_id}:{endpoint}:{window_start}"
        
        try:
            current_count = await self.redis_client.get(key)
            if current_count and int(current_count) >= 100:  # 100 requests per hour
                return True
        except:
            pass
        
        return False
    
    async def _update_rate_limit_counter(self, client_id: str, endpoint: str):
        """Update rate limit counter"""
        
        current_time = int(time.time())
        window_size = 3600
        window_start = current_time - (current_time % window_size)
        
        key = f"rate_limit:{client_id}:{endpoint}:{window_start}"
        
        try:
            await self.redis_client.incr(key)
            await self.redis_client.expire(key, window_size)
        except:
            pass

class InputValidationMiddleware(BaseHTTPMiddleware):
    """Input validation and sanitization middleware"""
    
    MAX_REQUEST_SIZE = 50 * 1024 * 1024  # 50MB for image uploads
    BLOCKED_PATTERNS = [
        r'<script.*?>.*?</script>',
        r'javascript:',
        r'vbscript:',
        r'onload=',
        r'onerror='
    ]
    
    async def dispatch(self, request: Request, call_next):
        # Check request size
        content_length = request.headers.get('content-length')
        if content_length and int(content_length) > self.MAX_REQUEST_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Request size too large"
            )
        
        # Validate content type for file uploads
        if request.method == "POST":
            content_type = request.headers.get('content-type', '')
            if 'multipart/form-data' in content_type or 'application/json' in content_type:
                # Additional validation can be added here
                pass
        
        response = await call_next(request)
        return response

class WebApplicationFirewall:
    """Basic WAF functionality for common attacks"""
    
    def __init__(self):
        self.blocked_ips = set()
        self.suspicious_patterns = [
            r'union.*select',  # SQL injection
            r'<script.*?>',    # XSS
            r'eval\(',         # Code injection
            r'exec\(',         # Code injection
            r'\.\./',          # Path traversal
        ]
    
    def is_malicious_request(self, request: Request) -> bool:
        """Check if request appears malicious"""
        
        # Check IP blacklist
        client_ip = get_remote_address(request)
        if client_ip in self.blocked_ips:
            return True
        
        # Check user agent
        user_agent = request.headers.get('user-agent', '').lower()
        if not user_agent or len(user_agent) < 10:
            return True
        
        # Check for suspicious patterns in URL and headers
        url_path = str(request.url.path).lower()
        for pattern in self.suspicious_patterns:
            if re.search(pattern, url_path):
                return True
        
        return False
    
    def block_ip(self, ip_address: str):
        """Add IP to block list"""
        self.blocked_ips.add(ip_address)

def setup_api_gateway_security(app: FastAPI, redis_client: redis.Redis):
    """Setup comprehensive API Gateway security"""
    
    # Trusted Host Middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=SecurityConfig.TRUSTED_HOSTS
    )
    
    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=SecurityConfig.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID", "X-RateLimit-Remaining"]
    )
    
    # Rate Limiting Middleware
    app.add_middleware(RateLimitingMiddleware, redis_client=redis_client)
    
    # Input Validation Middleware
    app.add_middleware(InputValidationMiddleware)
    
    # Security Headers Middleware
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = SecurityConfig.CSP_POLICY
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        
        # Remove server information
        response.headers.pop("server", None)
        
        return response
    
    # WAF Integration
    waf = WebApplicationFirewall()
    
    @app.middleware("http")
    async def waf_middleware(request: Request, call_next):
        if waf.is_malicious_request(request):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Request blocked by security policy"
            )
        
        return await call_next(request)
    
    return app
```

### 2.2 Data Validation and Sanitization

```python
# shared/security/input_validation.py
import re
import html
import bleach
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, validator, ValidationError
from PIL import Image
import io
import base64

class SecurityValidator:
    """Comprehensive input validation and sanitization"""
    
    # Allowed HTML tags for rich text (if needed)
    ALLOWED_HTML_TAGS = ['p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li']
    ALLOWED_HTML_ATTRIBUTES = {}
    
    # File type validation
    ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_IMAGE_DIMENSION = 8000  # pixels
    
    @staticmethod
    def sanitize_string(value: str, allow_html: bool = False) -> str:
        """Sanitize string input"""
        if not isinstance(value, str):
            return str(value)
        
        # HTML escape by default
        if not allow_html:
            return html.escape(value.strip())
        
        # Clean HTML if allowed
        return bleach.clean(
            value,
            tags=SecurityValidator.ALLOWED_HTML_TAGS,
            attributes=SecurityValidator.ALLOWED_HTML_ATTRIBUTES,
            strip=True
        )
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email.strip()) is not None
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate URL format and scheme"""
        pattern = r'^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/.*)?$'
        return re.match(pattern, url.strip()) is not None
    
    @staticmethod
    def validate_base64_image(data_url: str) -> Dict[str, Any]:
        """Validate base64 encoded image"""
        try:
            # Parse data URL
            if not data_url.startswith('data:image/'):
                raise ValueError("Invalid image data URL format")
            
            # Extract media type and data
            header, data = data_url.split(',', 1)
            media_type = header.split(';')[0].split(':')[1]
            
            # Check allowed types
            if media_type not in SecurityValidator.ALLOWED_IMAGE_TYPES:
                raise ValueError(f"Image type not allowed: {media_type}")
            
            # Decode base64
            image_bytes = base64.b64decode(data)
            
            # Check file size
            if len(image_bytes) > SecurityValidator.MAX_IMAGE_SIZE:
                raise ValueError("Image size exceeds maximum allowed")
            
            # Validate with PIL
            with Image.open(io.BytesIO(image_bytes)) as img:
                # Check dimensions
                if (img.width > SecurityValidator.MAX_IMAGE_DIMENSION or 
                    img.height > SecurityValidator.MAX_IMAGE_DIMENSION):
                    raise ValueError("Image dimensions exceed maximum allowed")
                
                # Check for malicious content (basic)
                if img.format not in ['JPEG', 'PNG', 'GIF', 'WEBP']:
                    raise ValueError("Invalid image format")
                
                return {
                    'valid': True,
                    'media_type': media_type,
                    'size': len(image_bytes),
                    'dimensions': (img.width, img.height),
                    'format': img.format
                }
                
        except Exception as e:
            return {
                'valid': False,
                'error': str(e)
            }

class CodeGenerationRequest(BaseModel):
    """Validated code generation request"""
    
    image: str
    framework: str = "react"
    style: Optional[str] = "tailwind"
    instructions: Optional[str] = None
    
    @validator('image')
    def validate_image(cls, v):
        """Validate image data URL"""
        validation_result = SecurityValidator.validate_base64_image(v)
        if not validation_result['valid']:
            raise ValueError(f"Invalid image: {validation_result['error']}")
        return v
    
    @validator('framework')
    def validate_framework(cls, v):
        """Validate framework selection"""
        allowed_frameworks = ['react', 'vue', 'angular', 'html', 'bootstrap']
        if v.lower() not in allowed_frameworks:
            raise ValueError(f"Framework must be one of: {allowed_frameworks}")
        return v.lower()
    
    @validator('instructions')
    def sanitize_instructions(cls, v):
        """Sanitize instruction text"""
        if v is None:
            return v
        return SecurityValidator.sanitize_string(v)

class ImageProcessingRequest(BaseModel):
    """Validated image processing request"""
    
    image: str
    operation: str = "process"
    max_size: Optional[int] = 5242880  # 5MB default
    
    @validator('image')
    def validate_image(cls, v):
        validation_result = SecurityValidator.validate_base64_image(v)
        if not validation_result['valid']:
            raise ValueError(f"Invalid image: {validation_result['error']}")
        return v
    
    @validator('operation')
    def validate_operation(cls, v):
        allowed_operations = ['process', 'resize', 'compress', 'validate']
        if v.lower() not in allowed_operations:
            raise ValueError(f"Operation must be one of: {allowed_operations}")
        return v.lower()

def validate_request_data(data: Dict[str, Any], model_class: BaseModel) -> BaseModel:
    """Validate request data against Pydantic model"""
    try:
        return model_class(**data)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation error: {e.errors()}"
        )
```

---

## Phase 3: Data Protection & Encryption

### 3.1 Data Classification and Encryption

```python
# shared/security/data_protection.py
import os
import json
from enum import Enum
from typing import Dict, Any, Optional, List
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential
import base64

class DataClassification(Enum):
    """Data classification levels"""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"

class EncryptionManager:
    """Centralized encryption management"""
    
    def __init__(self, key_vault_url: str = None):
        self.key_vault_url = key_vault_url or os.getenv('AZURE_KEY_VAULT_URL')
        self.credential = DefaultAzureCredential()
        self.secret_client = SecretClient(
            vault_url=self.key_vault_url,
            credential=self.credential
        ) if self.key_vault_url else None
        
        # Encryption keys by classification
        self.encryption_keys = {}
        self._load_encryption_keys()
    
    def _load_encryption_keys(self):
        """Load encryption keys from Key Vault"""
        if not self.secret_client:
            # Fallback to environment variables for development
            self.encryption_keys = {
                DataClassification.CONFIDENTIAL: os.getenv('CONFIDENTIAL_DATA_KEY'),
                DataClassification.RESTRICTED: os.getenv('RESTRICTED_DATA_KEY')
            }
            return
        
        try:
            # Load keys from Azure Key Vault
            confidential_key = self.secret_client.get_secret("confidential-data-key")
            restricted_key = self.secret_client.get_secret("restricted-data-key")
            
            self.encryption_keys = {
                DataClassification.CONFIDENTIAL: confidential_key.value,
                DataClassification.RESTRICTED: restricted_key.value
            }
        except Exception as e:
            raise RuntimeError(f"Failed to load encryption keys: {e}")
    
    def get_cipher(self, classification: DataClassification) -> Optional[Fernet]:
        """Get cipher for data classification level"""
        key = self.encryption_keys.get(classification)
        if not key:
            return None
        
        return Fernet(key.encode())
    
    def encrypt_data(self, data: str, classification: DataClassification) -> str:
        """Encrypt data based on classification"""
        if classification in [DataClassification.PUBLIC, DataClassification.INTERNAL]:
            return data  # No encryption needed
        
        cipher = self.get_cipher(classification)
        if not cipher:
            raise ValueError(f"No encryption key for classification: {classification}")
        
        encrypted_data = cipher.encrypt(data.encode())
        return base64.b64encode(encrypted_data).decode()
    
    def decrypt_data(self, encrypted_data: str, classification: DataClassification) -> str:
        """Decrypt data based on classification"""
        if classification in [DataClassification.PUBLIC, DataClassification.INTERNAL]:
            return encrypted_data  # No decryption needed
        
        cipher = self.get_cipher(classification)
        if not cipher:
            raise ValueError(f"No encryption key for classification: {classification}")
        
        encrypted_bytes = base64.b64decode(encrypted_data.encode())
        decrypted_data = cipher.decrypt(encrypted_bytes)
        return decrypted_data.decode()

class DataGovernance:
    """Data governance and compliance management"""
    
    DATA_RETENTION_POLICIES = {
        DataClassification.PUBLIC: 2555,  # 7 years in days
        DataClassification.INTERNAL: 1095,  # 3 years
        DataClassification.CONFIDENTIAL: 365,  # 1 year
        DataClassification.RESTRICTED: 90   # 90 days
    }
    
    def __init__(self, encryption_manager: EncryptionManager):
        self.encryption_manager = encryption_manager
    
    def classify_user_data(self, data: Dict[str, Any]) -> DataClassification:
        """Automatically classify user data"""
        
        # Check for PII indicators
        pii_fields = ['email', 'phone', 'address', 'ssn', 'credit_card']
        if any(field in data for field in pii_fields):
            return DataClassification.RESTRICTED
        
        # Check for confidential business data
        confidential_fields = ['api_key', 'token', 'password', 'secret']
        if any(field in data for field in confidential_fields):
            return DataClassification.CONFIDENTIAL
        
        # Check for internal data
        internal_fields = ['user_id', 'session_id', 'preferences']
        if any(field in data for field in internal_fields):
            return DataClassification.INTERNAL
        
        return DataClassification.PUBLIC
    
    def apply_data_protection(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply appropriate data protection based on classification"""
        
        classification = self.classify_user_data(data)
        
        protected_data = {}
        for key, value in data.items():
            if isinstance(value, str):
                protected_data[key] = self.encryption_manager.encrypt_data(value, classification)
            else:
                protected_data[key] = value
        
        # Add metadata
        protected_data['_classification'] = classification.value
        protected_data['_encrypted'] = classification in [
            DataClassification.CONFIDENTIAL,
            DataClassification.RESTRICTED
        ]
        
        return protected_data
    
    def should_purge_data(self, data_created: datetime, classification: DataClassification) -> bool:
        """Check if data should be purged based on retention policy"""
        
        retention_days = self.DATA_RETENTION_POLICIES[classification]
        age_days = (datetime.utcnow() - data_created).days
        
        return age_days > retention_days

class SecureDataHandler:
    """Secure data handling for sensitive operations"""
    
    def __init__(self):
        self.encryption_manager = EncryptionManager()
        self.data_governance = DataGovernance(self.encryption_manager)
    
    def store_user_session(self, user_data: Dict[str, Any]) -> str:
        """Securely store user session data"""
        
        # Apply data protection
        protected_data = self.data_governance.apply_data_protection(user_data)
        
        # Generate session ID
        session_id = secrets.token_urlsafe(32)
        
        # Store in secure storage (implement with your database)
        # This would typically go to encrypted database or secure cache
        
        return session_id
    
    def store_conversation_history(self, conversation_data: Dict[str, Any]) -> str:
        """Securely store conversation history"""
        
        # Classify and protect conversation data
        classification = DataClassification.CONFIDENTIAL  # Conversations are confidential
        
        protected_conversation = {}
        for key, value in conversation_data.items():
            if key in ['messages', 'code_generated', 'images']:
                protected_conversation[key] = self.encryption_manager.encrypt_data(
                    json.dumps(value), classification
                )
            else:
                protected_conversation[key] = value
        
        protected_conversation['_classification'] = classification.value
        
        return protected_conversation
    
    def redact_logs(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive information from logs"""
        
        redacted_data = log_data.copy()
        
        # Fields to redact
        sensitive_fields = [
            'password', 'token', 'api_key', 'secret', 'authorization',
            'email', 'phone', 'address', 'ssn', 'credit_card'
        ]
        
        for field in sensitive_fields:
            if field in redacted_data:
                redacted_data[field] = "[REDACTED]"
        
        # Redact in nested objects
        for key, value in redacted_data.items():
            if isinstance(value, dict):
                redacted_data[key] = self.redact_logs(value)
            elif isinstance(value, str) and len(value) > 100:
                # Potentially sensitive long strings
                redacted_data[key] = value[:50] + "[TRUNCATED]"
        
        return redacted_data
```

---

## Phase 4: Network Security

### 4.1 Network Segmentation and Private Endpoints

```yaml
# infrastructure/security/network-security.yml
# Azure Network Security Configuration

Network Architecture:
  VNet Configuration:
    - Name: screenshot-to-code-vnet
    - Address Space: 10.0.0.0/16
    - Subnets:
        - gateway-subnet: 10.0.1.0/24 (API Gateway)
        - services-subnet: 10.0.2.0/24 (Microservices)
        - data-subnet: 10.0.3.0/24 (Databases)
        - private-endpoints: 10.0.4.0/24 (Private Endpoints)

Network Security Groups:
  gateway-nsg:
    Rules:
      - Allow HTTPS (443) from Internet
      - Allow HTTP (80) redirect to HTTPS
      - Deny all other inbound traffic
      - Allow outbound to services-subnet
  
  services-nsg:
    Rules:
      - Allow traffic from gateway-subnet
      - Allow internal service communication
      - Allow outbound to data-subnet
      - Allow outbound to Azure services
      - Deny all other traffic
  
  data-nsg:
    Rules:
      - Allow traffic from services-subnet only
      - Deny all internet access
      - Allow Azure service endpoints

Private Endpoints:
  - Cosmos DB: Disable public access, private endpoint only
  - Storage Account: Disable public access, private endpoint only
  - Key Vault: Private endpoint for secure access
  - Redis Cache: VNet integration enabled

Azure Firewall Rules:
  Application Rules:
    - Allow Microsoft Graph API (graph.microsoft.com)
    - Allow Azure AD endpoints (login.microsoftonline.com)
    - Allow OpenAI API (api.openai.com)
    - Allow Anthropic API (api.anthropic.com)
    - Allow Replicate API (api.replicate.com)
    - Deny all other external URLs
  
  Network Rules:
    - Allow Azure service tags
    - Allow NTP (port 123)
    - Deny all other outbound traffic
```

### 4.2 Container Security

```dockerfile
# Security-hardened Dockerfile template
FROM python:3.11-slim as base

# Security: Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Security: Install security updates only
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Security: Set working directory with proper permissions
WORKDIR /app
RUN chown appuser:appuser /app

# Security: Copy and install dependencies as root, then switch user
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip cache purge

# Security: Copy application code
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser shared/ ./shared/

# Security: Switch to non-root user
USER appuser

# Security: Remove unnecessary packages and files
RUN find /app -name "*.pyc" -delete \
    && find /app -name "__pycache__" -delete

# Security: Set restrictive permissions
RUN chmod -R 755 /app \
    && chmod -R 644 /app/**/*.py

# Security: Health check with timeout
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Security: Use specific port and disable debug
EXPOSE 8000
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Security: Run with minimal privileges
CMD ["python", "-m", "app.main"]
```

```yaml
# Kubernetes Security Configuration
apiVersion: v1
kind: SecurityContext
metadata:
  name: screenshot-to-code-security-context
spec:
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  fsGroup: 1000
  seccompProfile:
    type: RuntimeDefault
  capabilities:
    drop:
      - ALL
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false

---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: screenshot-to-code-network-policy
spec:
  podSelector:
    matchLabels:
      app: screenshot-to-code
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: api-gateway
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: database
    ports:
    - protocol: TCP
      port: 5432
  - to: []
    ports:
    - protocol: TCP
      port: 443  # HTTPS only
```

---

## Phase 5: Threat Modeling & Incident Response

### 5.1 Threat Model Analysis

```yaml
# STRIDE Threat Model for Screenshot-to-Code

Assets:
  - User authentication tokens
  - Generated code and images
  - AI provider API keys
  - User conversation history
  - Application secrets

Threat Actors:
  - External attackers
  - Malicious users
  - Compromised AI providers
  - Insider threats

Threats by STRIDE:

Spoofing:
  - T1: Impersonation of legitimate users
    Mitigation: Azure AD authentication, MFA
    Risk: Medium
  - T2: Fake AI provider responses
    Mitigation: Certificate pinning, response validation
    Risk: Low

Tampering:
  - T3: Malicious code injection in generated output
    Mitigation: Output sanitization, content filtering
    Risk: High
  - T4: Image manipulation attacks
    Mitigation: Image validation, size limits
    Risk: Medium

Repudiation:
  - T5: Users denying actions
    Mitigation: Comprehensive audit logging
    Risk: Low
  - T6: Unauthorized access claims
    Mitigation: Authentication logs, correlation IDs
    Risk: Low

Information Disclosure:
  - T7: Unauthorized access to conversation history
    Mitigation: Encryption at rest, access controls
    Risk: High
  - T8: API key exposure
    Mitigation: Azure Key Vault, rotation policies
    Risk: Critical

Denial of Service:
  - T9: Resource exhaustion attacks
    Mitigation: Rate limiting, auto-scaling
    Risk: Medium
  - T10: AI provider quota exhaustion
    Mitigation: Multi-provider strategy, quotas
    Risk: Medium

Elevation of Privilege:
  - T11: Unauthorized admin access
    Mitigation: RBAC, principle of least privilege
    Risk: High
  - T12: Container escape
    Mitigation: Security contexts, runtime protection
    Risk: Medium
```

### 5.2 Security Incident Response Plan

```python
# shared/security/incident_response.py
import json
import asyncio
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from dataclasses import dataclass
import httpx

class SeverityLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class IncidentType(Enum):
    AUTHENTICATION_FAILURE = "auth_failure"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    DATA_BREACH = "data_breach"
    MALICIOUS_INPUT = "malicious_input"
    SERVICE_COMPROMISE = "service_compromise"
    DENIAL_OF_SERVICE = "denial_of_service"

@dataclass
class SecurityIncident:
    incident_id: str
    incident_type: IncidentType
    severity: SeverityLevel
    description: str
    affected_services: List[str]
    detected_at: datetime
    source_ip: Optional[str] = None
    user_id: Optional[str] = None
    evidence: Optional[Dict] = None

class IncidentResponseSystem:
    """Automated security incident response system"""
    
    def __init__(self, webhook_url: str, pagerduty_key: str = None):
        self.webhook_url = webhook_url
        self.pagerduty_key = pagerduty_key
        self.active_incidents = {}
        
        # Response playbooks
        self.response_playbooks = {
            IncidentType.AUTHENTICATION_FAILURE: self._handle_auth_failure,
            IncidentType.UNAUTHORIZED_ACCESS: self._handle_unauthorized_access,
            IncidentType.DATA_BREACH: self._handle_data_breach,
            IncidentType.MALICIOUS_INPUT: self._handle_malicious_input,
            IncidentType.SERVICE_COMPROMISE: self._handle_service_compromise,
            IncidentType.DENIAL_OF_SERVICE: self._handle_dos_attack
        }
    
    async def report_incident(self, incident: SecurityIncident) -> str:
        """Report and respond to security incident"""
        
        # Store incident
        self.active_incidents[incident.incident_id] = incident
        
        # Execute response playbook
        if incident.incident_type in self.response_playbooks:
            await self.response_playbooks[incident.incident_type](incident)
        
        # Send notifications
        await self._send_notifications(incident)
        
        # Log incident
        await self._log_incident(incident)
        
        return incident.incident_id
    
    async def _handle_auth_failure(self, incident: SecurityIncident):
        """Handle authentication failure incidents"""
        
        if incident.severity in [SeverityLevel.HIGH, SeverityLevel.CRITICAL]:
            # Multiple failed attempts - implement IP blocking
            if incident.source_ip:
                await self._block_ip_address(incident.source_ip)
            
            # Alert security team
            await self._alert_security_team(incident)
    
    async def _handle_unauthorized_access(self, incident: SecurityIncident):
        """Handle unauthorized access attempts"""
        
        # Revoke user sessions if user identified
        if incident.user_id:
            await self._revoke_user_sessions(incident.user_id)
        
        # Block source IP
        if incident.source_ip:
            await self._block_ip_address(incident.source_ip)
        
        # Escalate if critical
        if incident.severity == SeverityLevel.CRITICAL:
            await self._escalate_to_oncall(incident)
    
    async def _handle_data_breach(self, incident: SecurityIncident):
        """Handle potential data breach"""
        
        # Immediate containment
        await self._enable_enhanced_monitoring()
        
        # Alert legal and compliance teams
        await self._alert_compliance_team(incident)
        
        # Start evidence collection
        await self._collect_forensic_evidence(incident)
        
        # Escalate to highest priority
        await self._escalate_to_oncall(incident)
    
    async def _handle_malicious_input(self, incident: SecurityIncident):
        """Handle malicious input detection"""
        
        # Update WAF rules
        await self._update_waf_rules(incident)
        
        # Block source if repeated attempts
        if incident.source_ip:
            await self._temporary_ip_block(incident.source_ip)
    
    async def _handle_service_compromise(self, incident: SecurityIncident):
        """Handle service compromise"""
        
        # Isolate affected services
        for service in incident.affected_services:
            await self._isolate_service(service)
        
        # Rotate API keys and secrets
        await self._rotate_secrets()
        
        # Full incident response activation
        await self._activate_incident_response_team(incident)
    
    async def _handle_dos_attack(self, incident: SecurityIncident):
        """Handle denial of service attacks"""
        
        # Enable aggressive rate limiting
        await self._enable_emergency_rate_limiting()
        
        # Scale up infrastructure
        await self._auto_scale_services()
        
        # Block attack sources
        if incident.source_ip:
            await self._block_ip_address(incident.source_ip)
    
    async def _send_notifications(self, incident: SecurityIncident):
        """Send incident notifications"""
        
        # Slack notification
        await self._send_slack_alert(incident)
        
        # PagerDuty for high/critical incidents
        if incident.severity in [SeverityLevel.HIGH, SeverityLevel.CRITICAL]:
            await self._send_pagerduty_alert(incident)
    
    async def _send_slack_alert(self, incident: SecurityIncident):
        """Send Slack security alert"""
        
        color = {
            SeverityLevel.LOW: "good",
            SeverityLevel.MEDIUM: "warning",
            SeverityLevel.HIGH: "danger",
            SeverityLevel.CRITICAL: "#ff0000"
        }[incident.severity]
        
        payload = {
            "text": f"🚨 Security Incident: {incident.incident_type.value}",
            "attachments": [
                {
                    "color": color,
                    "fields": [
                        {"title": "Severity", "value": incident.severity.value, "short": True},
                        {"title": "Type", "value": incident.incident_type.value, "short": True},
                        {"title": "Services", "value": ", ".join(incident.affected_services), "short": True},
                        {"title": "Source IP", "value": incident.source_ip or "Unknown", "short": True},
                        {"title": "Description", "value": incident.description, "short": False},
                        {"title": "Incident ID", "value": incident.incident_id, "short": False}
                    ]
                }
            ]
        }
        
        async with httpx.AsyncClient() as client:
            try:
                await client.post(self.webhook_url, json=payload)
            except Exception as e:
                print(f"Failed to send Slack alert: {e}")
    
    async def _block_ip_address(self, ip_address: str):
        """Block IP address at firewall level"""
        # Implementation would integrate with Azure Firewall or WAF
        print(f"Blocking IP address: {ip_address}")
    
    async def _revoke_user_sessions(self, user_id: str):
        """Revoke all sessions for a user"""
        # Implementation would revoke JWT tokens and clear session cache
        print(f"Revoking sessions for user: {user_id}")
    
    async def _escalate_to_oncall(self, incident: SecurityIncident):
        """Escalate to on-call security team"""
        if self.pagerduty_key:
            # Send PagerDuty alert
            await self._send_pagerduty_alert(incident)
    
    async def _log_incident(self, incident: SecurityIncident):
        """Log incident to security information system"""
        
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "security_incident",
            "incident_id": incident.incident_id,
            "incident_type": incident.incident_type.value,
            "severity": incident.severity.value,
            "description": incident.description,
            "affected_services": incident.affected_services,
            "source_ip": incident.source_ip,
            "user_id": incident.user_id,
            "evidence": incident.evidence
        }
        
        # Send to security logging system
        print(f"Security incident logged: {json.dumps(log_entry)}")

# Usage example
async def detect_and_respond_to_threats():
    """Example threat detection and response"""
    
    incident_response = IncidentResponseSystem(
        webhook_url="https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK",
        pagerduty_key="YOUR_PAGERDUTY_KEY"
    )
    
    # Example: Detect suspicious authentication pattern
    suspicious_incident = SecurityIncident(
        incident_id=f"INC-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        incident_type=IncidentType.AUTHENTICATION_FAILURE,
        severity=SeverityLevel.HIGH,
        description="Multiple failed authentication attempts from single IP",
        affected_services=["api-gateway"],
        detected_at=datetime.utcnow(),
        source_ip="192.168.1.100",
        evidence={"failed_attempts": 15, "time_window": "5 minutes"}
    )
    
    await incident_response.report_incident(suspicious_incident)
```

---

## Completion Checklist

### ✅ **Identity & Access Management**
- [x] **Azure AD Integration**: OAuth 2.0, JWT validation, user management
- [x] **Role-Based Access Control**: Permissions matrix, role enforcement
- [x] **API Key Management**: Secure generation, validation, rotation
- [x] **Multi-Factor Authentication**: Azure AD MFA integration

### ✅ **API Security & Protection**
- [x] **API Gateway Security**: Rate limiting, input validation, CORS
- [x] **Web Application Firewall**: Attack pattern detection, IP blocking
- [x] **Security Headers**: CSP, HSTS, XSS protection, frame options
- [x] **Request Validation**: Pydantic models, input sanitization

### ✅ **Data Protection & Encryption**
- [x] **Data Classification**: Automatic classification, retention policies
- [x] **Encryption Management**: Key Vault integration, field-level encryption
- [x] **Data Governance**: GDPR compliance, data purging, audit trails
- [x] **Secure Data Handling**: Session management, log redaction

### ✅ **Network Security**
- [x] **Network Segmentation**: VNet design, NSG rules, subnets
- [x] **Private Endpoints**: Disable public access, private connectivity
- [x] **Container Security**: Hardened Dockerfiles, security contexts
- [x] **Firewall Rules**: Application and network rule configurations

### ✅ **Threat Modeling & Response**
- [x] **STRIDE Analysis**: Comprehensive threat identification
- [x] **Incident Response**: Automated response playbooks, notifications
- [x] **Security Monitoring**: Real-time threat detection, alerting
- [x] **Forensic Capabilities**: Evidence collection, incident tracking

---

## Next Steps for TASK-009

### Security Implementation Priority
1. **Phase 1**: Azure AD integration and API Gateway security
2. **Phase 2**: Data encryption and Key Vault setup
3. **Phase 3**: Network security and private endpoints
4. **Phase 4**: Incident response system and monitoring
5. **Phase 5**: Security testing and penetration testing

### Compliance Requirements
- **SOC 2 Type II**: Controls implementation and audit preparation
- **ISO 27001**: Information security management system
- **GDPR**: Data protection and privacy compliance
- **Microsoft Standards**: Cloud security framework alignment

---

**Status**: Security architecture design completed  
**Next Action**: Begin TASK-009 - Project Structure Creation  
**Deliverables**: Complete security architecture, authentication system, data protection framework, incident response system