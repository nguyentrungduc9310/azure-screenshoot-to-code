"""
Integration tests for Image Processor API endpoints
"""
import pytest
import base64
import io
from httpx import AsyncClient
from unittest.mock import patch
from PIL import Image

from app.main import create_application

class TestImageProcessorAPI:
    """Integration tests for Image Processor API endpoints"""
    
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
    def sample_image_data_url(self):
        """Generate sample image for testing"""
        img = Image.new('RGB', (200, 200), color='green')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        image_bytes = buffer.getvalue()
        
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:image/png;base64,{image_base64}"
    
    @pytest.fixture
    def mock_auth(self):
        """Mock authentication for testing"""
        mock_user = {
            "id": "test-user-id",
            "email": "test@example.com",
            "name": "Test User",
            "roles": ["user"]
        }
        
        with patch("shared.auth.azure_ad.get_current_user", return_value=mock_user):
            yield mock_user
    
    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test health check endpoint"""
        
        response = await client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "image-processor"
    
    @pytest.mark.asyncio
    async def test_health_ready(self, client: AsyncClient):
        """Test readiness probe"""
        
        response = await client.get("/health/ready")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
    
    @pytest.mark.asyncio
    async def test_health_metrics_authenticated(self, client: AsyncClient, mock_auth):
        """Test metrics endpoint with authentication"""
        
        response = await client.get(
            "/health/metrics",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "system" in data
        assert "application" in data
        assert "image_processing" in data
    
    @pytest.mark.asyncio
    async def test_capabilities_endpoint(self, client: AsyncClient):
        """Test capabilities endpoint (public)"""
        
        response = await client.get("/health/capabilities")
        
        assert response.status_code == 200
        data = response.json()
        assert "supported_providers" in data
        assert "features" in data
        assert "read_formats" in data or "error" in data  # Depends on PIL availability
    
    @pytest.mark.asyncio
    async def test_process_image_success(self, client: AsyncClient, mock_auth, sample_image_data_url):
        """Test successful image processing"""
        
        request_data = {
            "image": sample_image_data_url,
            "provider": "claude",
            "options": {"quality": 90}
        }
        
        response = await client.post(
            "/api/v1/process",
            json=request_data,
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "processed_image" in data
        assert data["processed_image"].startswith("data:image/")
        assert "processing_time_ms" in data
        assert "compression_ratio" in data
        assert "correlation_id" in data
    
    @pytest.mark.asyncio
    async def test_process_image_unauthenticated(self, client: AsyncClient, sample_image_data_url):
        """Test image processing without authentication"""
        
        request_data = {
            "image": sample_image_data_url,
            "provider": "claude"
        }
        
        response = await client.post("/api/v1/process", json=request_data)
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_process_image_invalid_data(self, client: AsyncClient, mock_auth):
        """Test image processing with invalid data"""
        
        request_data = {
            "image": "invalid-data-url",
            "provider": "claude"
        }
        
        response = await client.post(
            "/api/v1/process",
            json=request_data,
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_validate_image_success(self, client: AsyncClient, mock_auth, sample_image_data_url):
        """Test successful image validation"""
        
        request_data = {
            "image": sample_image_data_url,
            "provider": "claude"
        }
        
        response = await client.post(
            "/api/v1/validate",
            json=request_data,
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "valid" in data
        assert "dimensions" in data
        assert "format" in data
        assert "file_size" in data
        assert "provider" in data
    
    @pytest.mark.asyncio
    async def test_analyze_image(self, client: AsyncClient, mock_auth, sample_image_data_url):
        """Test image analysis endpoint"""
        
        request_data = {
            "image": sample_image_data_url
        }
        
        response = await client.post(
            "/api/v1/analyze",
            json=request_data,
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "analysis" in data
        assert "dimensions" in data["analysis"]
        assert "format" in data["analysis"]
        assert "complexity_score" in data["analysis"]
    
    @pytest.mark.asyncio
    async def test_create_thumbnail(self, client: AsyncClient, mock_auth, sample_image_data_url):
        """Test thumbnail creation endpoint"""
        
        request_data = {
            "image": sample_image_data_url,
            "width": 100,
            "height": 100
        }
        
        response = await client.post(
            "/api/v1/thumbnail",
            json=request_data,
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "thumbnail" in data
        assert data["thumbnail"].startswith("data:image/jpeg")
        assert data["dimensions"]["width"] == 100
        assert data["dimensions"]["height"] == 100
    
    @pytest.mark.asyncio
    async def test_get_providers(self, client: AsyncClient, mock_auth):
        """Test get supported providers endpoint"""
        
        response = await client.get(
            "/api/v1/providers",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "supported_providers" in data
        assert "provider_requirements" in data
        assert "claude" in data["supported_providers"]
        assert "openai" in data["supported_providers"]
        assert "gemini" in data["supported_providers"]
    
    @pytest.mark.asyncio
    async def test_different_providers(self, client: AsyncClient, mock_auth, sample_image_data_url):
        """Test processing with different providers"""
        
        providers = ["claude", "openai", "gemini"]
        
        for provider in providers:
            request_data = {
                "image": sample_image_data_url,
                "provider": provider
            }
            
            response = await client.post(
                "/api/v1/process",
                json=request_data,
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == 200, f"Failed for provider: {provider}"
            data = response.json()
            assert data["success"] is True
    
    @pytest.mark.asyncio
    async def test_invalid_provider(self, client: AsyncClient, mock_auth, sample_image_data_url):
        """Test with invalid provider"""
        
        request_data = {
            "image": sample_image_data_url,
            "provider": "invalid-provider"
        }
        
        response = await client.post(
            "/api/v1/process",
            json=request_data,
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_request_size_limit(self, client: AsyncClient, mock_auth):
        """Test request size limitation"""
        
        # Create very large image data
        large_data = "x" * (60 * 1024 * 1024)  # 60MB
        
        response = await client.post(
            "/api/v1/process",
            content=large_data,
            headers={
                "Authorization": "Bearer test-token",
                "Content-Type": "application/json",
                "Content-Length": str(len(large_data))
            }
        )
        
        assert response.status_code == 413  # Request too large
    
    @pytest.mark.asyncio
    async def test_cors_headers(self, client: AsyncClient):
        """Test CORS headers are properly set"""
        
        response = await client.options("/api/v1/process")
        
        # Check if CORS headers are present
        assert "access-control-allow-origin" in response.headers or response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_processing_time_header(self, client: AsyncClient, mock_auth, sample_image_data_url):
        """Test that processing time header is added"""
        
        request_data = {
            "image": sample_image_data_url,
            "provider": "claude"
        }
        
        response = await client.post(
            "/api/v1/process",
            json=request_data,
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        # Check for processing time header
        assert "X-Image-Process-Time" in response.headers
    
    @pytest.mark.asyncio
    async def test_thumbnail_invalid_dimensions(self, client: AsyncClient, mock_auth, sample_image_data_url):
        """Test thumbnail creation with invalid dimensions"""
        
        request_data = {
            "image": sample_image_data_url,
            "width": 1000,  # Too large
            "height": 1000
        }
        
        response = await client.post(
            "/api/v1/thumbnail",
            json=request_data,
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_admin_stats_endpoint(self, client: AsyncClient):
        """Test admin stats endpoint (requires admin role)"""
        
        admin_user = {
            "id": "admin-user-id",
            "email": "admin@example.com",
            "name": "Admin User",
            "roles": ["admin"]
        }
        
        with patch("shared.auth.azure_ad.get_current_user", return_value=admin_user):
            response = await client.get(
                "/api/v1/stats",
                headers={"Authorization": "Bearer admin-token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "total_processed" in data
        assert "average_processing_time_ms" in data
        assert "provider_usage" in data
    
    @pytest.mark.asyncio
    async def test_admin_stats_unauthorized(self, client: AsyncClient, mock_auth):
        """Test admin stats endpoint with non-admin user"""
        
        response = await client.get(
            "/api/v1/stats",
            headers={"Authorization": "Bearer user-token"}
        )
        
        assert response.status_code == 403  # Forbidden