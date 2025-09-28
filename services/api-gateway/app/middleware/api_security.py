"""
API Security Hardening Middleware
Advanced API security features including enhanced rate limiting, input validation, and security headers
"""
import re
import json
import time
import hashlib
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from starlette.responses import JSONResponse
import ipaddress

from shared.monitoring.structured_logger import StructuredLogger
from shared.monitoring.correlation import get_correlation_id


class RateLimitType(str, Enum):
    """Rate limit types"""
    IP_BASED = "ip_based"
    USER_BASED = "user_based"
    API_KEY_BASED = "api_key_based"
    ENDPOINT_BASED = "endpoint_based"


class SecurityLevel(str, Enum):
    """API endpoint security levels"""
    PUBLIC = "public"
    PROTECTED = "protected"
    RESTRICTED = "restricted"
    CRITICAL = "critical"


@dataclass
class RateLimitRule:
    """Rate limiting rule configuration"""
    name: str
    limit_type: RateLimitType
    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int
    burst_limit: int = 10  # Allow burst requests
    endpoints: List[str] = field(default_factory=list)
    exempt_ips: Set[str] = field(default_factory=set)
    
    
@dataclass
class SecurityPolicy:
    """Security policy for API endpoints"""
    endpoint_pattern: str
    security_level: SecurityLevel
    require_auth: bool = True
    require_api_key: bool = False
    rate_limit_rules: List[str] = field(default_factory=list)
    allowed_methods: List[str] = field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE"])
    input_validation_rules: Dict[str, Any] = field(default_factory=dict)
    response_headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class InputValidationRule:
    """Input validation rule"""
    field_name: str
    required: bool = False
    data_type: str = "string"  # string, integer, float, boolean, array, object
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    allowed_values: Optional[List[str]] = None
    sanitize: bool = True


