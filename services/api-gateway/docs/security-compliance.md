# Security & Compliance System Documentation

## Overview

The API Gateway implements a comprehensive multi-layer security system with advanced authentication, threat detection, and compliance monitoring. This system provides enterprise-grade security features including:

- **Advanced Authentication**: JWT, API keys, multi-factor authentication, role-based access control
- **Threat Detection**: Real-time security scanning for SQL injection, XSS, path traversal, and other attacks
- **Compliance Monitoring**: GDPR, SOC2, ISO27001, HIPAA compliance with automated assessments
- **Security Middleware**: Multi-layer protection with IP blocking, rate limiting, and audit trails

## Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    Security Middleware                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌────────────┐ │
│  │ IP Blocking │ │Rate Limiting│ │ Threat Det. │ │    Auth    │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
┌───────────────┐   ┌──────────────────┐   ┌──────────────────┐
│AdvancedAuth   │   │SecurityScanner   │   │ComplianceManager │
│Manager        │   │                  │   │                  │
│• JWT Tokens   │   │• Pattern Match   │   │• Audit Trails    │
│• API Keys     │   │• ML Detection    │   │• GDPR/SOC2/ISO   │
│• MFA Support  │   │• Bot Detection   │   │• Data Retention  │
│• RBAC         │   │• Vulnerability   │   │• Consent Mgmt    │
└───────────────┘   └──────────────────┘   └──────────────────┘
```

## Authentication System

### JWT Authentication

The system uses JWT tokens with configurable expiration and refresh capabilities.

**Token Structure:**
```json
{
  "sub": "user_id",
  "username": "john_doe", 
  "email": "john@example.com",
  "roles": ["user", "developer"],
  "permissions": ["read", "write"],
  "iat": 1640995200,
  "exp": 1641001200,
  "type": "access"
}
```

**Configuration:**
```python
auth_config = AuthConfig(
    jwt_secret_key="your-secret-key",
    jwt_algorithm="HS256", 
    jwt_access_token_expire_minutes=30,
    jwt_refresh_token_expire_days=7
)
```

### API Key Authentication

API keys provide programmatic access with scope-based permissions.

**Features:**
- Secure key generation with SHA-256 hashing
- Scoped permissions (read, write, admin)
- Expiration dates and usage tracking
- Rate limiting per key

**Usage:**
```bash
curl -H "X-API-Key: your-api-key" \
     https://api.example.com/api/v1/endpoint
