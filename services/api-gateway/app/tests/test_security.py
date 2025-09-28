"""
Comprehensive Security System Tests
Tests for authentication, threat detection, compliance, and security middleware
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from fastapi import Request, Response
from fastapi.testclient import TestClient

from app.security.advanced_auth import (
    AdvancedAuthManager, AuthConfig, AuthMethod, UserRole, Permission,
    SecurityLevel, User, APIKey, AuthContext
)
from app.security.security_scanner import (
    SecurityScanner, SecurityThreat, ThreatLevel, VulnerabilityType, AttackPattern
)
from app.security.compliance import (
    ComplianceManager, ComplianceFramework, DataClassification, AuditEventType,
    ComplianceStatus, AuditEvent, ComplianceAssessment
)
from app.middleware.security import SecurityMiddleware, SecurityConfig, SecurityContext
from app.core.config import Settings
from shared.monitoring.structured_logger import StructuredLogger


class TestAdvancedAuthManager:
    """Test cases for advanced authentication manager"""
    
    @pytest.fixture
    def auth_config(self):
        return AuthConfig(
            jwt_secret_key="test-secret-key",
            jwt_algorithm="HS256",
            jwt_access_token_expire_minutes=30,
            password_min_length=8,
            max_login_attempts=3,
            lockout_duration_minutes=15
        )
    
    @pytest.fixture
    def settings(self):
        return Settings()
    
    @pytest.fixture
    def logger(self):
        return Mock(spec=StructuredLogger)
    
    @pytest.fixture
    def auth_manager(self, settings, logger, auth_config):
        return AdvancedAuthManager(settings, logger, auth_config)
    
    def test_password_hashing(self, auth_manager):
        """Test password hashing and verification"""
        password = "TestPassword123!"
        hashed = auth_manager.hash_password(password)
        
        assert hashed != password
        assert auth_manager.verify_password(password, hashed)
        assert not auth_manager.verify_password("wrong", hashed)
    
    def test_password_strength_validation(self, auth_manager):
        """Test password strength validation"""
        # Strong password
        is_strong, issues = auth_manager.validate_password_strength("StrongPass123!")
        assert is_strong
        assert len(issues) == 0
        
        # Weak passwords
        weak_passwords = [
            "weak",          # Too short
            "lowercase123!", # No uppercase
            "UPPERCASE123!", # No lowercase
            "NoNumbers!",    # No digits
            "NoSpecial123"   # No special chars
        ]
        
        for weak_pass in weak_passwords:
            is_strong, issues = auth_manager.validate_password_strength(weak_pass)
            assert not is_strong
            assert len(issues) > 0
    
    @pytest.mark.asyncio
    async def test_user_creation(self, auth_manager):
        """Test user creation with validation"""
        user = await auth_manager.create_user(
            username="testuser",
            email="test@example.com",
            password="TestPassword123!",
            roles=[UserRole.USER]
        )
        
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.user_id in auth_manager.users
        assert UserRole.USER in user.roles
        assert Permission.READ in user.permissions
        assert Permission.WRITE in user.permissions
    
    @pytest.mark.asyncio
    async def test_user_authentication(self, auth_manager):
        """Test user authentication with rate limiting"""
        # Create user
        user = await auth_manager.create_user(
            username="testuser",
            email="test@example.com",
            password="TestPassword123!",
            require_verification=False
        )
        
        # Successful authentication
        authenticated_user = await auth_manager.authenticate_user(
            "testuser", "TestPassword123!", "127.0.0.1"
        )
        assert authenticated_user is not None
        assert authenticated_user.user_id == user.user_id
        
        # Failed authentication
        failed_user = await auth_manager.authenticate_user(
            "testuser", "wrongpassword", "127.0.0.1"
        )
        assert failed_user is None
    
    def test_jwt_token_creation_and_verification(self, auth_manager):
        """Test JWT token creation and verification"""
        user = User(
            user_id="test-user-id",
            username="testuser",
            email="test@example.com",
            hashed_password="hashed",
            roles=[UserRole.USER],
            permissions=[Permission.READ, Permission.WRITE]
        )
        
        # Create access token
        token = auth_manager.create_access_token(user)
        assert token is not None
        
        # Verify token
        payload = auth_manager.verify_token(token)
        assert payload is not None
        assert payload["sub"] == user.user_id
        assert payload["username"] == user.username
        assert UserRole.USER.value in payload["roles"]
        
        # Test token revocation
        auth_manager.revoke_token(token)
        revoked_payload = auth_manager.verify_token(token)
        assert revoked_payload is None
    
    def test_api_key_generation_and_verification(self, auth_manager):
        """Test API key generation and verification"""
        user_id = "test-user-id"
        
        # Generate API key
        api_key = auth_manager.generate_api_key(
            user_id=user_id,
            name="Test API Key",
            scopes=["read", "write"]
        )
        
        assert api_key.key_id is not None
        assert hasattr(api_key, 'raw_key')
        assert api_key.user_id == user_id
        assert "read" in api_key.scopes
        
        # Verify API key
        verified_key = auth_manager.verify_api_key(api_key.raw_key)
        assert verified_key is not None
        assert verified_key.key_id == api_key.key_id
        
        # Test invalid key
        invalid_key = auth_manager.verify_api_key("invalid-key")
        assert invalid_key is None
    
    def test_permission_checking(self, auth_manager):
        """Test permission and role checking"""
        auth_context = AuthContext(
            user_id="test-user",
            username="testuser",
            roles=[UserRole.ADMIN],
            permissions=[Permission.READ, Permission.WRITE, Permission.ADMIN],
            auth_method=AuthMethod.JWT
        )
        
        # Test permission checks
        assert auth_manager.check_permission(auth_context, Permission.READ)
        assert auth_manager.check_permission(auth_context, Permission.ADMIN)
        assert not auth_manager.check_permission(auth_context, Permission.EXECUTE)
        
        # Test role checks
        assert auth_manager.check_role(auth_context, UserRole.ADMIN)
        assert not auth_manager.check_role(auth_context, UserRole.SERVICE)


class TestSecurityScanner:
    """Test cases for security scanner"""
    
    @pytest.fixture
    def logger(self):
        return Mock(spec=StructuredLogger)
    
    @pytest.fixture
    def scanner(self, logger):
        return SecurityScanner(logger)
    
    @pytest.mark.asyncio
    async def test_sql_injection_detection(self, scanner):
        """Test SQL injection pattern detection"""
        # Mock request with SQL injection
        request = Mock(spec=Request)
        request.url.path = "/api/users"
        request.method = "GET"
        request.query_params = {"id": "1' OR '1'='1"}
        request.headers = {}
        
        async def mock_body():
            return b""
        request.body = mock_body
        
        threats = await scanner.scan_request(request)
        
        sql_threats = [t for t in threats if t.vulnerability_type == VulnerabilityType.SQL_INJECTION]
        assert len(sql_threats) > 0
        assert sql_threats[0].threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]
    
    @pytest.mark.asyncio
    async def test_xss_detection(self, scanner):
        """Test XSS pattern detection"""
        request = Mock(spec=Request)
        request.url.path = "/api/comments"
        request.method = "POST"
        request.query_params = {}
        request.headers = {"content-type": "application/json"}
        
        async def mock_body():
            return b'{"comment": "<script>alert(\\"xss\\")</script>"}'
        request.body = mock_body
        
        threats = await scanner.scan_request(request)
        
        xss_threats = [t for t in threats if t.vulnerability_type == VulnerabilityType.XSS]
        assert len(xss_threats) > 0
        assert xss_threats[0].threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]
    
    @pytest.mark.asyncio
    async def test_path_traversal_detection(self, scanner):
        """Test path traversal detection"""
        request = Mock(spec=Request)
        request.url.path = "/api/files"
        request.method = "GET"
        request.query_params = {"file": "../../../etc/passwd"}
        request.headers = {}
        
        async def mock_body():
            return b""
        request.body = mock_body
        
        threats = await scanner.scan_request(request)
        
        path_threats = [t for t in threats if t.vulnerability_type == VulnerabilityType.PATH_TRAVERSAL]
        assert len(path_threats) > 0
        assert path_threats[0].threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]
    
    @pytest.mark.asyncio
    async def test_bot_detection(self, scanner):
        """Test bot detection"""
        request = Mock(spec=Request)
        request.url.path = "/api/data"
        request.method = "GET"
        request.query_params = {}
        request.headers = {"user-agent": "python-requests/2.25.1"}
        
        async def mock_body():
            return b""
        request.body = mock_body
        
        threats = await scanner.scan_request(request)
        
        bot_threats = [t for t in threats if t.vulnerability_type == VulnerabilityType.BOT]
        assert len(bot_threats) > 0
        assert bot_threats[0].threat_level == ThreatLevel.MEDIUM


class TestComplianceManager:
    """Test cases for compliance manager"""
    
    @pytest.fixture
    def settings(self):
        return Settings()
    
    @pytest.fixture
    def logger(self):
        return Mock(spec=StructuredLogger)
    
    @pytest.fixture
    def compliance_manager(self, settings, logger):
        return ComplianceManager(settings, logger)
    
    @pytest.mark.asyncio
    async def test_audit_event_logging(self, compliance_manager):
        """Test audit event logging"""
        event_id = await compliance_manager.log_audit_event(
            event_type=AuditEventType.DATA_ACCESS,
            user_id="test-user",
            resource="/api/users/profile",
            action="GET /api/users/profile",
            outcome="success",
            ip_address="127.0.0.1",
            details={"status_code": 200},
            data_classification=DataClassification.PII
        )
        
        assert event_id.startswith("AUDIT_")
        assert len(compliance_manager.audit_events) == 1
        
        event = compliance_manager.audit_events[0]
        assert event.event_type == AuditEventType.DATA_ACCESS
        assert event.user_id == "test-user"
        assert event.data_classification == DataClassification.PII
        assert ComplianceFramework.GDPR in event.compliance_frameworks
    
    @pytest.mark.asyncio
    async def test_audit_event_querying(self, compliance_manager):
        """Test audit event querying"""
        # Log multiple events
        await compliance_manager.log_audit_event(
            AuditEventType.DATA_ACCESS, "user1", "resource1", "action1", "success"
        )
        await compliance_manager.log_audit_event(
            AuditEventType.DATA_MODIFICATION, "user2", "resource2", "action2", "success"
        )
        await compliance_manager.log_audit_event(
            AuditEventType.DATA_ACCESS, "user1", "resource3", "action3", "failure"
        )
        
        # Query by user
        user1_events = await compliance_manager.query_audit_events(user_id="user1")
        assert len(user1_events) == 2
        
        # Query by event type
        access_events = await compliance_manager.query_audit_events(
            event_type=AuditEventType.DATA_ACCESS
        )
        assert len(access_events) == 2
    
    @pytest.mark.asyncio
    async def test_consent_management(self, compliance_manager):
        """Test GDPR consent management"""
        user_id = "test-user"
        
        # Record consent
        consent_id = await compliance_manager.record_consent(
            user_id=user_id,
            consent_type="marketing",
            consent_given=True,
            legal_basis="consent",
            purpose="marketing communications",
            data_categories=["email", "preferences"]
        )
        
        assert consent_id.startswith("CONSENT_")
        
        # Get user consents
        consents = await compliance_manager.get_user_consents(user_id)
        assert len(consents) == 1
        assert consents[0]["consent_given"] is True
        
        # Withdraw consent
        success = await compliance_manager.withdraw_consent(
            user_id, consent_id, "user request"
        )
        assert success is True
        
        # Check withdrawal
        updated_consents = await compliance_manager.get_user_consents(user_id)
        assert updated_consents[0]["consent_given"] is False
        assert "withdrawn_at" in updated_consents[0]
    
    @pytest.mark.asyncio
    async def test_compliance_assessment(self, compliance_manager):
        """Test compliance assessment"""
        # Run GDPR assessment
        assessment = await compliance_manager.assess_compliance(ComplianceFramework.GDPR)
        
        assert assessment.framework == ComplianceFramework.GDPR
        assert assessment.status in [
            ComplianceStatus.COMPLIANT, 
            ComplianceStatus.PARTIAL, 
            ComplianceStatus.NON_COMPLIANT
        ]
        assert 0 <= assessment.score <= 100
        assert assessment.total_requirements > 0
    
    @pytest.mark.asyncio
    async def test_data_retention_policies(self, compliance_manager):
        """Test data retention policy application"""
        # Add some old audit events
        old_event = AuditEvent(
            event_id="OLD_EVENT",
            event_type=AuditEventType.DATA_ACCESS,
            timestamp=datetime.utcnow() - timedelta(days=8000),  # Very old
            user_id="test-user",
            session_id=None,
            ip_address="127.0.0.1",
            user_agent="test",
            resource="test",
            action="test",
            outcome="success",
            retention_period=365  # 1 year retention
        )
        compliance_manager.audit_events.append(old_event)
        
        # Apply retention policies
        cleaned_count = await compliance_manager.apply_retention_policies()
        
        assert cleaned_count > 0
        assert old_event not in compliance_manager.audit_events


class TestSecurityMiddleware:
    """Test cases for security middleware"""
    
    @pytest.fixture
    def settings(self):
        return Settings()
    
    @pytest.fixture
    def logger(self):
        return Mock(spec=StructuredLogger)
    
    @pytest.fixture
    def auth_manager(self, settings, logger):
        config = AuthConfig(jwt_secret_key="test-secret")
        return AdvancedAuthManager(settings, logger, config)
    
    @pytest.fixture
    def security_scanner(self, logger):
        return SecurityScanner(logger)
    
    @pytest.fixture
    def compliance_manager(self, settings, logger):
        return ComplianceManager(settings, logger)
    
    @pytest.fixture
    def security_config(self):
        return SecurityConfig(
            enable_threat_detection=True,
            enable_rate_limiting=True,
            enable_ip_blocking=True,
            max_requests_per_minute=10,
            max_requests_per_hour=100
        )
    
    @pytest.fixture
    def security_middleware(self, auth_manager, security_scanner, compliance_manager, logger, security_config):
        # Mock app
        app = Mock()
        return SecurityMiddleware(
            app, auth_manager, security_scanner, compliance_manager, logger, security_config
        )
    
    def test_client_ip_extraction(self, security_middleware):
        """Test client IP extraction with various headers"""
        # Test direct connection
        request = Mock(spec=Request)
        request.client.host = "192.168.1.1"
        request.headers = {}
        
        ip = security_middleware._get_client_ip(request)
        assert ip == "192.168.1.1"
        
        # Test X-Forwarded-For header
        request.headers = {"x-forwarded-for": "203.0.113.1, 198.51.100.1"}
        ip = security_middleware._get_client_ip(request)
        assert ip == "203.0.113.1"
        
        # Test X-Real-IP header
        request.headers = {"x-real-ip": "203.0.113.2"}
        ip = security_middleware._get_client_ip(request)
        assert ip == "203.0.113.2"
    
    @pytest.mark.asyncio
    async def test_ip_blocking(self, security_middleware):
        """Test IP blocking functionality"""
        # Add IP to blacklist
        security_middleware.add_ip_to_blacklist("192.168.1.100")
        
        # Test blocking
        security_context = SecurityContext(
            request_id="test-request",
            ip_address="192.168.1.100",
            user_agent="test",
            threat_level=ThreatLevel.LOW,
            threats_detected=[]
        )
        
        blocked = await security_middleware._check_ip_blocking(security_context)
        assert blocked is True
        assert security_context.blocked is True
        assert "blacklist" in security_context.block_reason
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, security_middleware):
        """Test rate limiting functionality"""
        security_context = SecurityContext(
            request_id="test-request",
            ip_address="192.168.1.200",
            user_agent="test",
            threat_level=ThreatLevel.LOW,
            threats_detected=[]
        )
        
        # Normal requests should pass
        for i in range(5):
            blocked = await security_middleware._check_rate_limiting(security_context)
            assert blocked is False
        
        # Excessive requests should be blocked
        for i in range(10):
            await security_middleware._check_rate_limiting(security_context)
        
        blocked = await security_middleware._check_rate_limiting(security_context)
        assert blocked is True
    
    def test_security_metrics(self, security_middleware):
        """Test security metrics collection"""
        # Simulate some activity
        security_middleware.requests_processed = 100
        security_middleware.threats_blocked = 5
        security_middleware.auth_failures = 3
        security_middleware.rate_limit_violations = 2
        
        metrics = security_middleware.get_security_metrics()
        
        assert metrics["requests_processed"] == 100
        assert metrics["threats_blocked"] == 5
        assert metrics["auth_failures"] == 3
        assert metrics["rate_limit_violations"] == 2
        assert "blocked_ips_count" in metrics
        assert "monitored_ips_count" in metrics
    
    def test_threat_summary(self, security_middleware):
        """Test threat detection summary"""
        # Add some threat counts
        security_middleware.threat_counts = {
            "192.168.1.1": 15,  # Above threshold
            "192.168.1.2": 8,
            "192.168.1.3": 3
        }
        
        summary = security_middleware.get_threat_summary()
        
        assert summary["total_threats"] == 26
        assert summary["threatening_ips"] == 3
        assert summary["auto_blocked_ips"] == 1  # Only first IP above threshold
        assert len(summary["top_threatening_ips"]) == 3


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])