"""
Advanced Security Middleware
Multi-layer security with threat detection, authentication, and compliance monitoring
"""
import time
import asyncio
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass
import ipaddress
from datetime import datetime, timedelta

from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from starlette.responses import JSONResponse

from app.security.advanced_auth import AdvancedAuthManager, AuthContext, SecurityLevel
from app.security.security_scanner import SecurityScanner, SecurityThreat, ThreatLevel
from app.security.compliance import ComplianceManager, AuditEventType, DataClassification
from shared.monitoring.structured_logger import StructuredLogger
from shared.monitoring.correlation import get_correlation_id

@dataclass
class SecurityConfig:
    """Security middleware configuration"""
    enable_threat_detection: bool = True
    enable_rate_limiting: bool = True
    enable_ip_blocking: bool = True
    enable_geo_blocking: bool = False
    enable_compliance_logging: bool = True
    block_suspicious_user_agents: bool = True
    max_requests_per_minute: int = 60
    max_requests_per_hour: int = 1000
    ip_whitelist: List[str] = None
    ip_blacklist: List[str] = None
    blocked_countries: List[str] = None
    suspicious_endpoints: List[str] = None
    high_security_endpoints: List[str] = None
    auto_block_threshold: int = 10  # Auto-block after N high-severity threats

@dataclass 
class SecurityContext:
    """Security context for requests"""
    request_id: str
    ip_address: str
    user_agent: str
    threat_level: ThreatLevel
    threats_detected: List[SecurityThreat]
    auth_context: Optional[AuthContext] = None
    blocked: bool = False
    block_reason: Optional[str] = None
    security_level: SecurityLevel = SecurityLevel.MEDIUM

