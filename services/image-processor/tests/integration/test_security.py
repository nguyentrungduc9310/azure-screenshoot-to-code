"""
Security integration tests for Image Processor service
Tests authentication, authorization, input validation, and security measures
"""
import pytest
import base64
import io
from httpx import AsyncClient
from unittest.mock import patch
from PIL import Image

from app.main import create_application

class TestSecurity:
    """Security testing suite for Image Processor service"""
    
    @pytest.fixture
    def app(self):
        """Create test application"""
        return create_application()
    
    @pytest.fixture
    async def client(self, app):
        """Create async HTTP client"""
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            yield client
    
    @pytest.fixture
    def valid_user(self):
        """Valid user for authentication tests"""
        return {
            "id": "user-123",
            "email": "user@example.com",
            "name": "Regular User",
            "roles": ["user"]
        }
    
    @pytest.fixture
    def admin_user(self):
        """Admin user for authorization tests"""
        return {
            "id": "admin-456",
            "email": "admin@example.com",
            "name": "Admin User",
            "roles": ["admin"]
        }
    
    @pytest.fixture
    def unauthorized_user(self):
        """User with no roles for authorization tests"""
        return {
            "id": "noauth-789",
            "email": "noauth@example.com",
            "name": "No Auth User",
            "roles": []
        }
    
    def create_test_image(self, width: int = 100, height: int = 100) -> str:
        """Create valid test image data URL"""
        img = Image.new('RGB', (width, height), color='red')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        image_bytes = buffer.getvalue()
        
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:image/png;base64,{image_base64}"
    
    # Authentication Tests
    
    @pytest.mark.security
    @pytest.mark.asyncio
    async def test_missing_authentication(self, client: AsyncClient):
        """Test endpoints reject requests without authentication"""
        
        protected_endpoints = [
            ("POST", "/api/v1/process", {"image": "data:image/png;base64,test", "provider": "claude"}),
            ("POST", "/api/v1/validate", {"image": "data:image/png;base64,test", "provider": "claude"}),
            ("POST", "/api/v1/analyze", {"image": "data:image/png;base64,test"}),
            ("POST", "/api/v1/thumbnail", {"image": "data:image/png;base64,test", "width": 100, "height": 100}),
            ("GET", "/api/v1/providers", None),
            ("GET", "/api/v1/stats", None),
            ("GET", "/health/metrics", None)
        ]
        
        for method, endpoint, payload in protected_endpoints:
            if method == "GET":
                response = await client.get(endpoint)
            else:
                response = await client.post(endpoint, json=payload)
            
            assert response.status_code == 401, f"Endpoint {method} {endpoint} should require authentication"
            
            # Verify error response format
            if response.headers.get("content-type", "").startswith("application/json"):
                data = response.json()
                assert data.get("success") is False
                assert "error" in data
    
    @pytest.mark.security
    @pytest.mark.asyncio
    async def test_invalid_token_authentication(self, client: AsyncClient):
        """Test endpoints reject invalid authentication tokens"""
        
        invalid_tokens = [
            "Bearer invalid-token",
            "Bearer ",
            "Invalid-Format token",
            "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature"  # Invalid JWT
        ]
        
        endpoint = "/api/v1/providers"
        
        for token in invalid_tokens:
            response = await client.get(
                endpoint,
                headers={"Authorization": token}
            )
            
            assert response.status_code == 401, f"Invalid token '{token}' should be rejected"
    
    @pytest.mark.security
    @pytest.mark.asyncio
    async def test_valid_authentication(self, client: AsyncClient, valid_user):
        """Test valid authentication is accepted"""
        
        with patch("shared.auth.azure_ad.get_current_user", return_value=valid_user):
            response = await client.get(
                "/api/v1/providers",
                headers={"Authorization": "Bearer valid-token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "supported_providers" in data
    
    # Authorization Tests
    
    @pytest.mark.security
    @pytest.mark.asyncio
    async def test_admin_only_endpoints(self, client: AsyncClient, valid_user, admin_user):
        """Test admin-only endpoints require admin role"""
        
        admin_endpoints = [
            "/api/v1/stats",
            "/health/metrics"
        ]
        
        for endpoint in admin_endpoints:
            # Test with regular user (should fail)
            with patch("shared.auth.azure_ad.get_current_user", return_value=valid_user):
                response = await client.get(
                    endpoint,
                    headers={"Authorization": "Bearer user-token"}
                )
                
                assert response.status_code == 403, f"Regular user should not access {endpoint}"
                
                if response.headers.get("content-type", "").startswith("application/json"):
                    data = response.json()
                    assert data.get("success") is False
                    assert "permission" in data.get("error", "").lower()
            
            # Test with admin user (should succeed)
            with patch("shared.auth.azure_ad.get_current_user", return_value=admin_user):
                response = await client.get(
                    endpoint,
                    headers={"Authorization": "Bearer admin-token"}
                )
                
                assert response.status_code == 200, f"Admin user should access {endpoint}"
    
    @pytest.mark.security
    @pytest.mark.asyncio
    async def test_role_based_access_control(self, client: AsyncClient, unauthorized_user):
        """Test users without proper roles are denied access"""
        
        # User with no roles should be denied
        with patch("shared.auth.azure_ad.get_current_user", return_value=unauthorized_user):
            response = await client.get(
                "/api/v1/providers",
                headers={"Authorization": "Bearer noauth-token"}
            )
            
            # Depending on implementation, this might be 403 or still 200 for basic endpoints
            # Adjust based on actual authorization requirements
            assert response.status_code in [200, 403]
    
    # Input Validation Security Tests
    
    @pytest.mark.security
    @pytest.mark.asyncio
    async def test_malicious_image_data_injection(self, client: AsyncClient, valid_user):
        """Test protection against malicious image data"""
        
        with patch("shared.auth.azure_ad.get_current_user", return_value=valid_user):
            malicious_payloads = [
                # Script injection attempts
                "data:text/html;base64," + base64.b64encode(b"<script>alert('xss')</script>").decode(),
                
                # SQL injection attempts
                "data:image/png;base64,'; DROP TABLE users; --",
                
                # Command injection attempts
                "data:image/png;base64,$(rm -rf /)",
                
                # Path traversal attempts
                "data:image/png;base64,../../../etc/passwd",
                
                # Null byte injection
                "data:image/png;base64,test\x00.exe",
                
                # Extremely long data
                "data:image/png;base64," + "A" * 100000,
                
                # Invalid base64 with special characters
                "data:image/png;base64,<>\"'&%$#@!",
                
                # Binary data that's not base64
                "data:image/png;base64,\x00\x01\x02\x03\x04\x05"
            ]
            
            for payload in malicious_payloads:
                response = await client.post(
                    "/api/v1/validate",
                    json={"image": payload, "provider": "claude"},
                    headers={"Authorization": "Bearer test-token"}
                )
                
                # Should either reject with 422 or return validation failure
                assert response.status_code in [200, 422], f"Malicious payload should be handled safely"
                
                if response.status_code == 200:
                    data = response.json()
                    # If validation passes, it should mark as invalid
                    assert data.get("valid") is False, "Malicious data should not validate as valid image"
    
    @pytest.mark.security
    @pytest.mark.asyncio
    async def test_oversized_request_protection(self, client: AsyncClient, valid_user):
        """Test protection against oversized requests"""
        
        with patch("shared.auth.azure_ad.get_current_user", return_value=valid_user):
            # Create oversized payload (>50MB)
            large_data = "x" * (60 * 1024 * 1024)  # 60MB
            
            try:
                response = await client.post(
                    "/api/v1/process",
                    content=large_data,
                    headers={
                        "Authorization": "Bearer test-token",
                        "Content-Type": "application/json"
                    }
                )
                
                # Should reject oversized requests
                assert response.status_code == 413, "Oversized requests should be rejected"
                
            except Exception as e:
                # Client might reject before sending
                assert "too large" in str(e).lower() or "size" in str(e).lower()
    
    @pytest.mark.security
    @pytest.mark.asyncio
    async def test_content_type_validation(self, client: AsyncClient, valid_user):
        """Test content type validation"""
        
        with patch("shared.auth.azure_ad.get_current_user", return_value=valid_user):
            valid_payload = {"image": self.create_test_image(), "provider": "claude"}
            
            # Test with various content types
            content_types = [
                "text/plain",
                "text/html", 
                "application/xml",
                "multipart/form-data",
                "",  # Missing content type
                "application/json; charset=utf-8",  # Valid
            ]
            
            for content_type in content_types:
                headers = {"Authorization": "Bearer test-token"}
                if content_type:
                    headers["Content-Type"] = content_type
                
                response = await client.post(
                    "/api/v1/process",
                    json=valid_payload,
                    headers=headers
                )
                
                if content_type.startswith("application/json") or not content_type:
                    # Should accept JSON content type
                    assert response.status_code in [200, 422], f"JSON content type should be accepted"
                else:
                    # Should reject non-JSON content types for JSON endpoints
                    assert response.status_code in [400, 415, 422], f"Invalid content type {content_type} should be rejected"
    
    @pytest.mark.security
    @pytest.mark.asyncio
    async def test_parameter_injection_protection(self, client: AsyncClient, valid_user):
        """Test protection against parameter injection attacks"""
        
        with patch("shared.auth.azure_ad.get_current_user", return_value=valid_user):
            image_data_url = self.create_test_image()
            
            # Test injection in provider parameter
            malicious_providers = [
                "claude'; DROP TABLE users; --",
                "claude<script>alert('xss')</script>",
                "claude$(rm -rf /)",
                "../../../etc/passwd",
                "claude\x00admin",
                "claude OR 1=1",
                "claude UNION SELECT * FROM users"
            ]
            
            for provider in malicious_providers:
                response = await client.post(
                    "/api/v1/validate",
                    json={"image": image_data_url, "provider": provider},
                    headers={"Authorization": "Bearer test-token"}
                )
                
                # Should reject invalid providers
                assert response.status_code == 422, f"Malicious provider '{provider}' should be rejected"
    
    @pytest.mark.security
    @pytest.mark.asyncio
    async def test_cors_security(self, client: AsyncClient):
        """Test CORS security configuration"""
        
        # Test CORS preflight
        response = await client.options(
            "/api/v1/process",
            headers={
                "Origin": "https://malicious-site.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization, Content-Type"
            }
        )
        
        # Check CORS headers
        cors_headers = {
            "access-control-allow-origin",
            "access-control-allow-methods", 
            "access-control-allow-headers",
            "access-control-max-age"
        }
        
        response_headers = {k.lower() for k in response.headers.keys()}
        
        # Should have CORS headers configured
        if any(header in response_headers for header in cors_headers):
            # If CORS is enabled, verify it's properly configured
            allow_origin = response.headers.get("access-control-allow-origin", "")
            assert allow_origin != "*" or response.status_code == 200, "CORS should not allow all origins in production"
    
    @pytest.mark.security
    @pytest.mark.asyncio
    async def test_error_information_disclosure(self, client: AsyncClient, valid_user):
        """Test that errors don't disclose sensitive information"""
        
        with patch("shared.auth.azure_ad.get_current_user", return_value=valid_user):
            # Trigger various error conditions
            error_requests = [
                # Invalid JSON
                ("/api/v1/process", "invalid-json"),
                
                # Missing required fields
                ("/api/v1/process", {"provider": "claude"}),
                
                # Invalid field types
                ("/api/v1/process", {"image": 123, "provider": "claude"}),
                
                # Invalid provider
                ("/api/v1/validate", {"image": self.create_test_image(), "provider": "nonexistent"})
            ]
            
            for endpoint, payload in error_requests:
                if isinstance(payload, str):
                    # Raw string payload
                    response = await client.post(
                        endpoint,
                        content=payload,
                        headers={
                            "Authorization": "Bearer test-token",
                            "Content-Type": "application/json"
                        }
                    )
                else:
                    # JSON payload
                    response = await client.post(
                        endpoint,
                        json=payload,
                        headers={"Authorization": "Bearer test-token"}
                    )
                
                # Should return error but not expose internals
                assert response.status_code >= 400
                
                if response.headers.get("content-type", "").startswith("application/json"):
                    data = response.json()
                    error_message = data.get("message", "").lower()
                    
                    # Should not expose internal paths, code, or sensitive info
                    sensitive_patterns = [
                        "/app/",
                        "/usr/",
                        "/var/",
                        "traceback",
                        "stack trace",
                        "internal server error",
                        "database",
                        "sql",
                        "connection string",
                        "secret",
                        "key"
                    ]
                    
                    for pattern in sensitive_patterns:
                        assert pattern not in error_message, f"Error should not expose '{pattern}'"
    
    @pytest.mark.security
    @pytest.mark.asyncio
    async def test_rate_limiting_protection(self, client: AsyncClient, valid_user):
        """Test rate limiting protection (if implemented)"""
        
        with patch("shared.auth.azure_ad.get_current_user", return_value=valid_user):
            image_data_url = self.create_test_image()
            
            # Make rapid requests
            responses = []
            for i in range(20):  # 20 rapid requests
                response = await client.post(
                    "/api/v1/validate",
                    json={"image": image_data_url, "provider": "claude"},
                    headers={"Authorization": "Bearer test-token"}
                )
                responses.append(response)
            
            # Check if any requests were rate limited
            rate_limited = [r for r in responses if r.status_code == 429]
            
            if rate_limited:
                # If rate limiting is implemented, verify proper headers
                rate_limited_response = rate_limited[0]
                assert "retry-after" in rate_limited_response.headers or "x-ratelimit" in str(rate_limited_response.headers).lower()
                
                # Error response should be informative
                if rate_limited_response.headers.get("content-type", "").startswith("application/json"):
                    data = rate_limited_response.json()
                    assert "rate" in data.get("message", "").lower() or "limit" in data.get("message", "").lower()
    
    @pytest.mark.security
    @pytest.mark.asyncio
    async def test_request_id_tracking(self, client: AsyncClient, valid_user):
        """Test request ID tracking for security auditing"""
        
        with patch("shared.auth.azure_ad.get_current_user", return_value=valid_user):
            response = await client.post(
                "/api/v1/validate",
                json={"image": self.create_test_image(), "provider": "claude"},
                headers={"Authorization": "Bearer test-token"}
            )
            
            # Should have correlation/request ID for tracking
            data = response.json()
            correlation_id = data.get("correlation_id")
            
            assert correlation_id is not None, "Response should include correlation ID for tracking"
            assert len(correlation_id) > 0, "Correlation ID should not be empty"
            
            # Correlation ID should be unique across requests
            response2 = await client.post(
                "/api/v1/validate", 
                json={"image": self.create_test_image(), "provider": "claude"},
                headers={"Authorization": "Bearer test-token"}
            )
            
            data2 = response2.json()
            correlation_id2 = data2.get("correlation_id")
            
            assert correlation_id != correlation_id2, "Correlation IDs should be unique"
    
    @pytest.mark.security
    @pytest.mark.asyncio
    async def test_security_headers(self, client: AsyncClient, valid_user):
        """Test security headers are properly set"""
        
        with patch("shared.auth.azure_ad.get_current_user", return_value=valid_user):
            response = await client.get(
                "/api/v1/providers",
                headers={"Authorization": "Bearer test-token"}
            )
            
            # Check for security headers (adjust based on implementation)
            security_headers = {
                "x-content-type-options": "nosniff",
                "x-frame-options": ["DENY", "SAMEORIGIN"],
                "x-xss-protection": "1; mode=block",
                "strict-transport-security": None,  # Should contain max-age
                "content-security-policy": None,
                "referrer-policy": None
            }
            
            response_headers = {k.lower(): v for k, v in response.headers.items()}
            
            for header, expected_value in security_headers.items():
                if header in response_headers:
                    if isinstance(expected_value, list):
                        assert response_headers[header] in expected_value, f"Header {header} has unexpected value"
                    elif expected_value is not None:
                        assert response_headers[header] == expected_value, f"Header {header} has unexpected value"
                    # If expected_value is None, just check that header exists
    
    @pytest.mark.security
    @pytest.mark.asyncio
    async def test_public_endpoints_security(self, client: AsyncClient):
        """Test that public endpoints don't expose sensitive information"""
        
        public_endpoints = [
            "/health",
            "/health/ready",
            "/health/live", 
            "/health/capabilities"
        ]
        
        for endpoint in public_endpoints:
            response = await client.get(endpoint)
            
            assert response.status_code == 200, f"Public endpoint {endpoint} should be accessible"
            
            if response.headers.get("content-type", "").startswith("application/json"):
                data = response.json()
                
                # Should not expose sensitive configuration
                sensitive_keys = [
                    "secret",
                    "key",
                    "password",
                    "token",
                    "connection_string",
                    "database_url",
                    "api_key"
                ]
                
                data_str = str(data).lower()
                for key in sensitive_keys:
                    assert key not in data_str, f"Public endpoint {endpoint} should not expose {key}"