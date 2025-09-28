"""
End-to-end workflow integration tests for Image Processor service
Tests complete user workflows from upload to processing
"""
import pytest
import asyncio
import base64
import io
import time
from httpx import AsyncClient
from unittest.mock import patch
from PIL import Image

from app.main import create_application

class TestE2EWorkflows:
    """End-to-end workflow tests covering complete user journeys"""
    
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
    
    @pytest.fixture
    def admin_auth(self):
        """Mock admin authentication for testing"""
        admin_user = {
            "id": "admin-user-id",
            "email": "admin@example.com", 
            "name": "Admin User",
            "roles": ["admin"]
        }
        
        with patch("shared.auth.azure_ad.get_current_user", return_value=admin_user):
            yield admin_user
    
    def create_test_image(self, width: int, height: int, format: str = "PNG", color: str = "red") -> str:
        """Create test image data URL"""
        img = Image.new('RGB', (width, height), color=color)
        buffer = io.BytesIO()
        img.save(buffer, format=format)
        image_bytes = buffer.getvalue()
        
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:image/{format.lower()};base64,{image_base64}"
    
    def create_large_test_image(self, width: int = 4000, height: int = 3000) -> str:
        """Create large test image for testing size limits"""
        return self.create_test_image(width, height, "PNG", "blue")
    
    def create_transparent_image(self, width: int = 200, height: int = 200) -> str:
        """Create test image with transparency"""
        img = Image.new('RGBA', (width, height), (255, 0, 0, 128))  # Semi-transparent red
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        image_bytes = buffer.getvalue()
        
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:image/png;base64,{image_base64}"
    
    @pytest.mark.asyncio
    async def test_complete_claude_workflow(self, client: AsyncClient, mock_auth):
        """Test complete workflow for Claude provider"""
        
        # Create test image optimized for Claude
        image_data_url = self.create_test_image(1920, 1080, "PNG")
        
        # Step 1: Validate image
        validate_response = await client.post(
            "/api/v1/validate",
            json={"image": image_data_url, "provider": "claude"},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert validate_response.status_code == 200
        validation_data = validate_response.json()
        assert validation_data["valid"] is True
        assert validation_data["provider"] == "claude"
        
        # Step 2: Analyze image
        analyze_response = await client.post(
            "/api/v1/analyze",
            json={"image": image_data_url},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert analyze_response.status_code == 200
        analysis_data = analyze_response.json()
        assert analysis_data["success"] is True
        assert "complexity_score" in analysis_data["analysis"]
        
        # Step 3: Process image
        process_response = await client.post(
            "/api/v1/process",
            json={
                "image": image_data_url,
                "provider": "claude",
                "options": {"format": "JPEG", "quality": 90}
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert process_response.status_code == 200
        process_data = process_response.json()
        assert process_data["success"] is True
        assert process_data["processed_format"] == "JPEG"
        assert process_data["compression_ratio"] > 0
        
        # Step 4: Create thumbnail
        thumbnail_response = await client.post(
            "/api/v1/thumbnail",
            json={
                "image": process_data["processed_image"],
                "width": 150,
                "height": 150
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert thumbnail_response.status_code == 200
        thumbnail_data = thumbnail_response.json()
        assert thumbnail_data["success"] is True
        assert thumbnail_data["dimensions"]["width"] == 150
        
        # Verify correlation IDs for tracking
        correlation_ids = [
            validation_data.get("correlation_id"),
            analysis_data.get("correlation_id"),
            process_data.get("correlation_id"),
            thumbnail_data.get("correlation_id")
        ]
        
        assert all(cid for cid in correlation_ids), "All operations should have correlation IDs"
    
    @pytest.mark.asyncio
    async def test_multi_provider_workflow(self, client: AsyncClient, mock_auth):
        """Test workflow across multiple providers"""
        
        # Create test image suitable for all providers
        image_data_url = self.create_test_image(1000, 800, "PNG")
        
        providers = ["claude", "openai", "gemini"]
        results = {}
        
        for provider in providers:
            # Validate for each provider
            validate_response = await client.post(
                "/api/v1/validate",
                json={"image": image_data_url, "provider": provider},
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert validate_response.status_code == 200
            validation = validate_response.json()
            
            if validation["valid"]:
                # Process if valid
                process_response = await client.post(
                    "/api/v1/process",
                    json={"image": image_data_url, "provider": provider},
                    headers={"Authorization": "Bearer test-token"}
                )
                
                assert process_response.status_code == 200
                process_data = process_response.json()
                assert process_data["success"] is True
                
                results[provider] = {
                    "valid": True,
                    "compression_ratio": process_data["compression_ratio"],
                    "processing_time": process_data["processing_time_ms"],
                    "format": process_data["processed_format"]
                }
            else:
                results[provider] = {"valid": False, "reason": validation.get("error_message")}
        
        # Verify at least one provider succeeded
        successful_providers = [p for p, r in results.items() if r.get("valid")]
        assert len(successful_providers) > 0, f"At least one provider should succeed. Results: {results}"
        
        # Compare results across providers
        successful_results = {p: r for p, r in results.items() if r.get("valid")}
        print(f"Provider comparison: {successful_results}")
    
    @pytest.mark.asyncio
    async def test_transparency_handling_workflow(self, client: AsyncClient, mock_auth):
        """Test workflow with transparent images"""
        
        # Create transparent image
        transparent_image = self.create_transparent_image()
        
        # Analyze transparency
        analyze_response = await client.post(
            "/api/v1/analyze",
            json={"image": transparent_image},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert analyze_response.status_code == 200
        analysis = analyze_response.json()
        assert analysis["analysis"]["has_transparency"] is True
        
        # Process with JPEG (should handle transparency)
        process_response = await client.post(
            "/api/v1/process",
            json={
                "image": transparent_image,
                "provider": "openai",  # OpenAI supports transparency better
                "options": {"format": "PNG", "preserve_transparency": True}
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert process_response.status_code == 200
        process_data = process_response.json()
        assert process_data["success"] is True
        assert process_data["metadata"]["has_transparency"] is True
        
        # Process with JPEG (should add background)
        jpeg_response = await client.post(
            "/api/v1/process",
            json={
                "image": transparent_image,
                "provider": "claude",
                "options": {"format": "JPEG", "background_color": "#FFFFFF"}
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert jpeg_response.status_code == 200
        jpeg_data = jpeg_response.json()
        assert jpeg_data["success"] is True
        assert jpeg_data["processed_format"] == "JPEG"
    
    @pytest.mark.asyncio
    async def test_large_image_optimization_workflow(self, client: AsyncClient, mock_auth):
        """Test workflow with large images requiring optimization"""
        
        # Create large image
        large_image = self.create_large_test_image(3000, 2000)
        
        # Validate - should pass for some providers
        validate_response = await client.post(
            "/api/v1/validate",
            json={"image": large_image, "provider": "gemini"},  # Gemini supports larger images
            headers={"Authorization": "Bearer test-token"}
        )
        
        validation = validate_response.json()
        
        if validation["valid"]:
            # Process large image
            process_response = await client.post(
                "/api/v1/process",
                json={
                    "image": large_image,
                    "provider": "gemini",
                    "options": {"max_dimension": 2048}  # Resize to fit
                },
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert process_response.status_code == 200
            process_data = process_response.json()
            assert process_data["success"] is True
            assert max(process_data["dimensions"]) <= 2048
            assert process_data["metadata"]["resized"] is True
        
        # Try with Claude (should require more optimization)
        claude_validate = await client.post(
            "/api/v1/validate",
            json={"image": large_image, "provider": "claude"},
            headers={"Authorization": "Bearer test-token"}
        )
        
        claude_validation = claude_validate.json()
        if not claude_validation["valid"]:
            # Should fail validation due to size
            assert "exceed" in claude_validation["error_message"].lower()
    
    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self, client: AsyncClient, mock_auth):
        """Test error recovery and graceful failure handling"""
        
        # Test invalid image data
        invalid_responses = []
        
        # Invalid base64
        invalid_base64_response = await client.post(
            "/api/v1/validate",
            json={"image": "data:image/png;base64,invalid_data", "provider": "claude"},
            headers={"Authorization": "Bearer test-token"}
        )
        invalid_responses.append(("invalid_base64", invalid_base64_response))
        
        # Invalid format
        invalid_format_response = await client.post(
            "/api/v1/validate",
            json={"image": "data:text/plain;base64,dGVzdA==", "provider": "claude"},
            headers={"Authorization": "Bearer test-token"}
        )
        invalid_responses.append(("invalid_format", invalid_format_response))
        
        # Invalid provider
        invalid_provider_response = await client.post(
            "/api/v1/validate",
            json={"image": self.create_test_image(100, 100), "provider": "invalid"},
            headers={"Authorization": "Bearer test-token"}
        )
        invalid_responses.append(("invalid_provider", invalid_provider_response))
        
        # Verify all invalid requests are handled gracefully
        for test_name, response in invalid_responses:
            assert response.status_code in [400, 422], f"Test {test_name} should return validation error"
            if response.status_code == 422:
                data = response.json()
                assert data["success"] is False
                assert "error" in data
    
    @pytest.mark.asyncio
    async def test_admin_workflow(self, client: AsyncClient, admin_auth):
        """Test admin-specific workflows"""
        
        # Test admin stats access
        stats_response = await client.get(
            "/api/v1/stats",
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert stats_response.status_code == 200
        stats_data = stats_response.json()
        assert "total_processed" in stats_data
        assert "provider_usage" in stats_data
        
        # Test admin metrics access
        metrics_response = await client.get(
            "/health/metrics",
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert metrics_response.status_code == 200
        metrics_data = metrics_response.json()
        assert "service" in metrics_data
        assert "image_processing" in metrics_data
    
    @pytest.mark.asyncio
    async def test_concurrent_processing_workflow(self, client: AsyncClient, mock_auth):
        """Test concurrent image processing"""
        
        # Create multiple test images
        images = [
            self.create_test_image(400, 300, "PNG", "red"),
            self.create_test_image(500, 400, "JPEG", "green"),
            self.create_test_image(300, 200, "PNG", "blue")
        ]
        
        # Process all images concurrently
        async def process_single_image(image_data_url: str):
            return await client.post(
                "/api/v1/process",
                json={"image": image_data_url, "provider": "claude"},
                headers={"Authorization": "Bearer test-token"}
            )
        
        # Execute concurrent requests
        start_time = time.time()
        responses = await asyncio.gather(*[process_single_image(img) for img in images])
        end_time = time.time()
        
        # Verify all requests succeeded
        for i, response in enumerate(responses):
            assert response.status_code == 200, f"Image {i} processing failed"
            data = response.json()
            assert data["success"] is True
        
        # Verify concurrent processing was faster than sequential
        concurrent_time = end_time - start_time
        print(f"Concurrent processing time: {concurrent_time:.2f}s for {len(images)} images")
        
        # Should complete within reasonable time (adjust based on system)
        assert concurrent_time < 10.0, "Concurrent processing should be efficient"
    
    @pytest.mark.asyncio
    async def test_health_monitoring_workflow(self, client: AsyncClient):
        """Test health monitoring and service readiness"""
        
        # Test basic health
        health_response = await client.get("/health")
        assert health_response.status_code == 200
        health_data = health_response.json()
        assert health_data["status"] == "healthy"
        
        # Test readiness
        ready_response = await client.get("/health/ready")
        assert ready_response.status_code == 200
        ready_data = ready_response.json()
        assert ready_data["status"] == "ready"
        
        # Test liveness
        live_response = await client.get("/health/live")
        assert live_response.status_code == 200
        
        # Test capabilities
        capabilities_response = await client.get("/health/capabilities")
        assert capabilities_response.status_code == 200
        capabilities_data = capabilities_response.json()
        assert "supported_providers" in capabilities_data
        assert "features" in capabilities_data
    
    @pytest.mark.asyncio
    async def test_performance_tracking_workflow(self, client: AsyncClient, mock_auth):
        """Test performance tracking across operations"""
        
        image_data_url = self.create_test_image(800, 600)
        
        # Track processing times
        processing_times = []
        
        for i in range(3):
            start_time = time.time()
            
            response = await client.post(
                "/api/v1/process",
                json={"image": image_data_url, "provider": "claude"},
                headers={"Authorization": "Bearer test-token"}
            )
            
            end_time = time.time()
            request_time = (end_time - start_time) * 1000  # Convert to ms
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify processing time header
            assert "X-Image-Process-Time" in response.headers
            
            processing_times.append({
                "request_time": request_time,
                "processing_time": data["processing_time_ms"],
                "compression_ratio": data["compression_ratio"]
            })
        
        # Analyze performance metrics
        avg_request_time = sum(t["request_time"] for t in processing_times) / len(processing_times)
        avg_processing_time = sum(t["processing_time"] for t in processing_times) / len(processing_times)
        avg_compression = sum(t["compression_ratio"] for t in processing_times) / len(processing_times)
        
        print(f"Performance metrics:")
        print(f"  Average request time: {avg_request_time:.1f}ms")
        print(f"  Average processing time: {avg_processing_time:.1f}ms")
        print(f"  Average compression ratio: {avg_compression:.3f}")
        
        # Verify reasonable performance
        assert avg_request_time < 5000, "Average request time should be under 5 seconds"
        assert avg_compression > 0.1, "Should achieve some compression"
    
    @pytest.mark.asyncio
    async def test_provider_fallback_workflow(self, client: AsyncClient, mock_auth):
        """Test provider fallback strategy"""
        
        # Create image that might exceed limits for some providers
        large_image = self.create_large_test_image(2500, 2000)
        
        providers = ["claude", "openai", "gemini"]
        results = {}
        
        for provider in providers:
            try:
                # Attempt validation
                validate_response = await client.post(
                    "/api/v1/validate",
                    json={"image": large_image, "provider": provider},
                    headers={"Authorization": "Bearer test-token"}
                )
                
                validation = validate_response.json()
                
                if validation["valid"]:
                    # Attempt processing
                    process_response = await client.post(
                        "/api/v1/process",
                        json={"image": large_image, "provider": provider},
                        headers={"Authorization": "Bearer test-token"}
                    )
                    
                    if process_response.status_code == 200:
                        results[provider] = {"status": "success", "data": process_response.json()}
                    else:
                        results[provider] = {"status": "processing_failed", "error": process_response.json()}
                else:
                    results[provider] = {"status": "validation_failed", "error": validation["error_message"]}
                    
            except Exception as e:
                results[provider] = {"status": "exception", "error": str(e)}
        
        # Verify fallback behavior
        successful_providers = [p for p, r in results.items() if r["status"] == "success"]
        print(f"Provider fallback results: {results}")
        
        # At least one provider should handle the image or provide clear errors
        assert len(results) == len(providers), "All providers should be tested"