class APISecurityMiddleware(BaseHTTPMiddleware):
    """Advanced API security hardening middleware"""
    
    def __init__(
        self,
        app: ASGIApp,
        logger: StructuredLogger,
        enable_rate_limiting: bool = True,
        enable_input_validation: bool = True,
        enable_security_headers: bool = True,
        enable_request_sanitization: bool = True
    ):
        super().__init__(app)
        self.logger = logger
        self.enable_rate_limiting = enable_rate_limiting
        self.enable_input_validation = enable_input_validation
        self.enable_security_headers = enable_security_headers
        self.enable_request_sanitization = enable_request_sanitization
        
        # Rate limiting storage
        self.rate_limit_storage: Dict[str, List[datetime]] = {}
        
        # Initialize rate limiting rules
        self.rate_limit_rules = self._initialize_rate_limit_rules()
        
        # Initialize security policies
        self.security_policies = self._initialize_security_policies()
        
        # Initialize input validation rules
        self.validation_rules = self._initialize_validation_rules()
        
        # Security metrics
        self.requests_processed = 0
        self.requests_blocked = 0
        self.validation_failures = 0
        self.rate_limit_violations = 0
        
        self.logger.info("API Security middleware initialized",
                        rate_limiting=enable_rate_limiting,
                        input_validation=enable_input_validation,
                        security_headers=enable_security_headers)
    
    def _initialize_rate_limit_rules(self) -> Dict[str, RateLimitRule]:
        """Initialize rate limiting rules"""
        return {
            "default_ip": RateLimitRule(
                name="Default IP Rate Limit",
                limit_type=RateLimitType.IP_BASED,
                requests_per_minute=60,
                requests_per_hour=1000,
                requests_per_day=10000,
                burst_limit=20
            ),
            "auth_endpoints": RateLimitRule(
                name="Authentication Endpoints",
                limit_type=RateLimitType.IP_BASED,
                requests_per_minute=10,
                requests_per_hour=100,
                requests_per_day=500,
                burst_limit=5,
                endpoints=["/api/v1/security/auth/login", "/api/v1/security/auth/refresh"]
            ),
            "api_key_based": RateLimitRule(
                name="API Key Based Limits",
                limit_type=RateLimitType.API_KEY_BASED,
                requests_per_minute=100,
                requests_per_hour=5000,
                requests_per_day=50000,
                burst_limit=50
            ),
            "critical_endpoints": RateLimitRule(
                name="Critical Endpoints",
                limit_type=RateLimitType.ENDPOINT_BASED,
                requests_per_minute=20,
                requests_per_hour=200,
                requests_per_day=1000,
                burst_limit=10,
                endpoints=["/api/v1/security/users", "/api/v1/security/api-keys"]
            )
        }
    
    def _initialize_security_policies(self) -> List[SecurityPolicy]:
        """Initialize security policies for different endpoints"""
        return [
            SecurityPolicy(
                endpoint_pattern=r"^/api/v1/security/auth/.*",
                security_level=SecurityLevel.CRITICAL,
                require_auth=False,
                rate_limit_rules=["auth_endpoints"],
                input_validation_rules={
                    "username": {"required": True, "max_length": 100, "sanitize": True},
                    "password": {"required": True, "min_length": 8, "max_length": 128}
                }
            ),
            SecurityPolicy(
                endpoint_pattern=r"^/api/v1/security/users.*",
                security_level=SecurityLevel.RESTRICTED,
                require_auth=True,
                rate_limit_rules=["critical_endpoints"],
                allowed_methods=["GET", "POST", "PUT", "DELETE"]
            ),
            SecurityPolicy(
                endpoint_pattern=r"^/api/v1/security/api-keys.*",
                security_level=SecurityLevel.RESTRICTED,
                require_auth=True,
                rate_limit_rules=["critical_endpoints"]
            ),
            SecurityPolicy(
                endpoint_pattern=r"^/api/v1/security/.*",
                security_level=SecurityLevel.PROTECTED,
                require_auth=True,
                rate_limit_rules=["default_ip"]
            ),
            SecurityPolicy(
                endpoint_pattern=r"^/api/v1/.*",
                security_level=SecurityLevel.PROTECTED,
                require_auth=True,
                rate_limit_rules=["default_ip", "api_key_based"]
            ),
            SecurityPolicy(
                endpoint_pattern=r"^/health.*",
                security_level=SecurityLevel.PUBLIC,
                require_auth=False,
                rate_limit_rules=["default_ip"]
            )
        ]
    
    def _initialize_validation_rules(self) -> Dict[str, List[InputValidationRule]]:
        """Initialize input validation rules"""
        return {
            "/api/v1/security/auth/login": [
                InputValidationRule(
                    field_name="username",
                    required=True,
                    max_length=100,
                    pattern=r"^[a-zA-Z0-9._@-]+$"
                ),
                InputValidationRule(
                    field_name="password",
                    required=True,
                    min_length=8,
                    max_length=128
                )
            ],
            "/api/v1/security/users": [
                InputValidationRule(
                    field_name="username",
                    required=True,
                    max_length=50,
                    pattern=r"^[a-zA-Z0-9._-]+$"
                ),
                InputValidationRule(
                    field_name="email",
                    required=True,
                    max_length=254,
                    pattern=r"^[^@]+@[^@]+\.[^@]+$"
                ),
                InputValidationRule(
                    field_name="password",
                    required=True,
                    min_length=8,
                    max_length=128
                ),
                InputValidationRule(
                    field_name="roles",
                    required=False,
                    data_type="array",
                    allowed_values=["admin", "user", "developer", "analyst", "service", "guest"]
                )
            ],
            "/api/v1/security/api-keys": [
                InputValidationRule(
                    field_name="name",
                    required=True,
                    min_length=3,
                    max_length=100,
                    pattern=r"^[a-zA-Z0-9\s._-]+$"
                ),
                InputValidationRule(
                    field_name="scopes",
                    required=False,
                    data_type="array",
                    allowed_values=["read", "write", "delete", "admin", "execute", "monitor", "config"]
                ),
                InputValidationRule(
                    field_name="expires_in_days",
                    required=False,
                    data_type="integer",
                    min_length=1,
                    max_length=365
                )
            ]
        }
    
    async def dispatch(self, request: Request, call_next):
        """Process request through API security layers"""
        start_time = time.time()
        correlation_id = get_correlation_id()
        
        self.requests_processed += 1
        
        try:
            # Get client information
            client_ip = self._get_client_ip(request)
            user_agent = request.headers.get("user-agent", "")
            path = request.url.path
            method = request.method
            
            # Find matching security policy
            security_policy = self._get_security_policy(path)
            
            # Security Layer 1: Method validation
            if method not in security_policy.allowed_methods:
                self.requests_blocked += 1
                return self._create_error_response(
                    status_code=405,
                    message="Method not allowed",
                    correlation_id=correlation_id
                )
            
            # Security Layer 2: Rate limiting
            if self.enable_rate_limiting:
                rate_limit_violated = await self._check_rate_limits(
                    request, client_ip, security_policy
                )
                if rate_limit_violated:
                    self.rate_limit_violations += 1
                    self.requests_blocked += 1
                    return self._create_rate_limit_response(correlation_id)
            
            # Security Layer 3: Input validation and sanitization
            if self.enable_input_validation and method in ["POST", "PUT", "PATCH"]:
                validation_error = await self._validate_and_sanitize_input(request, path)
                if validation_error:
                    self.validation_failures += 1
                    self.requests_blocked += 1
                    return self._create_validation_error_response(
                        validation_error, correlation_id
                    )
            
            # Security Layer 4: Request sanitization
            if self.enable_request_sanitization:
                await self._sanitize_request(request)
            
            # Process the request
            response = await call_next(request)
            
            # Security Layer 5: Response security headers
            if self.enable_security_headers:
                await self._add_security_headers(response, security_policy)
            
            # Security Layer 6: Response sanitization
            await self._sanitize_response(response)
            
            # Log successful request
            processing_time = time.time() - start_time
            self.logger.debug("API security processed request",
                            correlation_id=correlation_id,
                            path=path,
                            method=method,
                            client_ip=client_ip,
                            processing_time_ms=processing_time * 1000,
                            security_level=security_policy.security_level.value)
            
            return response
            
        except Exception as e:
            self.logger.error("API security middleware error",
                            correlation_id=correlation_id,
                            error=str(e),
                            path=request.url.path)
            
            return self._create_error_response(
                status_code=500,
                message="Internal security error",
                correlation_id=correlation_id
            )
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address"""
        # Check forwarded headers
        forwarded_headers = [
            "x-forwarded-for",
            "x-real-ip",
            "cf-connecting-ip",
            "x-client-ip"
        ]
        
        for header in forwarded_headers:
            if header in request.headers:
                ip = request.headers[header].split(",")[0].strip()
                if self._is_valid_ip(ip):
                    return ip
        
        return request.client.host if request.client else "unknown"
    
    def _is_valid_ip(self, ip_str: str) -> bool:
        """Validate IP address"""
        try:
            ipaddress.ip_address(ip_str)
            return True
        except ValueError:
            return False
    
    def _get_security_policy(self, path: str) -> SecurityPolicy:
        """Get security policy for endpoint"""
        for policy in self.security_policies:
            if re.match(policy.endpoint_pattern, path):
                return policy
        
        # Return default policy if no match
        return SecurityPolicy(
            endpoint_pattern=".*",
            security_level=SecurityLevel.PROTECTED,
            require_auth=True,
            rate_limit_rules=["default_ip"]
        )
    
    async def _check_rate_limits(
        self,
        request: Request,
        client_ip: str,
        security_policy: SecurityPolicy
    ) -> bool:
        """Check rate limiting rules"""
        current_time = datetime.utcnow()
        
        for rule_name in security_policy.rate_limit_rules:
            rule = self.rate_limit_rules.get(rule_name)
            if not rule:
                continue
            
            # Check if endpoint matches rule
            if rule.endpoints and request.url.path not in rule.endpoints:
                continue
            
            # Check if IP is exempt
            if client_ip in rule.exempt_ips:
                continue
            
            # Create rate limit key based on type
            if rule.limit_type == RateLimitType.IP_BASED:
                rate_key = f"ip:{client_ip}"
            elif rule.limit_type == RateLimitType.API_KEY_BASED:
                api_key = request.headers.get("x-api-key")
                if not api_key:
                    continue
                rate_key = f"api:{hashlib.sha256(api_key.encode()).hexdigest()[:16]}"
            elif rule.limit_type == RateLimitType.ENDPOINT_BASED:
                rate_key = f"endpoint:{request.url.path}"
            else:
                rate_key = f"user:{client_ip}"  # Default to IP
            
            # Check rate limits
            if await self._is_rate_limited(rate_key, rule, current_time):
                self.logger.warning("Rate limit exceeded",
                                  rule_name=rule_name,
                                  rate_key=rate_key,
                                  client_ip=client_ip,
                                  path=request.url.path)
                return True
        
        return False
    
    async def _is_rate_limited(
        self,
        rate_key: str,
        rule: RateLimitRule,
        current_time: datetime
    ) -> bool:
        """Check if rate limit is exceeded"""
        if rate_key not in self.rate_limit_storage:
            self.rate_limit_storage[rate_key] = []
        
        requests = self.rate_limit_storage[rate_key]
        
        # Clean old requests
        requests = [
            req_time for req_time in requests
            if current_time - req_time < timedelta(days=1)
        ]
        
        # Check minute limit
        recent_minute = [
            req_time for req_time in requests
            if current_time - req_time < timedelta(minutes=1)
        ]
        if len(recent_minute) >= rule.requests_per_minute:
            return True
        
        # Check hour limit
        recent_hour = [
            req_time for req_time in requests
            if current_time - req_time < timedelta(hours=1)
        ]
        if len(recent_hour) >= rule.requests_per_hour:
            return True
        
        # Check daily limit
        if len(requests) >= rule.requests_per_day:
            return True
        
        # Record this request
        requests.append(current_time)
        self.rate_limit_storage[rate_key] = requests
        
        return False
    
    async def _validate_and_sanitize_input(
        self,
        request: Request,
        path: str
    ) -> Optional[str]:
        """Validate and sanitize request input"""
        try:
            # Get validation rules for this endpoint
            rules = self.validation_rules.get(path, [])
            if not rules:
                return None
            
            # Get request body
            body = await request.body()
            if not body:
                return None
            
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return "Invalid JSON format"
            
            # Validate each field
            for rule in rules:
                field_value = data.get(rule.field_name)
                
                # Check required fields
                if rule.required and (field_value is None or field_value == ""):
                    return f"Field '{rule.field_name}' is required"
                
                if field_value is None:
                    continue
                
                # Type validation
                validation_error = self._validate_field_type(
                    rule.field_name, field_value, rule
                )
                if validation_error:
                    return validation_error
                
                # Pattern validation
                if rule.pattern and isinstance(field_value, str):
                    if not re.match(rule.pattern, field_value):
                        return f"Field '{rule.field_name}' format is invalid"
                
                # Length validation
                if isinstance(field_value, str):
                    if rule.min_length and len(field_value) < rule.min_length:
                        return f"Field '{rule.field_name}' is too short"
                    if rule.max_length and len(field_value) > rule.max_length:
                        return f"Field '{rule.field_name}' is too long"
                
                # Allowed values validation
                if rule.allowed_values:
                    if isinstance(field_value, list):
                        for item in field_value:
                            if item not in rule.allowed_values:
                                return f"Invalid value '{item}' in field '{rule.field_name}'"
                    elif field_value not in rule.allowed_values:
                        return f"Invalid value for field '{rule.field_name}'"
                
                # Sanitize field if requested
                if rule.sanitize and isinstance(field_value, str):
                    data[rule.field_name] = self._sanitize_string(field_value)
            
            # Update request body with sanitized data
            sanitized_body = json.dumps(data).encode()
            request._body = sanitized_body
            
            return None
            
        except Exception as e:
            self.logger.error("Input validation error", error=str(e))
            return "Input validation failed"
    
    def _validate_field_type(
        self,
        field_name: str,
        field_value: Any,
        rule: InputValidationRule
    ) -> Optional[str]:
        """Validate field data type"""
        if rule.data_type == "string" and not isinstance(field_value, str):
            return f"Field '{field_name}' must be a string"
        elif rule.data_type == "integer" and not isinstance(field_value, int):
            return f"Field '{field_name}' must be an integer"
        elif rule.data_type == "float" and not isinstance(field_value, (int, float)):
            return f"Field '{field_name}' must be a number"
        elif rule.data_type == "boolean" and not isinstance(field_value, bool):
            return f"Field '{field_name}' must be a boolean"
        elif rule.data_type == "array" and not isinstance(field_value, list):
            return f"Field '{field_name}' must be an array"
        elif rule.data_type == "object" and not isinstance(field_value, dict):
            return f"Field '{field_name}' must be an object"
        
        return None
    
    def _sanitize_string(self, value: str) -> str:
        """Sanitize string input"""
        # Remove or escape dangerous characters
        dangerous_patterns = [
            (r'<script[^>]*>.*?</script>', ''),  # Remove script tags
            (r'javascript:', ''),               # Remove javascript: URLs
            (r'on\w+\s*=', ''),                # Remove event handlers
            (r'<iframe[^>]*>.*?</iframe>', ''), # Remove iframes
            (r'[<>"\']', ''),                   # Remove HTML/SQL injection chars
        ]
        
        sanitized = value
        for pattern, replacement in dangerous_patterns:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
        
        # Limit length to prevent DoS
        if len(sanitized) > 10000:
            sanitized = sanitized[:10000]
        
        return sanitized.strip()
    
    async def _sanitize_request(self, request: Request):
        """Sanitize request headers and parameters"""
        # Sanitize query parameters
        if request.query_params:
            sanitized_params = {}
            for key, value in request.query_params.items():
                sanitized_key = self._sanitize_string(key)
                sanitized_value = self._sanitize_string(value)
                sanitized_params[sanitized_key] = sanitized_value
    
    async def _add_security_headers(
        self,
        response: Response,
        security_policy: SecurityPolicy
    ):
        """Add comprehensive security headers"""
        # Basic security headers
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
        
        # HSTS for HTTPS
        if hasattr(response, 'url') and str(response.url).startswith('https'):
            security_headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        
        # Content Security Policy based on security level
        if security_policy.security_level == SecurityLevel.CRITICAL:
            security_headers["Content-Security-Policy"] = (
                "default-src 'none'; "
                "script-src 'self'; "
                "style-src 'self'; "
                "img-src 'self' data:; "
                "font-src 'self'"
            )
        else:
            security_headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self'"
            )
        
        # Add custom headers from policy
        security_headers.update(security_policy.response_headers)
        
        # Apply headers to response
        for header, value in security_headers.items():
            response.headers[header] = value
    
    async def _sanitize_response(self, response: Response):
        """Sanitize response to prevent information disclosure"""
        # Remove server identification headers
        headers_to_remove = [
            "server",
            "x-powered-by",
            "x-aspnet-version",
            "x-frame-options"  # Will be set by our security headers
        ]
        
        for header in headers_to_remove:
            if header in response.headers:
                del response.headers[header]
        
        # Add correlation ID for tracking
        correlation_id = get_correlation_id()
        response.headers["X-Correlation-ID"] = correlation_id
    
    def _create_rate_limit_response(self, correlation_id: str) -> JSONResponse:
        """Create rate limit exceeded response"""
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "message": "Too many requests. Please try again later.",
                "correlation_id": correlation_id,
                "retry_after": 60
            },
            headers={
                "Retry-After": "60",
                "X-RateLimit-Reset": str(int(time.time()) + 60)
            }
        )
    
    def _create_validation_error_response(
        self,
        error_message: str,
        correlation_id: str
    ) -> JSONResponse:
        """Create validation error response"""
        return JSONResponse(
            status_code=400,
            content={
                "error": "Validation failed",
                "message": error_message,
                "correlation_id": correlation_id
            }
        )
    
    def _create_error_response(
        self,
        status_code: int,
        message: str,
        correlation_id: str
    ) -> JSONResponse:
        """Create generic error response"""
        return JSONResponse(
            status_code=status_code,
            content={
                "error": "Security error",
                "message": message,
                "correlation_id": correlation_id
            }
        )
    
    # Management and monitoring methods
    
    def get_security_metrics(self) -> Dict[str, Any]:
        """Get API security metrics"""
        return {
            "requests_processed": self.requests_processed,
            "requests_blocked": self.requests_blocked,
            "validation_failures": self.validation_failures,
            "rate_limit_violations": self.rate_limit_violations,
            "block_rate": self.requests_blocked / max(self.requests_processed, 1),
            "validation_failure_rate": self.validation_failures / max(self.requests_processed, 1),
            "rate_limit_violation_rate": self.rate_limit_violations / max(self.requests_processed, 1)
        }
    
    def update_rate_limit_rule(self, rule_name: str, rule: RateLimitRule):
        """Update rate limiting rule"""
        self.rate_limit_rules[rule_name] = rule
        self.logger.info("Rate limit rule updated", rule_name=rule_name)
    
    def add_security_policy(self, policy: SecurityPolicy):
        """Add new security policy"""
        self.security_policies.append(policy)
        self.logger.info("Security policy added", pattern=policy.endpoint_pattern)
    
    def clear_rate_limit_cache(self):
        """Clear rate limiting cache"""
        self.rate_limit_storage.clear()
        self.logger.info("Rate limit cache cleared")
    
    def get_rate_limit_status(self, identifier: str) -> Dict[str, Any]:
        """Get rate limit status for identifier"""
        requests = self.rate_limit_storage.get(identifier, [])
        current_time = datetime.utcnow()
        
        return {
            "identifier": identifier,
            "total_requests": len(requests),
            "requests_last_minute": len([
                r for r in requests
                if current_time - r < timedelta(minutes=1)
            ]),
            "requests_last_hour": len([
                r for r in requests
                if current_time - r < timedelta(hours=1)
            ]),
            "requests_today": len([
                r for r in requests
                if current_time - r < timedelta(days=1)
            ])
        }