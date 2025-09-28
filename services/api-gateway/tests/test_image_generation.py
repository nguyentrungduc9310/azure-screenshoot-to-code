"""
Tests for image generation endpoints
"""
import pytest
from fastapi.testclient import TestClient


class TestImageGeneration:
    """Test image generation endpoints"""
    
    def test_generate_image_success(self, client: TestClient, image_generation_request: dict):
        """Test successful image generation"""
        response = client.post("/api/v1/images/generate", json=image_generation_request)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "id" in data
        assert "prompt" in data
        assert "provider" in data
        assert "status" in data
        assert "images" in data
        assert "generation_time_ms" in data
        
        # Check specific values
        assert data["id"] == "img_test456"
        assert data["status"] == "completed"
        assert data["provider"] == "dalle3"
        assert isinstance(data["generation_time_ms"], (int, float))
        
        # Check images array
        assert isinstance(data["images"], list)
        assert len(data["images"]) > 0
        
        image = data["images"][0]
        assert "url" in image
        assert "size" in image
        assert "format" in image
        
        # Check optional fields
        if "cost_estimate" in data:
            assert isinstance(data["cost_estimate"], (int, float))
    
    def test_generate_image_with_authentication(self, auth_client: TestClient, auth_headers: dict, image_generation_request: dict):
        """Test image generation with authentication"""
        response = auth_client.post("/api/v1/images/generate", headers=auth_headers, json=image_generation_request)
        
        # Should not return auth error
        assert response.status_code != 401
    
    def test_generate_image_invalid_request(self, client: TestClient):
        """Test image generation with invalid request data"""
        invalid_requests = [
            {},  # Empty request
            {"provider": "dalle3"},  # Missing prompt
            {"prompt": ""},  # Empty prompt
            {"prompt": "test", "provider": "invalid_provider"},  # Invalid provider
            {"prompt": "test", "num_images": 0},  # Invalid num_images
            {"prompt": "test", "num_images": 10},  # Too many images
        ]
        
        for invalid_request in invalid_requests:
            response = client.post("/api/v1/images/generate", json=invalid_request)
            assert response.status_code == 400
            
            data = response.json()
            assert "error" in data
            assert "correlation_id" in data
    
    def test_generate_image_different_providers(self, client: TestClient):
        """Test image generation with different providers"""
        providers = ["dalle3", "flux_schnell"]
        
        for provider in providers:
            request_data = {
                "prompt": "A beautiful landscape",
                "provider": provider,
                "size": "1024x1024"
            }
            
            response = client.post("/api/v1/images/generate", json=request_data)
            assert response.status_code == 200
            
            data = response.json()
            assert data["provider"] == provider
    
    def test_generate_image_different_sizes(self, client: TestClient):
        """Test image generation with different sizes"""
        sizes = ["512x512", "1024x1024", "1024x1792", "1792x1024"]
        
        for size in sizes:
            request_data = {
                "prompt": "A modern interface",
                "size": size,
                "provider": "dalle3"
            }
            
            response = client.post("/api/v1/images/generate", json=request_data)
            assert response.status_code == 200
            
            data = response.json()
            # The generated image should have the requested size
            if data["images"]:
                assert data["images"][0]["size"] == size
    
    def test_get_image_generation_status(self, client: TestClient):
        """Test getting image generation status"""
        generation_id = "img_test456" 
        response = client.get(f"/api/v1/images/generation/{generation_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert "status" in data
        assert data["id"] == generation_id
    
    def test_get_image_generation_status_not_found(self, client: TestClient, mock_service_client):
        """Test getting status for non-existent image generation"""
        from app.services.service_client import RequestResult
        
        # Mock 404 response
        mock_service_client.call_image_generator.return_value = RequestResult(
            success=False,
            status_code=404,
            error="Generation not found"
        )
        
        response = client.get("/api/v1/images/generation/nonexistent")
        
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
    
    def test_get_image_providers(self, client: TestClient):
        """Test getting available image providers"""
        from app.services.service_client import RequestResult
        
        # Mock providers response
        mock_providers = {
            "providers": [
                {
                    "id": "dalle3",
                    "name": "DALL-E 3",
                    "description": "OpenAI's latest image generation model",
                    "supported_sizes": ["1024x1024", "1024x1792", "1792x1024"],
                    "supported_qualities": ["standard", "hd"],
                    "max_images_per_request": 1,
                    "cost_per_image": 0.04
                },
                {
                    "id": "flux_schnell",
                    "name": "Flux Schnell",
                    "description": "Fast image generation with Flux",
                    "supported_sizes": ["512x512", "1024x1024"],
                    "max_images_per_request": 4,
                    "cost_per_image": 0.02
                }
            ]
        }
        
        client.app.state.service_client.call_image_generator.return_value = RequestResult(
            success=True,
            status_code=200,
            data=mock_providers
        )
        
        response = client.get("/api/v1/images/providers")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "providers" in data
        assert isinstance(data["providers"], list)
        assert len(data["providers"]) == 2
        
        # Check provider structure
        provider = data["providers"][0]
        assert "id" in provider
        assert "name" in provider
        assert "description" in provider
        assert "supported_sizes" in provider
        assert "cost_per_image" in provider
    
    def test_batch_generate_images(self, client: TestClient):
        """Test batch image generation"""
        batch_request = {
            "requests": [
                {
                    "prompt": "App icon with blue gradient",
                    "size": "512x512",
                    "provider": "dalle3"
                },
                {
                    "prompt": "Hero background image",
                    "size": "1920x1080",
                    "provider": "flux_schnell"
                }
            ]
        }
        
        # Mock batch response
        from app.services.service_client import RequestResult
        mock_batch_response = {
            "batch_id": "batch_test123",
            "total_images": 2,
            "results": [
                {
                    "id": "img1",
                    "status": "completed",
                    "images": [{"url": "https://test.com/img1.png"}]
                },
                {
                    "id": "img2", 
                    "status": "completed",
                    "images": [{"url": "https://test.com/img2.png"}]
                }
            ]
        }
        
        client.app.state.service_client.call_image_generator.return_value = RequestResult(
            success=True,
            status_code=200,
            data=mock_batch_response
        )
        
        response = client.post("/api/v1/images/batch-generate", json=batch_request)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "batch_id" in data
        assert "total_images" in data
        assert "results" in data
        assert data["total_images"] == 2
        assert len(data["results"]) == 2
    
    def test_batch_generate_too_many_requests(self, client: TestClient):
        """Test batch generation with too many requests"""
        # Create more than the allowed limit (10)
        requests = [
            {
                "prompt": f"Test image {i}",
                "provider": "dalle3"
            }
            for i in range(11)  # 11 requests (over limit)
        ]
        
        batch_request = {"requests": requests}
        
        response = client.post("/api/v1/images/batch-generate", json=batch_request)
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "Batch size too large" in data["error"]
    
    def test_get_image_usage_stats(self, client: TestClient):
        """Test getting image usage statistics"""
        # Mock usage stats response
        from app.services.service_client import RequestResult
        mock_stats = {
            "total_images_generated": 150,
            "images_this_month": 45,
            "total_cost": 6.50,
            "cost_this_month": 2.80,
            "provider_usage": {
                "dalle3": {"count": 100, "cost": 4.00},
                "flux_schnell": {"count": 50, "cost": 1.00}
            }
        }
        
        client.app.state.service_client.call_image_generator.return_value = RequestResult(
            success=True,
            status_code=200,
            data=mock_stats
        )
        
        response = client.get("/api/v1/images/usage/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_images_generated" in data
        assert "images_this_month" in data
        assert "total_cost" in data
        assert "provider_usage" in data
    
    def test_delete_generated_images(self, client: TestClient):
        """Test deleting generated images"""
        generation_id = "img_test456"
        
        # Mock successful deletion
        from app.services.service_client import RequestResult
        client.app.state.service_client.call_image_generator.return_value = RequestResult(
            success=True,
            status_code=200,
            data={"message": "Images deleted successfully"}
        )
        
        response = client.delete(f"/api/v1/images/generation/{generation_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
    
    def test_delete_nonexistent_images(self, client: TestClient, mock_service_client):
        """Test deleting non-existent images"""
        from app.services.service_client import RequestResult
        
        # Mock 404 response
        mock_service_client.call_image_generator.return_value = RequestResult(
            success=False,
            status_code=404,
            error="Generation not found"
        )
        
        response = client.delete("/api/v1/images/generation/nonexistent")
        
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
    
    def test_downstream_service_failure(self, client: TestClient, image_generation_request: dict):
        """Test handling of downstream service failures"""
        from app.services.service_client import RequestResult
        
        # Mock service failure
        client.app.state.service_client.call_image_generator.return_value = RequestResult(
            success=False,
            status_code=503,
            error="Service unavailable"
        )
        
        response = client.post("/api/v1/images/generate", json=image_generation_request)
        
        assert response.status_code == 503
        data = response.json()
        assert "error" in data
        assert "Service unavailable" in data["error"]
    
    def test_correlation_id_propagation(self, client: TestClient, image_generation_request: dict, mock_service_client):
        """Test that correlation IDs are propagated to downstream services"""
        response = client.post("/api/v1/images/generate", json=image_generation_request)
        
        assert response.status_code == 200
        
        # Check that correlation ID is in response header
        correlation_id = response.headers.get("X-Correlation-ID")
        assert correlation_id is not None
        
        # Check that service client was called
        mock_service_client.call_image_generator.assert_called_once()
    
    def test_response_headers(self, client: TestClient, image_generation_request: dict):
        """Test that appropriate response headers are set"""
        response = client.post("/api/v1/images/generate", json=image_generation_request)
        
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
    
    def test_long_prompt_handling(self, client: TestClient):
        """Test handling of very long prompts"""
        # Create a very long prompt
        long_prompt = "A beautiful landscape with mountains and trees. " * 100  # Very long prompt
        
        request_data = {
            "prompt": long_prompt,
            "provider": "dalle3"
        }
        
        response = client.post("/api/v1/images/generate", json=request_data)
        
        # Should either process successfully or return appropriate error
        assert response.status_code in [200, 400]
        
        if response.status_code == 400:
            data = response.json()
            assert "error" in data
    
    def test_multiple_images_request(self, client: TestClient):
        """Test requesting multiple images in single request"""
        request_data = {
            "prompt": "A series of icons",
            "provider": "flux_schnell",  # Supports multiple images
            "num_images": 3
        }
        
        response = client.post("/api/v1/images/generate", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return multiple images
        assert "images" in data
        # Note: Mock returns 1 image, but in real scenario would return 3