```

### Role-Based Access Control (RBAC)

**Roles:**
- `ADMIN`: Full system access
- `DEVELOPER`: Development and monitoring access
- `ANALYST`: Read and monitoring access
- `USER`: Basic read/write access
- `SERVICE`: Service-to-service communication
- `GUEST`: Read-only access

**Permissions:**
- `READ`: Read data and configurations
- `WRITE`: Modify data and configurations  
- `DELETE`: Delete resources
- `ADMIN`: Administrative operations
- `EXECUTE`: Execute operations
- `MONITOR`: Access monitoring data
- `CONFIG`: Modify system configuration

## Security Scanning

### Threat Detection Patterns

The security scanner uses pattern matching and behavioral analysis to detect threats:

**SQL Injection Detection:**
```python
sql_patterns = [
    r"(\b(union|select|insert|update|delete|drop|create|alter)\b)",
    r"(\'|\"|;|--|\||&|\*|\%)",
    r"(\b(or|and)\s+\d+\s*=\s*\d+)",
    r"(\b(exec|execute|sp_|xp_)\b)"
]
```

**XSS Detection:**
```python
xss_patterns = [
    r"<script[^>]*>.*?</script>",
    r"javascript:",
    r"on\w+\s*=",
    r"<iframe[^>]*>.*?</iframe>"
]
```

**Path Traversal Detection:**
```python
path_traversal_patterns = [
    r"\.\.[\\/]",
    r"[\\/]etc[\\/]passwd",
    r"[\\/]windows[\\/]system32"
]
```

### Vulnerability Scanning

**Scan Types:**
- **Basic**: Pattern-based detection
- **Advanced**: Behavioral analysis + patterns
- **Deep**: Full request/response analysis

**Risk Scoring:**
- **Critical (9-10)**: Immediate threat, auto-block
- **High (7-8)**: Serious threat, alert + manual review
- **Medium (4-6)**: Moderate risk, log + monitor
- **Low (1-3)**: Minimal risk, log only

### Bot Detection

**Detection Methods:**
- User-Agent analysis
- Request pattern analysis
- Rate pattern detection
- Browser fingerprinting

**Common Bot Signatures:**
```python
bot_signatures = [
    "bot", "crawler", "spider", "scraper",
    "python-requests", "curl", "wget",
    "automated", "headless"
]
```

## Compliance Framework

### Supported Frameworks

**GDPR (General Data Protection Regulation):**
- Data processing legal basis tracking
- Consent management and withdrawal
- Data subject rights (access, rectification, erasure)
- Data protection by design and default
- Privacy impact assessments

**SOC 2 (Service Organization Control 2):**
- Access control monitoring
- System monitoring and incident response
- Change management tracking
- Data encryption and security

**ISO 27001:**
- Information security management
- Risk assessment and treatment
- Security incident management
- Business continuity planning

**HIPAA (Health Insurance Portability and Accountability Act):**
- Protected health information (PHI) handling
- Access controls and audit logs
- Data encryption and transmission security
- Breach notification procedures

### Audit Trail Management

**Event Types:**
- `DATA_ACCESS`: Data read operations
- `DATA_MODIFICATION`: Data write/update operations
- `DATA_DELETION`: Data deletion operations
- `DATA_EXPORT`: Data export operations
- `AUTHENTICATION`: Login/logout events
- `AUTHORIZATION`: Permission checks
- `CONFIGURATION_CHANGE`: System configuration changes
- `SECURITY_EVENT`: Security-related events
- `PRIVACY_EVENT`: Privacy-related events
- `COMPLIANCE_VIOLATION`: Compliance violations

**Audit Event Structure:**
```json
{
  "event_id": "AUDIT_20231201_143052_a1b2c3",
  "event_type": "DATA_ACCESS",
  "timestamp": "2023-12-01T14:30:52Z",
  "user_id": "user_123",
  "session_id": "session_abc",
  "ip_address": "192.168.1.100",
  "user_agent": "Mozilla/5.0...",
  "resource": "/api/v1/users/profile",
  "action": "GET /api/v1/users/profile",
  "outcome": "success",
  "details": {
    "status_code": 200,
    "response_size": 1024
  },
  "data_classification": "PII",
  "compliance_frameworks": ["GDPR", "SOC2"],
  "retention_period": 2557
}
```

### Data Retention Policies

**Default Retention Periods:**
- **Audit Logs**: 7 years (2557 days)
- **User Data**: 3 years (1095 days) 
- **Session Data**: 3 months (90 days)
- **Security Logs**: 3 years (1095 days)

**Automatic Cleanup:**
- Daily cleanup process removes expired data
- Secure deletion methods used
- Cleanup events are audited

### Consent Management

**GDPR Consent Tracking:**
```python
consent_record = {
    "consent_id": "CONSENT_user123_1640995200",
    "user_id": "user123",
    "consent_type": "marketing",
    "consent_given": True,
    "legal_basis": "consent",
    "purpose": "marketing communications",
    "data_categories": ["email", "preferences"],
    "recorded_at": "2023-12-01T14:30:52Z",
    "ip_address": "192.168.1.100"
}
```

## Security Middleware

### Multi-Layer Protection

The security middleware implements five layers of protection:

**Layer 1: IP-based Filtering**
- Whitelist/blacklist checking
- Geographic blocking (optional)
- Temporary blocks for suspicious IPs

**Layer 2: Rate Limiting**
- Per-IP rate limiting
- Sliding window algorithm
- Configurable limits (per minute/hour)
- Temporary blocking for violations

**Layer 3: Threat Detection**
- Real-time request scanning
- Pattern-based threat detection
- Confidence scoring
- Automatic blocking for critical threats

**Layer 4: Authentication**
- JWT token validation
- API key verification
- Session management
- Multi-factor authentication support

**Layer 5: Authorization**
- Role-based access control
- Permission checking
- Resource-specific access control
- Endpoint security levels

### Configuration

```python
security_config = SecurityConfig(
    enable_threat_detection=True,
    enable_rate_limiting=True,
    enable_ip_blocking=True,
    enable_compliance_logging=True,
    max_requests_per_minute=60,
    max_requests_per_hour=1000,
    auto_block_threshold=10,
    suspicious_endpoints=["/admin", "/config"],
    high_security_endpoints=["/auth", "/users"]
)
```

### Security Headers

The middleware automatically adds security headers:

```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'
```

## API Endpoints

### Authentication Endpoints

**Login:**
```http
POST /api/v1/security/auth/login
Content-Type: application/json

