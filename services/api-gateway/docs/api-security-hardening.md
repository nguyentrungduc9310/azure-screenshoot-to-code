# API Security Hardening Documentation

## Overview

The API Security Hardening system provides advanced protection for REST APIs through multi-layer security controls. This system builds on the core security framework to provide specialized API protection features.

## Architecture

### Multi-Layer API Security Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                  API Security Middleware                        │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌────────────┐ │
│  │   Method    │ │Rate Limiting│ │   Input     │ │  Request   │ │
│  │ Validation  │ │             │ │ Validation  │ │Sanitization│ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                │
           ┌────────────────────┼────────────────────┐
           │                    │                    │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│Advanced Rate    │    │Input Validation  │    │Security Headers │
│Limiting         │    │& Sanitization    │    │& Response       │
│• IP-based       │    │• Type checking   │    │Protection       │
│• User-based     │    │• Pattern matching│    │• CSP headers    │
│• API key-based  │    │• Length limits   │    │• CORS policies  │
│• Endpoint-based │    │• XSS prevention  │    │• Cache control  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Core Components

### 1. Advanced Rate Limiting

Multi-dimensional rate limiting with intelligent rules and exemptions.

#### Rate Limit Types

**IP-Based Rate Limiting:**
```python
RateLimitRule(
    name="Default IP Rate Limit",
    limit_type=RateLimitType.IP_BASED,
    requests_per_minute=60,
    requests_per_hour=1000,
    requests_per_day=10000,
    burst_limit=20
)
```

**API Key-Based Rate Limiting:**
```python
RateLimitRule(
    name="API Key Based Limits", 
    limit_type=RateLimitType.API_KEY_BASED,
    requests_per_minute=100,
    requests_per_hour=5000,
    requests_per_day=50000,
    burst_limit=50
)
```

**Endpoint-Specific Rate Limiting:**
```python
RateLimitRule(
    name="Critical Endpoints",
    limit_type=RateLimitType.ENDPOINT_BASED,
    requests_per_minute=20,
    requests_per_hour=200,
    requests_per_day=1000,
    endpoints=["/api/v1/security/users", "/api/v1/security/api-keys"]
)
```

#### Configuration Examples

```python
# Default rate limiting rules
rate_limit_rules = {
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
        endpoints=["/api/v1/security/auth/login"]
    )
}
```

### 2. Input Validation & Sanitization

Comprehensive input validation with pattern matching and sanitization.

#### Validation Rules

**Field-Level Validation:**
```python
InputValidationRule(
    field_name="username",
    required=True,
    max_length=50,
    pattern=r"^[a-zA-Z0-9._-]+$",
    sanitize=True
)
```

**Type Validation:**
```python
InputValidationRule(
    field_name="roles",
    required=False,
    data_type="array",
    allowed_values=["admin", "user", "developer", "analyst"]
)
```

#### Sanitization Features

**String Sanitization:**
- Removes script tags and JavaScript
- Filters dangerous HTML elements
- Limits string length to prevent DoS
- Escapes special characters

```python
# Example dangerous input
dangerous_input = "<script>alert('xss')</script>Hello"
sanitized = sanitize_string(dangerous_input)
# Result: "Hello"
```

**Request Sanitization:**
- Query parameter sanitization
- Header value sanitization
- Request body sanitization

### 3. Security Policies

Endpoint-specific security policies with granular control.

#### Security Levels

**Public Endpoints:**
```python
SecurityPolicy(
    endpoint_pattern=r"^/health.*",
    security_level=SecurityLevel.PUBLIC,
    require_auth=False,
    rate_limit_rules=["default_ip"]
)
```

**Protected Endpoints:**
```python
SecurityPolicy(
    endpoint_pattern=r"^/api/v1/.*",
    security_level=SecurityLevel.PROTECTED,
    require_auth=True,
    rate_limit_rules=["default_ip", "api_key_based"]
)
```

**Critical Endpoints:**
```python
SecurityPolicy(
    endpoint_pattern=r"^/api/v1/security/auth/.*",
    security_level=SecurityLevel.CRITICAL,
    require_auth=False,
    rate_limit_rules=["auth_endpoints"],
    input_validation_rules={
        "username": {"required": True, "max_length": 100},
        "password": {"required": True, "min_length": 8}
    }
)
```

