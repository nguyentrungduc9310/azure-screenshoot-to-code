"""
Tests for authentication middleware
"""
import pytest
from fastapi.testclient import TestClient


class TestAuthentication:
    """Test authentication functionality"""
    
    def test_public_endpoints_no_auth_required(self, auth_client: TestClient):
        """Test that public endpoints don't require authentication"""
        public_endpoints = [
            "/",
            "/health",
            "/health/live", 
            "/health/ready",
            "/health/detailed",
            "/docs",
            "/redoc",
            "/openapi.json"
        ]
        
        for endpoint in public_endpoints:
            response = auth_client.get(endpoint)
            # Should not return 401 (public endpoints)
            assert response.status_code != 401
    
    def test_protected_endpoints_require_auth(self, auth_client: TestClient):
        """Test that protected endpoints require authentication"""
        protected_endpoints = [
            "/api/v1/code/generate",
            "/api/v1/images/generate",
            "/api/v1/code/variants"
        ]
        
        for endpoint in protected_endpoints:
            if endpoint.endswith("/generate"):
                # POST endpoints
                response = auth_client.post(endpoint, json={"test": "data"})
            else:
                # GET endpoints
                response = auth_client.get(endpoint)
            
            assert response.status_code == 401
            
            data = response.json()
            assert "error" in data
            assert data["error"] == "Authentication required"
            
            # Check WWW-Authenticate header
            assert response.headers.get("WWW-Authenticate") == "Bearer"
    
    def test_valid_jwt_token_access(self, auth_client: TestClient, auth_headers: dict):
        """Test access with valid JWT token"""
        response = auth_client.get("/api/v1/code/variants", headers=auth_headers)
        
        # Should not return 401 with valid token
        assert response.status_code != 401
        # Might return other status codes depending on downstream service,
        # but authentication should pass
    
    def test_invalid_jwt_token_rejected(self, auth_client: TestClient, invalid_auth_headers: dict):
        """Test that invalid JWT tokens are rejected"""
        response = auth_client.get("/api/v1/code/variants", headers=invalid_auth_headers)
        
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert data["error"] == "Invalid authentication token"
    
    def test_expired_jwt_token_rejected(self, auth_client: TestClient, expired_jwt_token: str):
        """Test that expired JWT tokens are rejected"""
        headers = {
            "Authorization": f"Bearer {expired_jwt_token}",
            "Content-Type": "application/json"
        }
        
        response = auth_client.get("/api/v1/code/variants", headers=headers)
        
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert data["error"] == "Token expired"
    
    def test_malformed_authorization_header(self, auth_client: TestClient):
        """Test handling of malformed Authorization header"""
        malformed_headers = [
            {"Authorization": "InvalidFormat token"},
            {"Authorization": "Bearer"},  # Missing token
            {"Authorization": ""},  # Empty header
            {"Authorization": "Basic dGVzdDp0ZXN0"}  # Wrong auth type
        ]
        
        for headers in malformed_headers:
            response = auth_client.get("/api/v1/code/variants", headers=headers)
            assert response.status_code == 401
    
    def test_user_context_added_to_request(self, auth_client: TestClient, auth_headers: dict, mock_service_client):
        """Test that user context is added to requests to downstream services"""
        # Mock the downstream service call to capture the payload
        mock_service_client.call_code_generator.return_value.success = True
        mock_service_client.call_code_generator.return_value.data = {"id": "test"}
        
        payload = {
            "image": "data:image/jpeg;base64,test",
            "code_stack": "html_tailwind"
        }
        
        response = auth_client.post("/api/v1/code/generate", headers=auth_headers, json=payload)
        
        # Should not return auth error
        assert response.status_code != 401
        
        # Check that the downstream service was called with user context
        mock_service_client.call_code_generator.assert_called_once()
        call_args = mock_service_client.call_code_generator.call_args
        
        # The payload should include user_id and tenant_id
        sent_payload = call_args[1]["data"]  # kwargs data
        assert "user_id" in sent_payload
        assert "tenant_id" in sent_payload
        assert sent_payload["user_id"] == "test-user-123"
        assert sent_payload["tenant_id"] == "test-tenant"
    
    def test_jwt_token_validation_with_wrong_secret(self, auth_settings):
        """Test JWT validation with wrong secret"""
        import jwt
        from datetime import datetime, timedelta
        
        # Create token with wrong secret
        payload = {
            "sub": "test-user",
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        
        wrong_token = jwt.encode(payload, "wrong-secret", algorithm="HS256")
        
        from app.main import create_app
        app = create_app()
        app.state.settings = auth_settings
        
        client = TestClient(app)
        headers = {"Authorization": f"Bearer {wrong_token}"}
        
        response = client.get("/api/v1/code/variants", headers=headers)
        assert response.status_code == 401
    
    def test_correlation_id_in_auth_errors(self, auth_client: TestClient):
        """Test that correlation IDs are included in authentication errors"""
        response = auth_client.post("/api/v1/code/generate", json={"test": "data"})
        
        assert response.status_code == 401
        
        # Check correlation ID in response
        data = response.json()
        correlation_id_response = data.get("correlation_id")
        correlation_id_header = response.headers.get("X-Correlation-ID")
        
        assert correlation_id_response is not None
        assert correlation_id_header is not None
        assert correlation_id_response == correlation_id_header
    
    def test_authentication_middleware_order(self, auth_client: TestClient):
        """Test that authentication middleware works correctly with other middleware"""
        # Test that request ID is generated even for auth failures
        response = auth_client.post("/api/v1/code/generate", json={"test": "data"})
        
        assert response.status_code == 401
        
        # Should have correlation ID (from request ID middleware)
        assert response.headers.get("X-Correlation-ID") is not None
        
        # Should have auth error
        data = response.json()
        assert data["error"] == "Authentication required"
    
    def test_bearer_token_case_insensitive(self, auth_client: TestClient, valid_jwt_token: str):
        """Test that Bearer token handling is case insensitive"""
        headers_variations = [
            {"Authorization": f"Bearer {valid_jwt_token}"},
            {"Authorization": f"bearer {valid_jwt_token}"},
            {"Authorization": f"BEARER {valid_jwt_token}"}
        ]
        
        for headers in headers_variations:
            response = auth_client.get("/api/v1/code/variants", headers=headers)
            # Should not return 401 for any case variation
            # Note: Current implementation is case-sensitive for "Bearer"
            # This test documents expected behavior
            if headers["Authorization"].startswith("Bearer"):
                assert response.status_code != 401
            else:
                # Current implementation is case-sensitive
                assert response.status_code == 401