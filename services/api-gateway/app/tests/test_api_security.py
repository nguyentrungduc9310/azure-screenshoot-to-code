"""
API Security Hardening Tests
Comprehensive tests for rate limiting, input validation, security headers, and API key management
"""
import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from fastapi import Request, Response
from fastapi.testclient import TestClient

from app.middleware.api_security import (
    APISecurityMiddleware, RateLimitRule, SecurityPolicy, InputValidationRule,
    RateLimitType, SecurityLevel
)
from app.security.api_key_manager import (
    AdvancedAPIKeyManager, AdvancedAPIKey, APIKeyType, APIKeyStatus,
    APIKeyQuota, APIKeyPermissions, APIKeyUsageStats
)
from shared.monitoring.structured_logger import StructuredLogger


class TestAPISecurityMiddleware:
    """Test cases for API security middleware"""
    
    @pytest.fixture
    def logger(self):
        return Mock(spec=StructuredLogger)
    
    @pytest.fixture
    def security_middleware(self, logger):
        app = Mock()
        return APISecurityMiddleware(
            app=app,
            logger=logger,
            enable_rate_limiting=True,
            enable_input_validation=True,
            enable_security_headers=True,
            enable_request_sanitization=True
        )
    
    def test_middleware_initialization(self, security_middleware):
        """Test middleware initialization"""
        assert security_middleware.enable_rate_limiting is True
        assert security_middleware.enable_input_validation is True
        assert security_middleware.enable_security_headers is True
        assert len(security_middleware.rate_limit_rules) > 0
        assert len(security_middleware.security_policies) > 0
    
    def test_client_ip_extraction(self, security_middleware):
        """Test client IP extraction from various headers"""
        # Test X-Forwarded-For
        request = Mock(spec=Request)
        request.headers = {"x-forwarded-for": "203.0.113.1, 192.168.1.1"}
        request.client.host = "127.0.0.1"
        
        ip = security_middleware._get_client_ip(request)
        assert ip == "203.0.113.1"
        
        # Test X-Real-IP
        request.headers = {"x-real-ip": "203.0.113.2"}
        ip = security_middleware._get_client_ip(request)
        assert ip == "203.0.113.2"
        
        # Test direct connection
        request.headers = {}
        ip = security_middleware._get_client_ip(request)
        assert ip == "127.0.0.1"
    
    def test_security_policy_matching(self, security_middleware):
        """Test security policy matching for different endpoints"""
        # Test auth endpoints
        policy = security_middleware._get_security_policy("/api/v1/security/auth/login")
        assert policy.security_level == SecurityLevel.CRITICAL
        assert policy.require_auth is False
        
        # Test user endpoints
        policy = security_middleware._get_security_policy("/api/v1/security/users")
        assert policy.security_level == SecurityLevel.RESTRICTED
        assert policy.require_auth is True
        
        # Test health endpoints
        policy = security_middleware._get_security_policy("/health")
        assert policy.security_level == SecurityLevel.PUBLIC
        assert policy.require_auth is False
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, security_middleware):
        """Test rate limiting functionality"""
        # Create mock request
        request = Mock(spec=Request)
        request.url.path = "/api/v1/test"
        request.headers = {}
        request.client.host = "192.168.1.100"
        
        client_ip = "192.168.1.100"
        policy = security_middleware._get_security_policy("/api/v1/test")
        
        # First few requests should pass
        for i in range(5):
            result = await security_middleware._check_rate_limits(request, client_ip, policy)
            assert result is False
        
        # Simulate many requests quickly
        rule = security_middleware.rate_limit_rules["default_ip"]
        for i in range(rule.requests_per_minute):
            await security_middleware._is_rate_limited(
                f"ip:{client_ip}", rule, datetime.utcnow()
            )
        
        # Next request should be rate limited
        result = await security_middleware._is_rate_limited(
            f"ip:{client_ip}", rule, datetime.utcnow()
        )
        assert result is True
    
    @pytest.mark.asyncio
    async def test_input_validation(self, security_middleware):
        """Test input validation and sanitization"""
        # Create mock request with valid data
        request = Mock(spec=Request)
        request.url.path = "/api/v1/security/auth/login"
        
        valid_data = {
            "username": "testuser",
            "password": "securepassword123"
        }
        
        async def mock_body():
            return json.dumps(valid_data).encode()
        
        request.body = mock_body
        
        # Valid input should return None (no error)
        error = await security_middleware._validate_and_sanitize_input(
            request, "/api/v1/security/auth/login"
        )
        assert error is None
        
        # Test invalid input
        invalid_data = {
            "username": "",  # Empty username (required)
            "password": "123"  # Too short
        }
        
        async def mock_invalid_body():
            return json.dumps(invalid_data).encode()
        
        request.body = mock_invalid_body
        
        error = await security_middleware._validate_and_sanitize_input(
            request, "/api/v1/security/auth/login"
        )
        assert error is not None
        assert "required" in error or "too short" in error
    
    def test_string_sanitization(self, security_middleware):
        """Test string sanitization"""
        # Test script removal
        dangerous_input = "<script>alert('xss')</script>Hello"
        sanitized = security_middleware._sanitize_string(dangerous_input)
        assert "<script>" not in sanitized
        assert "Hello" in sanitized
        
        # Test javascript: URL removal
        dangerous_input = "javascript:alert('xss')"
        sanitized = security_middleware._sanitize_string(dangerous_input)
        assert "javascript:" not in sanitized
        
        # Test length limiting
        long_input = "a" * 20000
        sanitized = security_middleware._sanitize_string(long_input)
        assert len(sanitized) <= 10000
    
    def test_validation_rules(self, security_middleware):
        """Test input validation rules"""
        # Test username validation
        rule = InputValidationRule(
            field_name="username",
            required=True,
            max_length=50,
            pattern=r"^[a-zA-Z0-9._-]+$"
        )
        
        # Valid username
        error = security_middleware._validate_field_type("username", "testuser", rule)
        assert error is None
        
        # Invalid type
        error = security_middleware._validate_field_type("username", 123, rule)
        assert error is not None
    
    def test_security_metrics(self, security_middleware):
        """Test security metrics collection"""
        # Simulate some activity
        security_middleware.requests_processed = 100
        security_middleware.requests_blocked = 5
        security_middleware.validation_failures = 3
        security_middleware.rate_limit_violations = 2
        
        metrics = security_middleware.get_security_metrics()
        
        assert metrics["requests_processed"] == 100
        assert metrics["requests_blocked"] == 5
        assert metrics["validation_failures"] == 3
        assert metrics["rate_limit_violations"] == 2
        assert metrics["block_rate"] == 0.05
        assert metrics["validation_failure_rate"] == 0.03


