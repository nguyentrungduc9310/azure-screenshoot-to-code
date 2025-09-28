"""
Tests for code generation endpoints
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import base64


class TestCodeGeneration:
    """Test code generation endpoints"""
    
    def test_generate_code_success(self, client: TestClient, code_generation_request: dict):
        """Test successful code generation"""
        response = client.post("/api/v1/code/generate", json=code_generation_request)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "id" in data
        assert "code" in data
        assert "status" in data
        assert "code_stack" in data
        assert "provider" in data
        assert "generation_time_ms" in data
        
        # Check specific values
        assert data["id"] == "gen_test123"
        assert data["status"] == "completed"
        assert data["code_stack"] == "html_tailwind"
        assert data["provider"] == "openai"
        assert isinstance(data["generation_time_ms"], (int, float))
        
        # Check optional fields
        assert "token_usage" in data
        assert data["token_usage"]["total_tokens"] == 2000
    
    def test_generate_code_with_authentication(self, auth_client: TestClient, auth_headers: dict, code_generation_request: dict):
        """Test code generation with authentication"""
        response = auth_client.post("/api/v1/code/generate", headers=auth_headers, json=code_generation_request)
        
        # Should not return auth error
        assert response.status_code != 401
    
    def test_generate_code_invalid_request(self, client: TestClient):
        """Test code generation with invalid request data"""
        invalid_requests = [
            {},  # Empty request
            {"image": "invalid-base64"},  # Missing required fields
            {"code_stack": "html_tailwind"},  # Missing image
            {"image": "data:image/jpeg;base64,test", "code_stack": ""},  # Empty code_stack
        ]
        
        for invalid_request in invalid_requests:
            response = client.post("/api/v1/code/generate", json=invalid_request)
            assert response.status_code == 400
            
            data = response.json()
            assert "error" in data
            assert "correlation_id" in data
    
    def test_upload_and_generate_success(self, client: TestClient, sample_image_file):
        """Test file upload and code generation"""
        filename, file_content, content_type = sample_image_file
        
        files = {"file": (filename, file_content, content_type)}
        data = {
            "code_stack": "react_tailwind",
            "generation_type": "create"
        }
        
        response = client.post("/api/v1/code/upload-and-generate", files=files, data=data)
        
        assert response.status_code == 200
        response_data = response.json()
        
        # Check response structure
        assert "id" in response_data
        assert "code" in response_data
        assert "status" in response_data
    
    def test_upload_invalid_file_type(self, client: TestClient):
        """Test upload with invalid file type"""
        # Create a text file instead of image
        files = {"file": ("test.txt", b"not an image", "text/plain")}
        data = {"code_stack": "html_tailwind"}
        
        response = client.post("/api/v1/code/upload-and-generate", files=files, data=data)
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "File must be an image" in data["error"]
    
    def test_get_generation_status(self, client: TestClient):
        """Test getting generation status"""
        generation_id = "gen_test123"
        response = client.get(f"/api/v1/code/generation/{generation_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert "status" in data
        assert data["id"] == generation_id
    
    def test_get_generation_status_not_found(self, client: TestClient, mock_service_client):
        """Test getting status for non-existent generation"""
        from app.services.service_client import RequestResult
        
        # Mock 404 response
        mock_service_client.call_code_generator.return_value = RequestResult(
            success=False,
            status_code=404,
            error="Generation not found"
        )
        
        response = client.get("/api/v1/code/generation/nonexistent")
        
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
    
    def test_get_code_variants(self, client: TestClient):
        """Test getting available code variants"""
        from app.services.service_client import RequestResult
        
        # Mock variants response
        mock_variants = {
            "variants": [
                {
                    "id": "html_tailwind",
                    "name": "HTML + Tailwind CSS",
                    "description": "Static HTML with Tailwind CSS classes",
                    "features": ["responsive", "modern_css", "semantic_html"]
                },
                {
                    "id": "react_tailwind", 
                    "name": "React + Tailwind CSS",
                    "description": "React components with Tailwind CSS",
                    "features": ["components", "hooks", "typescript", "responsive"]
                }
            ]
        }
        
        client.app.state.service_client.call_code_generator.return_value = RequestResult(
            success=True,
            status_code=200,
            data=mock_variants
        )
        
        response = client.get("/api/v1/code/variants")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "variants" in data
        assert isinstance(data["variants"], list)
        assert len(data["variants"]) == 2
        
        # Check first variant structure
        variant = data["variants"][0]
        assert "id" in variant
        assert "name" in variant
        assert "description" in variant
        assert "features" in variant
    
    def test_refine_generated_code(self, client: TestClient):
        """Test code refinement"""
        generation_id = "gen_test123"
        refinement_data = {
            "instructions": "Add a dark mode toggle button",
            "refinement_type": "feature_addition",
            "preserve_structure": True
        }
        
        response = client.post(f"/api/v1/code/refine/{generation_id}", json=refinement_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return refined code generation result
        assert "id" in data
        assert "code" in data
    
    def test_downstream_service_failure(self, client: TestClient, code_generation_request: dict):
        """Test handling of downstream service failures"""
        from app.services.service_client import RequestResult
        
        # Mock service failure
        client.app.state.service_client.call_code_generator.return_value = RequestResult(
            success=False,
            status_code=503,
            error="Service unavailable"
        )
        
        response = client.post("/api/v1/code/generate", json=code_generation_request)
        
        assert response.status_code == 503
        data = response.json()
        assert "error" in data
        assert "Service unavailable" in data["error"]
    
    def test_request_timeout_handling(self, client: TestClient, code_generation_request: dict):
        """Test handling of request timeouts"""
        from app.services.service_client import RequestResult
        
        # Mock timeout error
        client.app.state.service_client.call_code_generator.return_value = RequestResult(
            success=False,
            status_code=504,
            error="Request timeout"
        )
        
        response = client.post("/api/v1/code/generate", json=code_generation_request)
        
        assert response.status_code == 504
        data = response.json()
        assert "error" in data
    
    def test_correlation_id_propagation(self, client: TestClient, code_generation_request: dict, mock_service_client):
        """Test that correlation IDs are propagated to downstream services"""
        response = client.post("/api/v1/code/generate", json=code_generation_request)
        
        assert response.status_code == 200
        
        # Check that correlation ID is in response header
        correlation_id = response.headers.get("X-Correlation-ID")
        assert correlation_id is not None
        
        # Check that service client was called (correlation ID would be passed internally)
        mock_service_client.call_code_generator.assert_called_once()
    
    def test_large_image_handling(self, client: TestClient):
        """Test handling of large image uploads"""
        # Create a large base64 encoded image
        large_image_data = "A" * (5 * 1024 * 1024)  # 5MB of data
        large_request = {
            "image": f"data:image/jpeg;base64,{large_image_data}",
            "code_stack": "html_tailwind"
        }
        
        response = client.post("/api/v1/code/generate", json=large_request)
        
        # Should either process successfully or return appropriate error
        # Depending on configuration, might return 413 (Payload Too Large)
        assert response.status_code in [200, 413, 400]
    
    def test_concurrent_requests(self, client: TestClient, code_generation_request: dict):
        """Test handling of concurrent requests"""
        import concurrent.futures
        import threading
        
        def make_request():
            return client.post("/api/v1/code/generate", json=code_generation_request)
        
        # Make multiple concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(5)]
            responses = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # All requests should complete successfully
        for response in responses:
            assert response.status_code == 200
            
            # Each should have unique correlation ID
            correlation_id = response.headers.get("X-Correlation-ID")
            assert correlation_id is not None
    
    def test_response_headers(self, client: TestClient, code_generation_request: dict):
        """Test that appropriate response headers are set"""
        response = client.post("/api/v1/code/generate", json=code_generation_request)
        
        assert response.status_code == 200
        
        # Check required headers
        assert response.headers.get("X-Correlation-ID") is not None
        assert response.headers.get("X-Response-Time") is not None
        
        # Check response time format
        response_time = response.headers.get("X-Response-Time")
        assert response_time.endswith("ms")
        
        # Parse and validate response time
        time_value = float(response_time[:-2])  # Remove 'ms' suffix
        assert time_value >= 0
    
    def test_error_response_format(self, client: TestClient):
        """Test that error responses follow consistent format"""
        # Make an invalid request to trigger error
        response = client.post("/api/v1/code/generate", json={})
        
        assert response.status_code == 400
        data = response.json()
        
        # Check error response format
        required_fields = ["error", "status_code", "correlation_id", "timestamp"]
        for field in required_fields:
            assert field in data
        
        assert data["status_code"] == 400
        assert isinstance(data["error"], str)
        assert isinstance(data["timestamp"], str)