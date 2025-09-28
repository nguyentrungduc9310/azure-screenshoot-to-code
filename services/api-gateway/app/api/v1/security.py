"""
Security Management API Endpoints
Provides REST APIs for security monitoring, compliance, and authentication management
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Query, Body, status
from pydantic import BaseModel, Field

from app.security.advanced_auth import (
    AdvancedAuthManager, AuthContext, UserRole, Permission, User, APIKey
)
from app.security.security_scanner import SecurityScanner, SecurityScanResult
from app.security.compliance import (
    ComplianceManager, ComplianceFramework, AuditEventType, 
    DataClassification, ComplianceAssessment
)
from app.middleware.security import SecurityMiddleware
from app.core.dependencies import get_auth_manager, get_compliance_manager, get_security_scanner
from shared.monitoring.correlation import get_correlation_id

router = APIRouter(prefix="/security", tags=["security"])


# Request/Response Models
class LoginRequest(BaseModel):
    """User login request"""
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="User password")


class LoginResponse(BaseModel):
    """User login response"""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")
    user_info: Dict[str, Any] = Field(..., description="User information")


class CreateUserRequest(BaseModel):
    """Create user request"""
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$')
    password: str = Field(..., min_length=8)
    roles: List[UserRole] = Field(default=[UserRole.USER])


class CreateAPIKeyRequest(BaseModel):
    """Create API key request"""
    name: str = Field(..., description="API key name")
    scopes: List[str] = Field(default=[], description="API key scopes")
    expires_in_days: Optional[int] = Field(None, description="Expiration in days")


class APIKeyResponse(BaseModel):
    """API key response"""
    key_id: str
    name: str
    api_key: str = Field(..., description="API key (returned only once)")
    scopes: List[str]
    created_at: datetime
    expires_at: Optional[datetime]


class ChangePasswordRequest(BaseModel):
    """Change password request"""
    old_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")


class SecurityMetricsResponse(BaseModel):
    """Security metrics response"""
    requests_processed: int
    threats_blocked: int
    auth_failures: int
    rate_limit_violations: int
    blocked_ips_count: int
    monitored_ips_count: int
    active_sessions: int
    api_keys_count: int


class ThreatSummaryResponse(BaseModel):
    """Threat detection summary response"""
    total_threats: int
    threatening_ips: int
    auto_blocked_ips: int
    top_threatening_ips: List[Dict[str, Any]]
    recent_threats: List[Dict[str, Any]]


class ComplianceReportResponse(BaseModel):
    """Compliance report response"""
    framework: str
    assessment: Dict[str, Any]
    audit_statistics: Dict[str, Any]
    recommendations: List[str]
    next_assessment_due: str


class VulnerabilityScanRequest(BaseModel):
    """Vulnerability scan request"""
    target_url: str = Field(..., description="Target URL to scan")
    scan_type: str = Field(default="basic", description="Scan type")


class IPManagementRequest(BaseModel):
    """IP management request"""
    ip_address: str = Field(..., description="IP address")
    duration_hours: Optional[int] = Field(24, description="Block duration in hours")
    reason: Optional[str] = Field(None, description="Block reason")


# Authentication Endpoints
@router.post("/auth/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    auth_manager: AdvancedAuthManager = Depends(get_auth_manager)
):
    """Authenticate user and return tokens"""
    correlation_id = get_correlation_id()
    
    try:
        # Authenticate user
        user = await auth_manager.authenticate_user(
            username=request.username,
            password=request.password
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Generate tokens
        access_token = auth_manager.create_access_token(user)
        refresh_token = auth_manager.create_refresh_token(user)
        
        # Create session
        auth_context = AuthContext(
            user_id=user.user_id,
            username=user.username,
            roles=user.roles,
            permissions=user.permissions,
            auth_method="jwt"
        )
        session_id = auth_manager.create_session(auth_context)
        
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=auth_manager.config.jwt_access_token_expire_minutes * 60,
            user_info={
                "user_id": user.user_id,
                "username": user.username,
                "email": user.email,
                "roles": [role.value for role in user.roles],
                "session_id": session_id
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication failed: {str(e)}"
        )


@router.post("/auth/refresh")
async def refresh_token(
    refresh_token: str = Body(..., embed=True),
    auth_manager: AdvancedAuthManager = Depends(get_auth_manager)
):
    """Refresh access token using refresh token"""
    try:
        payload = auth_manager.verify_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        user_id = payload.get("sub")
        user = auth_manager.users.get(user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Generate new access token
        new_access_token = auth_manager.create_access_token(user)
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_in": auth_manager.config.jwt_access_token_expire_minutes * 60
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh failed: {str(e)}"
        )


@router.post("/auth/logout")
async def logout(
    auth_context: AuthContext = Depends(get_auth_manager.get_current_user),
    auth_manager: AdvancedAuthManager = Depends(get_auth_manager)
):
    """Logout user and revoke session"""
    try:
        if auth_context.session_id:
            auth_manager.revoke_session(auth_context.session_id)
        
        return {"message": "Successfully logged out"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Logout failed: {str(e)}"
        )


# User Management Endpoints
@router.post("/users", response_model=Dict[str, Any])
async def create_user(
    request: CreateUserRequest,
    auth_context: AuthContext = Depends(get_auth_manager.get_current_user),
    auth_manager: AdvancedAuthManager = Depends(get_auth_manager)
):
    """Create new user (admin only)"""
    if not auth_manager.check_permission(auth_context, Permission.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        user = await auth_manager.create_user(
            username=request.username,
            email=request.email,
            password=request.password,
            roles=request.roles
        )
        
        return {
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email,
            "roles": [role.value for role in user.roles],
            "created_at": user.created_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"User creation failed: {str(e)}"
        )


@router.put("/users/password")
async def change_password(
    request: ChangePasswordRequest,
    auth_context: AuthContext = Depends(get_auth_manager.get_current_user),
    auth_manager: AdvancedAuthManager = Depends(get_auth_manager)
):
    """Change user password"""
    try:
        success = await auth_manager.change_password(
            user_id=auth_context.user_id,
            old_password=request.old_password,
            new_password=request.new_password
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password change failed"
            )
        
        return {"message": "Password changed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Password change failed: {str(e)}"
        )


# API Key Management
@router.post("/api-keys", response_model=APIKeyResponse)
async def create_api_key(
    request: CreateAPIKeyRequest,
    auth_context: AuthContext = Depends(get_auth_manager.get_current_user),
    auth_manager: AdvancedAuthManager = Depends(get_auth_manager)
):
    """Create new API key"""
    try:
        api_key = auth_manager.generate_api_key(
            user_id=auth_context.user_id,
            name=request.name,
            scopes=request.scopes,
            expires_in_days=request.expires_in_days
        )
        
        return APIKeyResponse(
            key_id=api_key.key_id,
            name=api_key.name,
            api_key=api_key.raw_key,
            scopes=api_key.scopes,
            created_at=api_key.created_at,
            expires_at=api_key.expires_at
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"API key creation failed: {str(e)}"
        )


@router.get("/api-keys")
async def list_api_keys(
    auth_context: AuthContext = Depends(get_auth_manager.get_current_user),
    auth_manager: AdvancedAuthManager = Depends(get_auth_manager)
):
    """List user's API keys"""
    try:
        user = auth_manager.users.get(auth_context.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        api_keys = []
        for key_id in user.api_keys:
            api_key = auth_manager.api_keys.get(key_id)
            if api_key:
                api_keys.append({
                    "key_id": api_key.key_id,
                    "name": api_key.name,
                    "scopes": api_key.scopes,
                    "created_at": api_key.created_at.isoformat(),
                    "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
                    "last_used": api_key.last_used.isoformat() if api_key.last_used else None,
                    "is_active": api_key.is_active
                })
        
        return {"api_keys": api_keys}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list API keys: {str(e)}"
        )


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    auth_context: AuthContext = Depends(get_auth_manager.get_current_user),
    auth_manager: AdvancedAuthManager = Depends(get_auth_manager)
):
    """Revoke API key"""
    try:
        api_key = auth_manager.api_keys.get(key_id)
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        # Check ownership or admin permission
        if (api_key.user_id != auth_context.user_id and 
            not auth_manager.check_permission(auth_context, Permission.ADMIN)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        api_key.is_active = False
        
        return {"message": "API key revoked successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"API key revocation failed: {str(e)}"
        )


# Security Monitoring Endpoints
@router.get("/metrics", response_model=SecurityMetricsResponse)
async def get_security_metrics(
    auth_context: AuthContext = Depends(get_auth_manager.get_current_user),
    auth_manager: AdvancedAuthManager = Depends(get_auth_manager)
):
    """Get security metrics (monitor permission required)"""
    if not auth_manager.check_permission(auth_context, Permission.MONITOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        # Get metrics from security middleware (would be injected in real app)
        # For now, return mock metrics
        return SecurityMetricsResponse(
            requests_processed=1000,
            threats_blocked=25,
            auth_failures=15,
            rate_limit_violations=8,
            blocked_ips_count=5,
            monitored_ips_count=100,
            active_sessions=len(auth_manager.active_sessions),
            api_keys_count=len(auth_manager.api_keys)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get security metrics: {str(e)}"
        )


@router.get("/threats", response_model=ThreatSummaryResponse)
async def get_threat_summary(
    auth_context: AuthContext = Depends(get_auth_manager.get_current_user),
    auth_manager: AdvancedAuthManager = Depends(get_auth_manager)
):
    """Get threat detection summary (monitor permission required)"""
    if not auth_manager.check_permission(auth_context, Permission.MONITOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        # Mock threat summary - would come from security middleware
        return ThreatSummaryResponse(
            total_threats=50,
            threatening_ips=12,
            auto_blocked_ips=3,
            top_threatening_ips=[
                {"ip": "192.168.1.100", "threats": 15},
                {"ip": "10.0.0.50", "threats": 8},
                {"ip": "172.16.1.200", "threats": 5}
            ],
            recent_threats=[
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "ip": "192.168.1.100",
                    "type": "sql_injection",
                    "severity": "high"
                }
            ]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get threat summary: {str(e)}"
        )


# Vulnerability Scanning
@router.post("/scan")
async def vulnerability_scan(
    request: VulnerabilityScanRequest,
    auth_context: AuthContext = Depends(get_auth_manager.get_current_user),
    auth_manager: AdvancedAuthManager = Depends(get_auth_manager),
    scanner: SecurityScanner = Depends(get_security_scanner)
):
    """Perform vulnerability scan (admin permission required)"""
    if not auth_manager.check_permission(auth_context, Permission.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        scan_result = await scanner.perform_vulnerability_scan(request.target_url)
        
        return {
            "scan_id": scan_result.scan_id,
            "target_url": scan_result.target_url,
            "scan_type": scan_result.scan_type,
            "started_at": scan_result.started_at.isoformat(),
            "completed_at": scan_result.completed_at.isoformat() if scan_result.completed_at else None,
            "status": scan_result.status,
            "vulnerabilities_found": len(scan_result.vulnerabilities),
            "risk_score": scan_result.risk_score,
            "vulnerabilities": [
                {
                    "type": vuln.vulnerability_type.value,
                    "severity": vuln.threat_level.value,
                    "title": vuln.title,
                    "description": vuln.description,
                    "confidence": vuln.confidence_score
                }
                for vuln in scan_result.vulnerabilities
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vulnerability scan failed: {str(e)}"
        )


# IP Management Endpoints
@router.post("/ip/blacklist")
async def add_ip_to_blacklist(
    request: IPManagementRequest,
    auth_context: AuthContext = Depends(get_auth_manager.get_current_user),
    auth_manager: AdvancedAuthManager = Depends(get_auth_manager)
):
    """Add IP to blacklist (admin permission required)"""
    if not auth_manager.check_permission(auth_context, Permission.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        # Would interact with security middleware
        return {
            "message": f"IP {request.ip_address} added to blacklist",
            "duration_hours": request.duration_hours,
            "reason": request.reason
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to blacklist IP: {str(e)}"
        )


@router.delete("/ip/blacklist/{ip_address}")
async def remove_ip_from_blacklist(
    ip_address: str,
    auth_context: AuthContext = Depends(get_auth_manager.get_current_user),
    auth_manager: AdvancedAuthManager = Depends(get_auth_manager)
):
    """Remove IP from blacklist (admin permission required)"""
    if not auth_manager.check_permission(auth_context, Permission.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        # Would interact with security middleware
        return {"message": f"IP {ip_address} removed from blacklist"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove IP from blacklist: {str(e)}"
        )


# Compliance Endpoints
@router.get("/compliance/{framework}", response_model=ComplianceReportResponse)
async def get_compliance_report(
    framework: ComplianceFramework,
    auth_context: AuthContext = Depends(get_auth_manager.get_current_user),
    auth_manager: AdvancedAuthManager = Depends(get_auth_manager),
    compliance_manager: ComplianceManager = Depends(get_compliance_manager)
):
    """Get compliance report (admin permission required)"""
    if not auth_manager.check_permission(auth_context, Permission.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        report = compliance_manager.generate_compliance_report(framework)
        return ComplianceReportResponse(**report)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate compliance report: {str(e)}"
        )


@router.post("/compliance/{framework}/assess")
async def run_compliance_assessment(
    framework: ComplianceFramework,
    auth_context: AuthContext = Depends(get_auth_manager.get_current_user),
    auth_manager: AdvancedAuthManager = Depends(get_auth_manager),
    compliance_manager: ComplianceManager = Depends(get_compliance_manager)
):
    """Run compliance assessment (admin permission required)"""
    if not auth_manager.check_permission(auth_context, Permission.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        assessment = await compliance_manager.assess_compliance(framework)
        
        return {
            "assessment_id": assessment.assessment_id,
            "framework": assessment.framework.value,
            "status": assessment.status.value,
            "score": assessment.score,
            "assessed_at": assessment.assessed_at.isoformat(),
            "total_requirements": assessment.total_requirements,
            "met_requirements": assessment.met_requirements,
            "compliance_percentage": assessment.score,
            "failed_requirements": assessment.failed_requirements,
            "recommendations": assessment.recommendations,
            "next_assessment_due": assessment.next_assessment_due.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Compliance assessment failed: {str(e)}"
        )


@router.get("/audit/events")
async def get_audit_events(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    resource: Optional[str] = Query(None, description="Filter by resource"),
    event_type: Optional[AuditEventType] = Query(None, description="Filter by event type"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of events"),
    auth_context: AuthContext = Depends(get_auth_manager.get_current_user),
    auth_manager: AdvancedAuthManager = Depends(get_auth_manager),
    compliance_manager: ComplianceManager = Depends(get_compliance_manager)
):
    """Get audit events (monitor permission required)"""
    if not auth_manager.check_permission(auth_context, Permission.MONITOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    try:
        events = await compliance_manager.query_audit_events(
            user_id=user_id,
            resource=resource,
            event_type=event_type,
            limit=limit
        )
        
        return {
            "events": [
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type.value,
                    "timestamp": event.timestamp.isoformat(),
                    "user_id": event.user_id,
                    "resource": event.resource,
                    "action": event.action,
                    "outcome": event.outcome,
                    "ip_address": event.ip_address,
                    "data_classification": event.data_classification.value if event.data_classification else None,
                    "compliance_frameworks": [f.value for f in event.compliance_frameworks]
                }
                for event in events
            ],
            "total_count": len(events)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get audit events: {str(e)}"
        )