class TestAdvancedAPIKeyManager:
    """Test cases for advanced API key manager"""
    
    @pytest.fixture
    def logger(self):
        return Mock(spec=StructuredLogger)
    
    @pytest.fixture
    def key_manager(self, logger):
        return AdvancedAPIKeyManager(logger)
    
    def test_manager_initialization(self, key_manager):
        """Test API key manager initialization"""
        assert len(key_manager.default_quotas) == 4
        assert APIKeyType.STANDARD in key_manager.default_quotas
        assert APIKeyType.PREMIUM in key_manager.default_quotas
        assert APIKeyType.ENTERPRISE in key_manager.default_quotas
        assert APIKeyType.INTERNAL in key_manager.default_quotas
    
    def test_api_key_creation(self, key_manager):
        """Test API key creation"""
        api_key = key_manager.create_api_key(
            name="Test Key",
            description="Test API key",
            user_id="user123",
            key_type=APIKeyType.STANDARD,
            scopes={"read", "write"},
            expires_in_days=30
        )
        
        assert api_key.name == "Test Key"
        assert api_key.user_id == "user123"
        assert api_key.key_type == APIKeyType.STANDARD
        assert api_key.status == APIKeyStatus.ACTIVE
        assert "read" in api_key.permissions.scopes
        assert "write" in api_key.permissions.scopes
        assert api_key.expires_at is not None
        assert api_key.raw_key is not None
        assert api_key.raw_key.startswith("apk_")
    
    def test_api_key_verification(self, key_manager):
        """Test API key verification"""
        # Create API key
        api_key = key_manager.create_api_key(
            name="Test Key",
            description="Test",
            user_id="user123"
        )
        raw_key = api_key.raw_key
        
        # Verify valid key
        verified_key = key_manager.verify_api_key(raw_key)
        assert verified_key is not None
        assert verified_key.key_id == api_key.key_id
        
        # Verify invalid key
        invalid_key = key_manager.verify_api_key("invalid_key")
        assert invalid_key is None
        
        # Test expired key
        api_key.expires_at = datetime.utcnow() - timedelta(days=1)
        expired_key = key_manager.verify_api_key(raw_key)
        assert expired_key is None
        assert api_key.status == APIKeyStatus.EXPIRED
    
    def test_permission_validation(self, key_manager):
        """Test API key permission validation"""
        # Create API key with specific permissions
        permissions = APIKeyPermissions(
            scopes={"read"},
            allowed_endpoints={"/api/v1/data"},
            denied_endpoints={"/api/v1/admin"},
            allowed_methods={"GET"},
            ip_whitelist={"192.168.1.100"}
        )
        
        api_key = key_manager.create_api_key(
            name="Restricted Key",
            description="Restricted API key",
            user_id="user123",
            permissions=permissions
        )
        
        # Test allowed endpoint and method
        valid, error = key_manager.validate_key_permissions(
            api_key, "/api/v1/data", "GET", "192.168.1.100", "test-agent"
        )
        assert valid is True
        assert error is None
        
        # Test denied endpoint
        valid, error = key_manager.validate_key_permissions(
            api_key, "/api/v1/admin", "GET", "192.168.1.100", "test-agent"
        )
        assert valid is False
        assert "denied" in error
        
        # Test disallowed method
        valid, error = key_manager.validate_key_permissions(
            api_key, "/api/v1/data", "POST", "192.168.1.100", "test-agent"
        )
        assert valid is False
        assert "Method" in error
        
        # Test IP not in whitelist
        valid, error = key_manager.validate_key_permissions(
            api_key, "/api/v1/data", "GET", "192.168.1.200", "test-agent"
        )
        assert valid is False
        assert "whitelist" in error
    
    def test_quota_checking(self, key_manager):
        """Test quota limit checking"""
        # Create API key with low quota
        quota = APIKeyQuota(
            requests_per_minute=5,
            requests_per_hour=50,
            requests_per_day=500,
            data_transfer_mb_per_day=100
        )
        
        api_key = key_manager.create_api_key(
            name="Low Quota Key",
            description="API key with low quota",
            user_id="user123",
            custom_quota=quota
        )
        
        # Initially should be within limits
        within_limits, error = key_manager.check_quota_limits(api_key)
        assert within_limits is True
        assert error is None
        
        # Simulate quota exceeded
        api_key.usage_stats.requests_this_minute = 10
        within_limits, error = key_manager.check_quota_limits(api_key)
        assert within_limits is False
        assert "Minute quota" in error
        
        # Test data transfer quota
        api_key.usage_stats.requests_this_minute = 0
        within_limits, error = key_manager.check_quota_limits(api_key, estimated_data_mb=150)
        assert within_limits is False
        assert "data transfer" in error
    
    def test_usage_recording(self, key_manager):
        """Test API key usage recording"""
        api_key = key_manager.create_api_key(
            name="Usage Test Key",
            description="Test usage recording",
            user_id="user123"
        )
        
        # Record successful usage
        key_manager.record_api_key_usage(
            api_key=api_key,
            endpoint="/api/v1/test",
            method="GET",
            client_ip="192.168.1.100",
            response_time_ms=150.0,
            data_transfer_mb=0.5,
            success=True
        )
        
        stats = api_key.usage_stats
        assert stats.total_requests == 1
        assert stats.requests_today == 1
        assert stats.requests_this_hour == 1
        assert stats.requests_this_minute == 1
        assert stats.data_transfer_mb == 0.5
        assert stats.avg_response_time_ms == 150.0
        assert stats.last_used_endpoint == "/api/v1/test"
        assert stats.last_used_ip == "192.168.1.100"
        assert stats.error_count == 0
        
        # Record failed usage
        key_manager.record_api_key_usage(
            api_key=api_key,
            endpoint="/api/v1/test",
            method="POST",
            client_ip="192.168.1.100",
            response_time_ms=200.0,
            success=False
        )
        
        assert stats.total_requests == 2
        assert stats.error_count == 1
        assert stats.avg_response_time_ms == 175.0  # Average of 150 and 200
    
    def test_key_lifecycle_management(self, key_manager):
        """Test API key lifecycle operations"""
        api_key = key_manager.create_api_key(
            name="Lifecycle Test Key",
            description="Test lifecycle management",
            user_id="user123"
        )
        key_id = api_key.key_id
        
        # Test suspension
        success = key_manager.suspend_api_key(key_id, "Testing suspension")
        assert success is True
        assert api_key.status == APIKeyStatus.SUSPENDED
        assert "suspension_reason" in api_key.metadata
        
        # Test reactivation
        success = key_manager.reactivate_api_key(key_id)
        assert success is True
        assert api_key.status == APIKeyStatus.ACTIVE
        assert "reactivated_at" in api_key.metadata
        
        # Test revocation
        success = key_manager.revoke_api_key(key_id, "Testing revocation")
        assert success is True
        assert api_key.status == APIKeyStatus.REVOKED
        assert "revocation_reason" in api_key.metadata
    
    def test_key_rotation(self, key_manager):
        """Test API key rotation"""
        api_key = key_manager.create_api_key(
            name="Rotation Test Key",
            description="Test key rotation",
            user_id="user123"
        )
        key_id = api_key.key_id
        old_hash = api_key.key_hash
        
        # Rotate key
        new_raw_key = key_manager.rotate_api_key(key_id)
        assert new_raw_key is not None
        assert new_raw_key != api_key.raw_key
        assert api_key.key_hash != old_hash
        assert api_key.last_rotated_at is not None
        
        # Old key should no longer work
        old_key = key_manager.verify_api_key(api_key.raw_key or "")
        assert old_key is None
        
        # New key should work
        new_key = key_manager.verify_api_key(new_raw_key)
        assert new_key is not None
        assert new_key.key_id == key_id
    
    def test_user_key_management(self, key_manager):
        """Test user-specific key management"""
        # Create multiple keys for different users
        key1 = key_manager.create_api_key("Key 1", "User 1 key", "user1")
        key2 = key_manager.create_api_key("Key 2", "User 1 key 2", "user1")
        key3 = key_manager.create_api_key("Key 3", "User 2 key", "user2")
        
        # Get keys for user1
        user1_keys = key_manager.get_api_keys_for_user("user1")
        assert len(user1_keys) == 2
        assert all(key.user_id == "user1" for key in user1_keys)
        
        # Get keys for user2
        user2_keys = key_manager.get_api_keys_for_user("user2")
        assert len(user2_keys) == 1
        assert user2_keys[0].user_id == "user2"
    
    def test_analytics_and_reporting(self, key_manager):
        """Test analytics and reporting features"""
        # Create and use API key
        api_key = key_manager.create_api_key(
            name="Analytics Test Key",
            description="Test analytics",
            user_id="user123",
            key_type=APIKeyType.PREMIUM
        )
        
        # Record some usage
        for i in range(10):
            key_manager.record_api_key_usage(
                api_key, f"/api/v1/endpoint{i}", "GET", 
                "192.168.1.100", 100.0, 0.1, i < 8  # 2 failures
            )
        
        # Get analytics
        analytics = key_manager.get_api_key_analytics(api_key.key_id)
        assert analytics is not None
        assert analytics["usage_stats"]["total_requests"] == 10
        assert analytics["usage_stats"]["error_count"] == 2
        assert analytics["usage_stats"]["error_rate"] == 0.2
        assert "quota_usage" in analytics
        assert "permissions" in analytics
        
        # Get system analytics
        system_analytics = key_manager.get_system_analytics()
        assert system_analytics["total_keys"] >= 1
        assert system_analytics["active_keys"] >= 1
        assert system_analytics["total_requests"] >= 10
        assert APIKeyType.PREMIUM.value in system_analytics["key_types"]
    
    def test_expired_key_cleanup(self, key_manager):
        """Test cleanup of expired keys"""
        # Create expired key
        api_key = key_manager.create_api_key(
            name="Expired Key",
            description="Will be expired",
            user_id="user123",
            expires_in_days=1
        )
        
        # Manually set expiration to past
        api_key.expires_at = datetime.utcnow() - timedelta(days=1)
        
        # Run cleanup
        expired_count = key_manager.cleanup_expired_keys()
        assert expired_count == 1
        assert api_key.status == APIKeyStatus.EXPIRED


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])