{
  "username": "john_doe",
  "password": "secure_password"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user_info": {
    "user_id": "user_123",
    "username": "john_doe",
    "roles": ["user"],
    "session_id": "session_abc"
  }
}
```

**Refresh Token:**
```http
POST /api/v1/security/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Logout:**
```http
POST /api/v1/security/auth/logout
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### User Management Endpoints

**Create User (Admin only):**
```http
POST /api/v1/security/users
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
Content-Type: application/json

{
  "username": "new_user",
  "email": "user@example.com",
  "password": "secure_password",
  "roles": ["user"]
}
```

**Change Password:**
```http
PUT /api/v1/security/users/password  
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
Content-Type: application/json

{
  "old_password": "current_password",
  "new_password": "new_secure_password"
}
```

### API Key Management

**Create API Key:**
```http
POST /api/v1/security/api-keys
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
Content-Type: application/json

{
  "name": "My API Key",
  "scopes": ["read", "write"],
  "expires_in_days": 90
}
```

**List API Keys:**
```http
GET /api/v1/security/api-keys
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Revoke API Key:**
```http
DELETE /api/v1/security/api-keys/{key_id}
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### Security Monitoring

**Get Security Metrics:**
```http
GET /api/v1/security/metrics
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Response:**
```json
{
  "requests_processed": 10000,
  "threats_blocked": 25,
  "auth_failures": 15,
  "rate_limit_violations": 8,
  "blocked_ips_count": 5,
  "monitored_ips_count": 100,
  "active_sessions": 45,
  "api_keys_count": 12
}
```

**Get Threat Summary:**
```http
GET /api/v1/security/threats
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### Vulnerability Scanning

**Run Vulnerability Scan:**
```http
POST /api/v1/security/scan
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
Content-Type: application/json

{
  "target_url": "https://example.com/api/endpoint",
  "scan_type": "advanced"
}
```

### IP Management

**Add IP to Blacklist:**
```http
POST /api/v1/security/ip/blacklist
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
Content-Type: application/json

{
  "ip_address": "192.168.1.100",
  "duration_hours": 24,
  "reason": "Suspicious activity detected"
}
```

**Remove IP from Blacklist:**
```http
DELETE /api/v1/security/ip/blacklist/192.168.1.100
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### Compliance Reporting

**Get Compliance Report:**
```http
GET /api/v1/security/compliance/gdpr
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Run Compliance Assessment:**
```http
POST /api/v1/security/compliance/gdpr/assess
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Get Audit Events:**
```http
GET /api/v1/security/audit/events?user_id=user123&limit=100
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

## Configuration

### Environment Variables

```bash
# JWT Configuration
JWT_SECRET_KEY=your-super-secret-key-change-in-production
JWT_ALGORITHM=HS256

# Security Features
ENABLE_SECURITY_SCANNING=true
ENABLE_COMPLIANCE_MONITORING=true
SECURITY_LOG_LEVEL=info

# Rate Limiting
ENABLE_RATE_LIMITING=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60

# Authentication
ENABLE_AUTHENTICATION=true
```

### Security Configuration File

```python
# config/security.py
from app.security.advanced_auth import AuthConfig
from app.middleware.security import SecurityConfig

# Authentication Configuration
AUTH_CONFIG = AuthConfig(
    jwt_secret_key=os.getenv("JWT_SECRET_KEY"),
    jwt_algorithm="HS256",
    jwt_access_token_expire_minutes=30,
    jwt_refresh_token_expire_days=7,
    password_min_length=8,
    max_login_attempts=5,
    lockout_duration_minutes=15,
    require_mfa=False,
    session_timeout_minutes=60
)

# Security Middleware Configuration  
SECURITY_CONFIG = SecurityConfig(
    enable_threat_detection=True,
    enable_rate_limiting=True,
    enable_ip_blocking=True,
    enable_compliance_logging=True,
    max_requests_per_minute=60,
    max_requests_per_hour=1000,
    auto_block_threshold=10,
    suspicious_endpoints=["/admin", "/config", "/debug"],
    high_security_endpoints=["/auth", "/users", "/keys"]
)
```

## Testing

### Running Security Tests

```bash
# Run all security tests
pytest app/tests/test_security.py -v