### 4. Security Headers

Comprehensive HTTP security headers based on endpoint security level.

#### Standard Security Headers

```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Cache-Control: no-cache, no-store, must-revalidate
Pragma: no-cache
Expires: 0
```

#### Content Security Policy

**Critical Endpoints:**
```http
Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'
```

**Standard Endpoints:**
```http
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'
```

## Advanced API Key Management

### API Key Types and Quotas

**Standard API Keys:**
```python
APIKeyQuota(
    requests_per_minute=100,
    requests_per_hour=5000,
    requests_per_day=50000,
    requests_per_month=1000000,
    data_transfer_mb_per_day=1000,
    concurrent_requests=10
)
```

**Premium API Keys:**
```python
APIKeyQuota(
    requests_per_minute=500,
    requests_per_hour=25000,
    requests_per_day=250000,
    requests_per_month=5000000,
    data_transfer_mb_per_day=5000,
    concurrent_requests=50
)
```

**Enterprise API Keys:**
```python
APIKeyQuota(
    requests_per_minute=2000,
    requests_per_hour=100000,
    requests_per_day=1000000,
    requests_per_month=20000000,
    data_transfer_mb_per_day=20000,
    concurrent_requests=200
)
```

### API Key Permissions

**Scope-Based Permissions:**
```python
APIKeyPermissions(
    scopes={"read", "write", "monitor"},
    allowed_endpoints={"/api/v1/data", "/api/v1/reports"},
    denied_endpoints={"/api/v1/admin"},
    allowed_methods={"GET", "POST"},
    ip_whitelist={"192.168.1.100", "10.0.0.50"}
)
```

**IP-Based Restrictions:**
```python
permissions = APIKeyPermissions(
    scopes={"read"},
    ip_whitelist={"203.0.113.0/24"},  # Only allow from specific subnet
    ip_blacklist={"192.168.1.100"}   # Block specific IPs
)
```

### API Key Lifecycle Management

**Key Creation:**
```python
api_key = key_manager.create_api_key(
    name="Production API Key",
    description="Main production application key",
    user_id="user123",
    key_type=APIKeyType.PREMIUM,
    scopes={"read", "write"},
    expires_in_days=365,
    permissions=custom_permissions
)
```

**Key Rotation:**
```python
# Rotate key (generate new key, keep permissions)
new_raw_key = key_manager.rotate_api_key(api_key.key_id)
```

**Key Suspension:**
```python
# Temporarily suspend key
key_manager.suspend_api_key(api_key.key_id, "Suspicious activity detected")

# Reactivate key
key_manager.reactivate_api_key(api_key.key_id)
```

**Key Revocation:**
```python
# Permanently revoke key
key_manager.revoke_api_key(api_key.key_id, "Security breach")
```

## Usage Examples

### Rate Limiting Configuration

```python
# Configure custom rate limits
api_security = APISecurityMiddleware(
    app=app,
    logger=logger,
    enable_rate_limiting=True
)

# Add custom rate limit rule
custom_rule = RateLimitRule(
    name="Heavy API Users",
    limit_type=RateLimitType.API_KEY_BASED,
    requests_per_minute=1000,
    requests_per_hour=50000,
    requests_per_day=1000000,
    endpoints=["/api/v1/bulk-operations"]
)

api_security.update_rate_limit_rule("heavy_users", custom_rule)
```

### Input Validation Setup

```python
# Define validation rules for endpoint
validation_rules = {
    "/api/v1/users": [
        InputValidationRule(
            field_name="email",
            required=True,
            max_length=254,
            pattern=r"^[^@]+@[^@]+\.[^@]+$"
        ),
        InputValidationRule(
            field_name="age",
            required=False,
            data_type="integer",
            min_length=1,
            max_length=120
        )
    ]
}
```

### Security Policy Configuration

```python
# Add custom security policy
policy = SecurityPolicy(
    endpoint_pattern=r"^/api/v1/billing/.*",
    security_level=SecurityLevel.CRITICAL,
    require_auth=True,
    require_api_key=True,
    rate_limit_rules=["critical_endpoints"],
    allowed_methods=["GET", "POST"],
    response_headers={
        "X-Financial-Data": "true",
        "Cache-Control": "no-cache, no-store"
    }
)

api_security.add_security_policy(policy)
```