class SecurityMiddleware(BaseHTTPMiddleware):
    """Advanced security middleware with comprehensive threat protection"""
    
    def __init__(
        self,
        app: ASGIApp,
        auth_manager: AdvancedAuthManager,
        security_scanner: SecurityScanner,
        compliance_manager: ComplianceManager,
        logger: StructuredLogger,
        config: Optional[SecurityConfig] = None
    ):
        super().__init__(app)
        self.auth_manager = auth_manager
        self.security_scanner = security_scanner
        self.compliance_manager = compliance_manager
        self.logger = logger
        self.config = config or SecurityConfig()
        
        # Rate limiting and blocking state
        self.rate_limits: Dict[str, List[datetime]] = {}
        self.blocked_ips: Dict[str, datetime] = {}
        self.threat_counts: Dict[str, int] = {}
        
        # Security metrics
        self.requests_processed = 0
        self.threats_blocked = 0
        self.auth_failures = 0
        self.rate_limit_violations = 0
        
        # Initialize IP lists
        self.ip_whitelist = set(self.config.ip_whitelist or [])
        self.ip_blacklist = set(self.config.ip_blacklist or [])
        
        self.logger.info("Security middleware initialized",
                        threat_detection=self.config.enable_threat_detection,
                        rate_limiting=self.config.enable_rate_limiting,
                        compliance_logging=self.config.enable_compliance_logging)
    
    async def dispatch(self, request: Request, call_next):
        """Process request through security layers"""
        start_time = time.time()
        correlation_id = get_correlation_id()
        
        # Extract request information
        ip_address = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        method = request.method
        path = request.url.path
        
        self.requests_processed += 1
        
        # Create security context
        security_context = SecurityContext(
            request_id=correlation_id,
            ip_address=ip_address,
            user_agent=user_agent,
            threat_level=ThreatLevel.LOW,
            threats_detected=[]
        )
        
        try:
            # Security Layer 1: IP-based filtering
            if self.config.enable_ip_blocking:
                if await self._check_ip_blocking(security_context):
                    return self._create_blocked_response("IP blocked", security_context)
            
            # Security Layer 2: Rate limiting
            if self.config.enable_rate_limiting:
                if await self._check_rate_limiting(security_context):
                    return self._create_blocked_response("Rate limit exceeded", security_context)
            
            # Security Layer 3: Threat detection
            if self.config.enable_threat_detection:
                await self._detect_threats(request, security_context)
                
                # Block high-severity threats
                critical_threats = [t for t in security_context.threats_detected 
                                  if t.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]]
                
                if critical_threats:
                    await self._handle_critical_threats(security_context, critical_threats)
                    if security_context.blocked:
                        return self._create_blocked_response(security_context.block_reason, security_context)
            
            # Security Layer 4: Authentication (if required)
            if self._requires_authentication(path):
                auth_context = await self.auth_manager.authenticate_request(request)
                security_context.auth_context = auth_context
                
                if not auth_context:
                    self.auth_failures += 1
                    await self._log_security_event(
                        security_context,
                        "authentication_failed",
                        "Authentication required but not provided"
                    )
                    return self._create_auth_required_response()
                
                # Authorization check
                if not await self._check_authorization(auth_context, path, method):
                    await self._log_security_event(
                        security_context,
                        "authorization_failed",
                        "Insufficient permissions"
                    )
                    return self._create_forbidden_response()
            
            # Security Layer 5: Endpoint-specific security
            security_context.security_level = self._determine_security_level(path)
            
            # Add security context to request state
            request.state.security_context = security_context
            
            # Process request
            response = await call_next(request)
            
            # Post-processing security checks
            await self._post_process_security(request, response, security_context)
            
            # Add security headers
            self._add_security_headers(response, security_context)
            
            # Log compliance events
            if self.config.enable_compliance_logging:
                await self._log_compliance_event(request, response, security_context)
            
            return response
            
        except Exception as e:
            self.logger.error("Security middleware error",
                            correlation_id=correlation_id,
                            error=str(e),
                            ip_address=ip_address)
            
            # Log security incident
            await self._log_security_event(
                security_context,
                "middleware_error",
                f"Security middleware error: {str(e)}"
            )
            
            # Return generic error to avoid information disclosure
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "correlation_id": correlation_id
                }
            )
        
        finally:
            # Record processing time
            processing_time = time.time() - start_time
            self.logger.debug("Security middleware processed request",
                            correlation_id=correlation_id,
                            processing_time_ms=processing_time * 1000,
                            threats_detected=len(security_context.threats_detected),
                            blocked=security_context.blocked)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address considering proxies"""
        # Check for forwarded headers (in order of preference)
        forwarded_headers = [
            "x-forwarded-for",
            "x-real-ip", 
            "x-client-ip",
            "cf-connecting-ip"  # Cloudflare
        ]
        
        for header in forwarded_headers:
            if header in request.headers:
                ip = request.headers[header].split(",")[0].strip()
                if self._is_valid_ip(ip):
                    return ip
        
        # Fallback to direct connection IP
        return request.client.host if request.client else "unknown"
    
    def _is_valid_ip(self, ip_str: str) -> bool:
        """Validate IP address format"""
        try:
            ipaddress.ip_address(ip_str)
            return True
        except ValueError:
            return False
    
    async def _check_ip_blocking(self, security_context: SecurityContext) -> bool:
        """Check if IP should be blocked"""
        ip = security_context.ip_address
        
        # Check whitelist (bypass all other checks)
        if ip in self.ip_whitelist:
            return False
        
        # Check blacklist
        if ip in self.ip_blacklist:
            security_context.blocked = True
            security_context.block_reason = "IP in blacklist"
            return True
        
        # Check temporary blocks
        if ip in self.blocked_ips:
            block_time = self.blocked_ips[ip]
            if datetime.utcnow() < block_time:
                security_context.blocked = True
                security_context.block_reason = "Temporarily blocked"
                return True
            else:
                # Block expired, remove it
                del self.blocked_ips[ip]
        
        return False
    
    async def _check_rate_limiting(self, security_context: SecurityContext) -> bool:
        """Check rate limiting violations"""
        ip = security_context.ip_address
        current_time = datetime.utcnow()
        
        # Initialize rate limit tracking for IP
        if ip not in self.rate_limits:
            self.rate_limits[ip] = []
        
        # Clean old requests (older than 1 hour)
        self.rate_limits[ip] = [
            req_time for req_time in self.rate_limits[ip]
            if current_time - req_time < timedelta(hours=1)
        ]
        
        # Add current request
        self.rate_limits[ip].append(current_time)
        
        # Check per-minute limit
        recent_requests = [
            req_time for req_time in self.rate_limits[ip]
            if current_time - req_time < timedelta(minutes=1)
        ]
        
        if len(recent_requests) > self.config.max_requests_per_minute:
            self.rate_limit_violations += 1
            security_context.blocked = True
            security_context.block_reason = f"Rate limit exceeded: {len(recent_requests)} requests per minute"
            
            # Temporary block for repeat offenders
            if len(recent_requests) > self.config.max_requests_per_minute * 2:
                self.blocked_ips[ip] = current_time + timedelta(minutes=15)
            
            return True
        
        # Check per-hour limit
        if len(self.rate_limits[ip]) > self.config.max_requests_per_hour:
            self.rate_limit_violations += 1
            security_context.blocked = True
            security_context.block_reason = f"Hourly rate limit exceeded: {len(self.rate_limits[ip])} requests per hour"
            
            # Longer block for excessive hourly usage
            self.blocked_ips[ip] = current_time + timedelta(hours=1)
            return True
        
        return False
    
    async def _detect_threats(self, request: Request, security_context: SecurityContext):
        """Detect security threats in request"""
        try:
            threats = await self.security_scanner.scan_request(request)
            security_context.threats_detected = threats
            
            if threats:
                # Determine overall threat level
                max_threat_level = max((t.threat_level for t in threats), default=ThreatLevel.LOW)
                security_context.threat_level = max_threat_level
                
                # Count threats for this IP
                ip = security_context.ip_address
                if ip not in self.threat_counts:
                    self.threat_counts[ip] = 0
                self.threat_counts[ip] += len(threats)
                
                self.logger.warning("Security threats detected",
                                  correlation_id=security_context.request_id,
                                  ip_address=ip,
                                  threats_count=len(threats),
                                  max_threat_level=max_threat_level.value,
                                  threat_types=[t.threat_type.value for t in threats])
        
        except Exception as e:
            self.logger.error("Threat detection error",
                            correlation_id=security_context.request_id,
                            error=str(e))
    
    async def _handle_critical_threats(
        self,
        security_context: SecurityContext,
        critical_threats: List[SecurityThreat]
    ):
        """Handle critical security threats"""
        ip = security_context.ip_address
        
        # Log all critical threats
        for threat in critical_threats:
            await self._log_security_event(
                security_context,
                "critical_threat_detected",
                f"{threat.title}: {threat.description}",
                {
                    "threat_id": threat.threat_id,
                    "threat_type": threat.threat_type.value,
                    "confidence_score": threat.confidence_score,
                    "evidence": threat.evidence
                }
            )
        
        # Auto-block based on threat count
        if self.threat_counts.get(ip, 0) >= self.config.auto_block_threshold:
            security_context.blocked = True
            security_context.block_reason = f"Auto-blocked: {len(critical_threats)} critical threats detected"
            
            # Block IP for 24 hours
            self.blocked_ips[ip] = datetime.utcnow() + timedelta(hours=24)
            self.threats_blocked += 1
            
            self.logger.critical("IP auto-blocked due to critical threats",
                               ip_address=ip,
                               threat_count=self.threat_counts[ip],
                               critical_threats=len(critical_threats))
    
    def _requires_authentication(self, path: str) -> bool:
        """Check if endpoint requires authentication"""
        # Public endpoints that don't require authentication
        public_endpoints = [
            "/health",
            "/docs",
            "/openapi.json",
            "/api/v1/health",
            "/api/v1/metrics"  # Public metrics
        ]
        
        for public_path in public_endpoints:
            if path.startswith(public_path):
                return False
        
        # All API endpoints require authentication by default
        return path.startswith("/api/")
    
    async def _check_authorization(self, auth_context: AuthContext, path: str, method: str) -> bool:
        """Check if user is authorized for the requested action"""
        from app.security.advanced_auth import Permission
        
        # Admin endpoints require admin permission
        if "/admin" in path:
            return self.auth_manager.check_permission(auth_context, Permission.ADMIN)
        
        # Configuration endpoints require config permission
        if "/config" in path or "/settings" in path:
            return self.auth_manager.check_permission(auth_context, Permission.CONFIG)
        
        # Monitor endpoints require monitor permission
        if "/metrics" in path or "/observability" in path:
            return self.auth_manager.check_permission(auth_context, Permission.MONITOR)
        
        # Write operations require write permission
        if method in ["POST", "PUT", "PATCH", "DELETE"]:
            return self.auth_manager.check_permission(auth_context, Permission.WRITE)
        
        # Read operations require read permission
        return self.auth_manager.check_permission(auth_context, Permission.READ)
    
    def _determine_security_level(self, path: str) -> SecurityLevel:
        """Determine security level required for endpoint"""
        # Critical security endpoints
        if any(critical in path for critical in ["/admin", "/config", "/auth"]):
            return SecurityLevel.CRITICAL
        
        # High security endpoints
        if any(high in path for high in ["/users", "/keys", "/secrets"]):
            return SecurityLevel.HIGH
        
        # Medium security for API endpoints
        if path.startswith("/api/"):
            return SecurityLevel.MEDIUM
        
        # Low security for public endpoints
        return SecurityLevel.LOW
    
    async def _post_process_security(
        self,
        request: Request,
        response: Response,
        security_context: SecurityContext
    ):
        """Post-process security after request handling"""
        
        # Check for potential data leakage in error responses
        if response.status_code >= 400:
            await self._check_error_response_security(request, response, security_context)
        
        # Monitor for unusual response patterns
        if response.status_code == 200 and hasattr(response, 'body'):
            await self._monitor_response_patterns(request, response, security_context)
    
    async def _check_error_response_security(
        self,
        request: Request,
        response: Response,
        security_context: SecurityContext
    ):
        """Check error responses for information disclosure"""
        
        # Log authentication/authorization failures
        if response.status_code in [401, 403]:
            await self._log_security_event(
                security_context,
                "access_denied",
                f"Access denied: {response.status_code}",
                {
                    "status_code": response.status_code,
                    "endpoint": request.url.path,
                    "method": request.method
                }
            )
    
    async def _monitor_response_patterns(
        self,
        request: Request,
        response: Response,
        security_context: SecurityContext
    ):
        """Monitor response patterns for anomalies"""
        
        # This could include checking for:
        # - Unusual response sizes
        # - Suspicious response content
        # - Data access patterns
        
        pass  # Placeholder for advanced monitoring
    
    def _add_security_headers(self, response: Response, security_context: SecurityContext):
        """Add security headers to response"""
        
        # Basic security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Strict Transport Security (HTTPS only)
        if hasattr(response, 'url') and str(response.url).startswith('https'):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'"
        )
        
        # Add security context headers for debugging (non-production)
        if not self.config.enable_compliance_logging:  # Debug mode
            response.headers["X-Security-Level"] = security_context.security_level.value
            response.headers["X-Threats-Detected"] = str(len(security_context.threats_detected))
            if security_context.auth_context:
                response.headers["X-Auth-Method"] = security_context.auth_context.auth_method.value
    
    async def _log_security_event(
        self,
        security_context: SecurityContext,
        event_type: str,
        description: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log security event for audit and compliance"""
        
        user_id = None
        if security_context.auth_context:
            user_id = security_context.auth_context.user_id
        
        event_details = {
            "event_type": event_type,
            "description": description,
            "ip_address": security_context.ip_address,
            "user_agent": security_context.user_agent,
            "threat_level": security_context.threat_level.value,
            "threats_count": len(security_context.threats_detected)
        }
        
        if details:
            event_details.update(details)
        
        await self.compliance_manager.log_audit_event(
            event_type=AuditEventType.SECURITY_EVENT,
            user_id=user_id,
            resource="security_middleware",
            action=event_type,
            outcome="detected" if not security_context.blocked else "blocked",
            session_id=security_context.auth_context.session_id if security_context.auth_context else None,
            ip_address=security_context.ip_address,
            user_agent=security_context.user_agent,
            details=event_details,
            data_classification=DataClassification.CONFIDENTIAL
        )
    
    async def _log_compliance_event(
        self,
        request: Request,
        response: Response,
        security_context: SecurityContext
    ):
        """Log compliance event for audit trail"""
        
        # Determine if this is a data access event
        data_classification = None
        if "/users" in request.url.path or "/profile" in request.url.path:
            data_classification = DataClassification.PII
        elif "/admin" in request.url.path:
            data_classification = DataClassification.CONFIDENTIAL
        
        # Log data access events
        if request.method == "GET" and data_classification:
            await self.compliance_manager.log_audit_event(
                event_type=AuditEventType.DATA_ACCESS,
                user_id=security_context.auth_context.user_id if security_context.auth_context else None,
                resource=request.url.path,
                action=f"{request.method} {request.url.path}",
                outcome="success" if response.status_code < 400 else "failure",
                session_id=security_context.auth_context.session_id if security_context.auth_context else None,
                ip_address=security_context.ip_address,
                user_agent=security_context.user_agent,
                details={
                    "status_code": response.status_code,
                    "endpoint": request.url.path,
                    "method": request.method
                },
                data_classification=data_classification
            )
        
        # Log data modification events
        elif request.method in ["POST", "PUT", "PATCH", "DELETE"] and data_classification:
            await self.compliance_manager.log_audit_event(
                event_type=AuditEventType.DATA_MODIFICATION,
                user_id=security_context.auth_context.user_id if security_context.auth_context else None,
                resource=request.url.path,
                action=f"{request.method} {request.url.path}",
                outcome="success" if response.status_code < 400 else "failure",
                session_id=security_context.auth_context.session_id if security_context.auth_context else None,
                ip_address=security_context.ip_address,
                user_agent=security_context.user_agent,
                details={
                    "status_code": response.status_code,
                    "endpoint": request.url.path,
                    "method": request.method
                },
                data_classification=data_classification
            )
    
    def _create_blocked_response(self, reason: str, security_context: SecurityContext) -> JSONResponse:
        """Create response for blocked requests"""
        return JSONResponse(
            status_code=429,
            content={
                "error": "Request blocked",
                "reason": reason,
                "correlation_id": security_context.request_id,
                "retry_after": 900  # 15 minutes
            },
            headers={
                "Retry-After": "900",
                "X-Security-Block-Reason": reason
            }
        )
    
    def _create_auth_required_response(self) -> JSONResponse:
        """Create response for authentication required"""
        return JSONResponse(
            status_code=401,
            content={
                "error": "Authentication required",
                "message": "Valid authentication credentials are required"
            },
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )
    
    def _create_forbidden_response(self) -> JSONResponse:
        """Create response for forbidden access"""
        return JSONResponse(
            status_code=403,
            content={
                "error": "Forbidden",
                "message": "Insufficient permissions for this resource"
            }
        )
    
    # Management and monitoring methods
    
    def get_security_metrics(self) -> Dict[str, Any]:
        """Get security middleware metrics"""
        return {
            "requests_processed": self.requests_processed,
            "threats_blocked": self.threats_blocked,
            "auth_failures": self.auth_failures,
            "rate_limit_violations": self.rate_limit_violations,
            "blocked_ips_count": len(self.blocked_ips),
            "monitored_ips_count": len(self.rate_limits),
            "whitelist_size": len(self.ip_whitelist),
            "blacklist_size": len(self.ip_blacklist)
        }
    
    def add_ip_to_whitelist(self, ip: str):
        """Add IP to whitelist"""
        self.ip_whitelist.add(ip)
        self.logger.info("IP added to whitelist", ip=ip)
    
    def add_ip_to_blacklist(self, ip: str, duration_hours: int = 24):
        """Add IP to blacklist"""
        self.ip_blacklist.add(ip)
        
        # Also add to temporary blocks
        self.blocked_ips[ip] = datetime.utcnow() + timedelta(hours=duration_hours)
        
        self.logger.warning("IP added to blacklist", ip=ip, duration_hours=duration_hours)
    
    def remove_ip_from_blacklist(self, ip: str):
        """Remove IP from blacklist"""
        if ip in self.ip_blacklist:
            self.ip_blacklist.remove(ip)
        
        if ip in self.blocked_ips:
            del self.blocked_ips[ip]
        
        self.logger.info("IP removed from blacklist", ip=ip)
    
    def get_blocked_ips(self) -> Dict[str, datetime]:
        """Get currently blocked IPs"""
        current_time = datetime.utcnow()
        
        # Clean expired blocks
        expired_ips = [
            ip for ip, block_time in self.blocked_ips.items()
            if current_time > block_time
        ]
        
        for ip in expired_ips:
            del self.blocked_ips[ip]
        
        return self.blocked_ips.copy()
    
    def get_threat_summary(self) -> Dict[str, Any]:
        """Get threat detection summary"""
        return {
            "total_threats": sum(self.threat_counts.values()),
            "threatening_ips": len(self.threat_counts),
            "auto_blocked_ips": len([
                ip for ip, count in self.threat_counts.items()
                if count >= self.config.auto_block_threshold
            ]),
            "top_threatening_ips": sorted(
                self.threat_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
        }


class ComplianceSecurityMiddleware(SecurityMiddleware):
    """Enhanced security middleware with additional compliance features"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Additional compliance tracking
        self.pii_access_log: List[Dict[str, Any]] = []
        self.data_export_log: List[Dict[str, Any]] = []
        self.consent_violations: List[Dict[str, Any]] = []
    
    async def _log_compliance_event(
        self,
        request: Request,
        response: Response,
        security_context: SecurityContext
    ):
        """Enhanced compliance logging with additional privacy checks"""
        
        await super()._log_compliance_event(request, response, security_context)
        
        # Additional PII access logging
        if self._contains_pii_access(request):
            pii_event = {
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": security_context.auth_context.user_id if security_context.auth_context else None,
                "ip_address": security_context.ip_address,
                "endpoint": request.url.path,
                "method": request.method,
                "status_code": response.status_code
            }
            self.pii_access_log.append(pii_event)
            
            # Keep only last 10000 entries
            if len(self.pii_access_log) > 10000:
                self.pii_access_log = self.pii_access_log[-10000:]
    
    def _contains_pii_access(self, request: Request) -> bool:
        """Check if request involves PII access"""
        pii_endpoints = [
            "/users",
            "/profile",
            "/personal",
            "/contact",
            "/identity"
        ]
        
        return any(pii_endpoint in request.url.path for pii_endpoint in pii_endpoints)
    
    def get_compliance_metrics(self) -> Dict[str, Any]:
        """Get compliance-specific metrics"""
        base_metrics = self.get_security_metrics()
        
        base_metrics.update({
            "pii_access_events": len(self.pii_access_log),
            "data_export_events": len(self.data_export_log),
            "consent_violations": len(self.consent_violations),
            "compliance_events_last_24h": len([
                event for event in self.pii_access_log
                if datetime.fromisoformat(event["timestamp"]) > datetime.utcnow() - timedelta(days=1)
            ])
        })
        
        return base_metrics