# Run specific test categories
pytest app/tests/test_security.py::TestAdvancedAuthManager -v
pytest app/tests/test_security.py::TestSecurityScanner -v
pytest app/tests/test_security.py::TestComplianceManager -v
pytest app/tests/test_security.py::TestSecurityMiddleware -v
```

### Test Coverage

The security test suite covers:
- **Authentication**: Password hashing, JWT tokens, API keys
- **Authorization**: Role-based access control, permissions
- **Threat Detection**: SQL injection, XSS, path traversal, bot detection
- **Compliance**: Audit logging, consent management, data retention
- **Middleware**: IP blocking, rate limiting, security headers

### Example Test

```python
@pytest.mark.asyncio
async def test_sql_injection_detection(scanner):
    """Test SQL injection pattern detection"""
    request = Mock(spec=Request)
    request.query_params = {"id": "1' OR '1'='1"}
    
    threats = await scanner.scan_request(request)
    
    sql_threats = [t for t in threats 
                  if t.vulnerability_type == VulnerabilityType.SQL_INJECTION]
    assert len(sql_threats) > 0
    assert sql_threats[0].threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]
```

## Monitoring and Alerting

### Security Metrics

The system collects comprehensive security metrics:

- **Request Metrics**: Total requests, blocked requests, processing times
- **Authentication Metrics**: Login attempts, failures, session count
- **Threat Metrics**: Threats detected, blocked IPs, vulnerability scans
- **Compliance Metrics**: Audit events, consent records, assessments

### Alerting Rules

**Critical Alerts:**
- Multiple critical threats from same IP
- Authentication failures exceeding threshold
- Compliance violations detected
- System component failures

**Warning Alerts:**
- Unusual traffic patterns
- High threat detection rates
- API key usage anomalies
- Session timeout increases

### Integration with Monitoring Stack

The security system integrates with:
- **Prometheus**: Metrics collection and alerting
- **Grafana**: Security dashboards and visualizations
- **OpenTelemetry**: Distributed tracing for security events
- **Structured Logging**: Centralized log aggregation

## Best Practices

### Deployment Security

1. **Change Default Secrets**: Update all default passwords and keys
2. **Enable HTTPS**: Use TLS 1.2+ for all communications
3. **Network Segmentation**: Isolate security components
4. **Regular Updates**: Keep dependencies updated
5. **Backup Encryption**: Encrypt all backup data

### Operational Security

1. **Regular Security Assessments**: Run compliance assessments quarterly
2. **Log Monitoring**: Monitor security logs continuously
3. **Incident Response**: Have incident response procedures ready
4. **Access Reviews**: Review user access regularly
5. **Key Rotation**: Rotate keys and tokens regularly

### Development Security

1. **Security Testing**: Include security tests in CI/CD
2. **Code Reviews**: Review security-related code thoroughly
3. **Dependency Scanning**: Scan dependencies for vulnerabilities
4. **Static Analysis**: Use static analysis tools
5. **Penetration Testing**: Conduct regular penetration tests

## Troubleshooting

### Common Issues

**Authentication Issues:**
```bash
# Check JWT token validity
curl -H "Authorization: Bearer <token>" \
     https://api.example.com/api/v1/security/auth/verify

# Check user permissions
curl -H "Authorization: Bearer <token>" \
     https://api.example.com/api/v1/security/users/permissions
```

**Rate Limiting Issues:**
```bash
# Check current rate limits
curl -H "X-API-Key: <key>" \
     https://api.example.com/api/v1/security/metrics

# Check IP blocking status
curl https://api.example.com/api/v1/security/ip/status/192.168.1.100
```

**Threat Detection Issues:**
```bash
# Check threat detection logs
docker logs api-gateway | grep "threat_detected"

# Adjust detection sensitivity
curl -X PUT -H "Authorization: Bearer <token>" \
     -d '{"sensitivity": "medium"}' \
     https://api.example.com/api/v1/security/config/threats
```

### Debugging

**Enable Debug Logging:**
```python
import logging
logging.getLogger("app.security").setLevel(logging.DEBUG)
```

**Check Component Status:**
```python
# In Python shell
from app.main import app
print("Auth Manager:", app.state.auth_manager)
print("Security Scanner:", app.state.security_scanner)
print("Compliance Manager:", app.state.compliance_manager)
```

## Support and Updates

For security issues or questions:
1. Review this documentation
2. Check the test suite for examples
3. Review security logs and metrics
4. Contact the security team for critical issues

Regular security updates are released quarterly with:
- New threat detection patterns
- Compliance framework updates
- Security vulnerability fixes
- Performance improvements