### API Key Management

```python
# Create API key with custom permissions
permissions = APIKeyPermissions(
    scopes={"read", "write"},
    allowed_endpoints={"/api/v1/data"},
    allowed_methods={"GET", "POST"},
    ip_whitelist={"203.0.113.0/24"}
)

quota = APIKeyQuota(
    requests_per_minute=200,
    requests_per_hour=10000,
    data_transfer_mb_per_day=2000
)

api_key = key_manager.create_api_key(
    name="Analytics Service Key",
    description="Key for analytics microservice",
    user_id="service_analytics",
    key_type=APIKeyType.ENTERPRISE,
    permissions=permissions,
    custom_quota=quota,
    expires_in_days=90
)
```

## Monitoring and Analytics

### Security Metrics

```python
# Get API security metrics
metrics = api_security.get_security_metrics()
{
    "requests_processed": 10000,
    "requests_blocked": 150,
    "validation_failures": 45,
    "rate_limit_violations": 25,
    "block_rate": 0.015,
    "validation_failure_rate": 0.0045
}
```

### API Key Analytics

```python
# Get detailed API key analytics
analytics = key_manager.get_api_key_analytics(api_key.key_id)
{
    "usage_stats": {
        "total_requests": 5000,
        "requests_today": 250,
        "error_count": 12,
        "error_rate": 0.0024,
        "avg_response_time_ms": 145.2
    },
    "quota_usage": {
        "requests_per_minute": {
            "used": 45,
            "limit": 200,
            "percentage": 22.5
        }
    }
}
```

### System-Wide Analytics

```python
# Get system analytics
system_stats = key_manager.get_system_analytics()
{
    "total_keys": 150,
    "active_keys": 120,
    "suspended_keys": 5,
    "revoked_keys": 25,
    "total_requests": 1000000,
    "error_rate": 0.002
}
```

## Testing

### Rate Limiting Tests

```python
@pytest.mark.asyncio
async def test_rate_limiting():
    # Create middleware
    middleware = APISecurityMiddleware(app, logger)
    
    # Simulate requests from same IP
    client_ip = "192.168.1.100"
    policy = middleware._get_security_policy("/api/v1/test")
    
    # First requests should pass
    for i in range(50):
        blocked = await middleware._check_rate_limits(
            mock_request, client_ip, policy
        )
        assert blocked is False
    
    # Exceed rate limit
    rule = middleware.rate_limit_rules["default_ip"]
    for i in range(rule.requests_per_minute):
        await middleware._is_rate_limited(
            f"ip:{client_ip}", rule, datetime.utcnow()
        )
    
    # Next request should be blocked
    blocked = await middleware._is_rate_limited(
        f"ip:{client_ip}", rule, datetime.utcnow()
    )
    assert blocked is True
```

### Input Validation Tests

```python
@pytest.mark.asyncio
async def test_input_validation():
    middleware = APISecurityMiddleware(app, logger)
    
    # Test valid input
    request = create_mock_request({
        "username": "testuser",
        "email": "test@example.com"
    })
    
    error = await middleware._validate_and_sanitize_input(
        request, "/api/v1/users"
    )
    assert error is None
    
    # Test invalid input
    request = create_mock_request({
        "username": "",  # Required field empty
        "email": "invalid-email"  # Invalid format
    })
    
    error = await middleware._validate_and_sanitize_input(
        request, "/api/v1/users"
    )
    assert error is not None
```

### API Key Management Tests

```python
def test_api_key_lifecycle():
    key_manager = AdvancedAPIKeyManager(logger)
    
    # Create key
    api_key = key_manager.create_api_key(
        name="Test Key",
        description="Test",
        user_id="user123",
        key_type=APIKeyType.STANDARD
    )
    
    # Verify key
    verified = key_manager.verify_api_key(api_key.raw_key)
    assert verified is not None
    
    # Suspend key
    success = key_manager.suspend_api_key(api_key.key_id)
    assert success is True
    assert api_key.status == APIKeyStatus.SUSPENDED
    
    # Suspended key should not verify
    verified = key_manager.verify_api_key(api_key.raw_key)
    assert verified is None
```

## Configuration

### Environment Variables

```bash
# API Security Settings
ENABLE_API_RATE_LIMITING=true
ENABLE_INPUT_VALIDATION=true
ENABLE_SECURITY_HEADERS=true
ENABLE_REQUEST_SANITIZATION=true

# Rate Limiting Configuration
DEFAULT_RATE_LIMIT_PER_MINUTE=60
DEFAULT_RATE_LIMIT_PER_HOUR=1000
DEFAULT_RATE_LIMIT_PER_DAY=10000

# Security Policy Configuration
DEFAULT_SECURITY_LEVEL=protected
CRITICAL_ENDPOINTS="/api/v1/security/auth/*,/api/v1/admin/*"
```

### Application Configuration

```python
# config/api_security.py
from app.middleware.api_security import APISecurityMiddleware, SecurityPolicy

API_SECURITY_CONFIG = {
    "enable_rate_limiting": True,
    "enable_input_validation": True,
    "enable_security_headers": True,
    "enable_request_sanitization": True
}

CUSTOM_SECURITY_POLICIES = [
    SecurityPolicy(
        endpoint_pattern=r"^/api/v1/payments/.*",
        security_level=SecurityLevel.CRITICAL,
        require_auth=True,
        rate_limit_rules=["critical_endpoints"],
        response_headers={
            "X-PCI-Compliant": "true"
        }
    )
]
```

## Best Practices

### Rate Limiting

1. **Tiered Rate Limits**: Use different limits for different user types
2. **Burst Allowances**: Allow short bursts of activity
3. **Graceful Degradation**: Provide meaningful error messages
4. **Exemption Lists**: Whitelist trusted IPs and services

### Input Validation

1. **Whitelist Approach**: Define allowed patterns rather than blocked ones
2. **Layered Validation**: Validate at multiple levels (client, API, business logic)
3. **Error Handling**: Don't expose internal validation details
4. **Performance**: Use efficient validation patterns

### API Key Management

1. **Key Rotation**: Regularly rotate API keys
2. **Least Privilege**: Grant minimum required permissions
3. **Monitoring**: Track API key usage and anomalies
4. **Lifecycle Management**: Have clear policies for key creation, suspension, and revocation

### Security Headers

1. **Content Security Policy**: Use strict CSP for critical endpoints
2. **HSTS**: Always use HTTPS in production
3. **Cache Control**: Prevent caching of sensitive data
4. **Information Disclosure**: Remove server identification headers

## Troubleshooting

### Common Issues

**Rate Limiting False Positives:**
```bash
# Check rate limit status
curl -H "Authorization: Bearer <token>" \
     https://api.example.com/api/v1/security/rate-limit/status

# Clear rate limit cache if needed
curl -X DELETE -H "Authorization: Bearer <admin-token>" \
     https://api.example.com/api/v1/security/rate-limit/cache
```

**Input Validation Errors:**
```bash
# Test input validation
curl -X POST -H "Content-Type: application/json" \
     -d '{"username":"test<script>","email":"invalid"}' \
     https://api.example.com/api/v1/users

# Check validation rules
curl -H "Authorization: Bearer <admin-token>" \
     https://api.example.com/api/v1/security/validation-rules
```

**API Key Issues:**
```bash
# Verify API key
curl -H "X-API-Key: <key>" \
     https://api.example.com/api/v1/security/api-keys/verify

# Check key permissions
curl -H "X-API-Key: <key>" \
     https://api.example.com/api/v1/security/api-keys/permissions
```

### Debug Mode

```python
# Enable debug logging
import logging
logging.getLogger("app.middleware.api_security").setLevel(logging.DEBUG)
logging.getLogger("app.security.api_key_manager").setLevel(logging.DEBUG)
```

## Support

For issues related to API security hardening:
1. Check security metrics and logs
2. Review rate limiting and validation rules
3. Verify API key permissions and quotas
4. Test with debug logging enabled
5. Contact security team for critical issues

The API Security Hardening system provides comprehensive protection for REST APIs while maintaining performance and usability. Regular monitoring and tuning ensure optimal security posture.