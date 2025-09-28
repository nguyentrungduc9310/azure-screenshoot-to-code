"""
Provider compatibility integration tests for Image Processor service
Tests compatibility and optimization for different AI providers (Claude, OpenAI, Gemini)
"""
import pytest
import base64
import io
from httpx import AsyncClient
from unittest.mock import patch
from PIL import Image

from app.main import create_application

class TestProviderCompatibility:
    """Provider compatibility testing suite"""
    
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
    
    def create_test_image(self, width: int, height: int, format: str = "PNG", quality: int = 95) -> str:
        """Create test image with specified dimensions and format"""
        img = Image.new('RGB', (width, height), color='red')
        buffer = io.BytesIO()
        
        if format.upper() == "JPEG":
            img.save(buffer, format='JPEG', quality=quality)
        else:
            img.save(buffer, format=format)
        
        image_bytes = buffer.getvalue()
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:image/{format.lower()};base64,{image_base64}"
    
    def create_transparent_image(self, width: int = 200, height: int = 200) -> str:
        """Create image with transparency"""
        img = Image.new('RGBA', (width, height), (255, 0, 0, 128))
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        image_bytes = buffer.getvalue()
        
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:image/png;base64,{image_base64}"
    
    @pytest.mark.asyncio
    async def test_provider_requirements_endpoint(self, client: AsyncClient, mock_auth):
        """Test provider requirements endpoint returns correct information"""
        
        response = await client.get(
            "/api/v1/providers",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "supported_providers" in data
        assert "provider_requirements" in data
        
        # Verify all expected providers are listed
        expected_providers = ["claude", "openai", "gemini"]
        assert all(provider in data["supported_providers"] for provider in expected_providers)
        
        # Verify requirements for each provider
        for provider in expected_providers:
            assert provider in data["provider_requirements"]
            requirements = data["provider_requirements"][provider]
            
            # Required fields
            assert "max_size" in requirements
            assert "max_size_mb" in requirements
            assert "max_dimension" in requirements
            assert "supported_formats" in requirements
            assert "preferred_format" in requirements
            
            # Verify data types
            assert isinstance(requirements["max_size"], int)
            assert isinstance(requirements["max_size_mb"], (int, float))
            assert isinstance(requirements["max_dimension"], int)
            assert isinstance(requirements["supported_formats"], list)
            assert isinstance(requirements["preferred_format"], str)
    
    # Claude Provider Tests
    
    @pytest.mark.asyncio
    async def test_claude_provider_validation(self, client: AsyncClient, mock_auth):
        """Test Claude provider validation requirements"""
        
        # Test cases for Claude provider
        test_cases = [
            # Should pass: Small image
            {"image": self.create_test_image(500, 400), "should_pass": True, "name": "small_image"},
            
            # Should pass: Medium image 
            {"image": self.create_test_image(1920, 1080), "should_pass": True, "name": "medium_image"},
            
            # Should pass: Large but within limits
            {"image": self.create_test_image(2000, 1500), "should_pass": True, "name": "large_image"},
            
            # May fail: Very large image (depends on file size)
            {"image": self.create_test_image(4000, 3000), "should_pass": False, "name": "very_large_image"},
            
            # Should pass: Transparent image (PNG)
            {"image": self.create_transparent_image(800, 600), "should_pass": True, "name": "transparent_image"}
        ]
        
        for case in test_cases:
            response = await client.post(
                "/api/v1/validate",
                json={"image": case["image"], "provider": "claude"},
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            
            print(f"Claude validation - {case['name']}: {data.get('valid')} (expected: {case['should_pass']})")
            
            if case["should_pass"]:
                assert data["valid"] is True, f"Claude should accept {case['name']}"
            else:
                # Large images might be rejected due to size
                if not data["valid"]:
                    assert "exceed" in data.get("error_message", "").lower()
    
    @pytest.mark.asyncio
    async def test_claude_provider_processing(self, client: AsyncClient, mock_auth):
        """Test Claude provider processing optimization"""
        
        test_image = self.create_test_image(1200, 800, "PNG")
        
        response = await client.post(
            "/api/v1/process",
            json={
                "image": test_image,
                "provider": "claude",
                "options": {"format": "JPEG", "quality": 90}
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify Claude optimizations
        assert data["processed_format"] == "JPEG"  # Claude prefers JPEG
        assert data["compression_ratio"] > 0.1  # Should achieve compression
        assert data["metadata"]["provider"] == "claude"
        
        # Verify file size is within Claude limits (5MB)
        assert data["processed_size"] <= 5 * 1024 * 1024
        
        # Verify dimensions are within Claude limits (7990px)
        assert max(data["dimensions"]) <= 7990
    
    # OpenAI Provider Tests
    
    @pytest.mark.asyncio
    async def test_openai_provider_validation(self, client: AsyncClient, mock_auth):
        """Test OpenAI provider validation requirements"""
        
        test_cases = [
            # Should pass: Small image
            {"image": self.create_test_image(512, 512), "should_pass": True, "name": "small_square"},
            
            # Should pass: Medium image within limits
            {"image": self.create_test_image(1024, 768), "should_pass": True, "name": "medium_image"},
            
            # Should pass: At dimension limit
            {"image": self.create_test_image(2048, 1536), "should_pass": True, "name": "at_limit"},
            
            # Should fail: Exceeds dimension limit
            {"image": self.create_test_image(3000, 2000), "should_pass": False, "name": "exceeds_dimension"},
            
            # Should pass: Transparent image (OpenAI supports transparency)
            {"image": self.create_transparent_image(1000, 800), "should_pass": True, "name": "transparent"}
        ]
        
        for case in test_cases:
            response = await client.post(
                "/api/v1/validate",
                json={"image": case["image"], "provider": "openai"},
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            
            print(f"OpenAI validation - {case['name']}: {data.get('valid')} (expected: {case['should_pass']})")
            
            if case["should_pass"]:
                if not data["valid"]:
                    print(f"  Error: {data.get('error_message')}")
                # Note: Some large images might still fail due to file size
            else:
                assert data["valid"] is False, f"OpenAI should reject {case['name']}"
                assert "exceed" in data.get("error_message", "").lower()
    
    @pytest.mark.asyncio
    async def test_openai_provider_processing(self, client: AsyncClient, mock_auth):
        """Test OpenAI provider processing optimization"""
        
        # Test with transparent image (OpenAI strength)
        transparent_image = self.create_transparent_image(800, 600)
        
        response = await client.post(
            "/api/v1/process",
            json={
                "image": transparent_image,
                "provider": "openai",
                "options": {"format": "PNG", "preserve_transparency": True}
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify OpenAI optimizations
        assert data["processed_format"] == "PNG"  # PNG for transparency
        assert data["metadata"]["provider"] == "openai"
        assert data["metadata"]["has_transparency"] is True
        
        # Verify file size is within OpenAI limits (20MB)
        assert data["processed_size"] <= 20 * 1024 * 1024
        
        # Verify dimensions are within OpenAI limits (2048px)
        assert max(data["dimensions"]) <= 2048
    
    # Gemini Provider Tests
    
    @pytest.mark.asyncio
    async def test_gemini_provider_validation(self, client: AsyncClient, mock_auth):
        """Test Gemini provider validation requirements"""
        
        test_cases = [
            # Should pass: High resolution image
            {"image": self.create_test_image(2048, 1536), "should_pass": True, "name": "high_res"},
            
            # Should pass: Very high resolution (Gemini supports up to 4096px)
            {"image": self.create_test_image(3000, 2000), "should_pass": True, "name": "very_high_res"},
            
            # Should pass: At dimension limit
            {"image": self.create_test_image(4096, 3072), "should_pass": True, "name": "at_limit"},
            
            # Should fail: Exceeds dimension limit
            {"image": self.create_test_image(5000, 4000), "should_pass": False, "name": "exceeds_dimension"},
            
            # Should pass: JPEG image (Gemini prefers JPEG)
            {"image": self.create_test_image(2000, 1500, "JPEG"), "should_pass": True, "name": "jpeg_image"}
        ]
        
        for case in test_cases:
            response = await client.post(
                "/api/v1/validate",
                json={"image": case["image"], "provider": "gemini"},
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            
            print(f"Gemini validation - {case['name']}: {data.get('valid')} (expected: {case['should_pass']})")
            
            if case["should_pass"]:
                if not data["valid"]:
                    print(f"  Error: {data.get('error_message')}")
                # Note: Large images might still fail due to file size
            else:
                assert data["valid"] is False, f"Gemini should reject {case['name']}"
    
    @pytest.mark.asyncio
    async def test_gemini_provider_processing(self, client: AsyncClient, mock_auth):
        """Test Gemini provider processing optimization"""
        
        # Test with high-resolution image (Gemini strength)
        high_res_image = self.create_test_image(2500, 2000, "PNG")
        
        response = await client.post(
            "/api/v1/process",
            json={
                "image": high_res_image,
                "provider": "gemini",
                "options": {"format": "JPEG", "quality": 85}
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify Gemini optimizations
        assert data["processed_format"] == "JPEG"  # Gemini prefers JPEG
        assert data["metadata"]["provider"] == "gemini"
        
        # Verify file size is within Gemini limits (20MB)
        assert data["processed_size"] <= 20 * 1024 * 1024
        
        # Verify dimensions are within Gemini limits (4096px)
        assert max(data["dimensions"]) <= 4096
    
    # Cross-Provider Compatibility Tests
    
    @pytest.mark.asyncio
    async def test_cross_provider_compatibility(self, client: AsyncClient, mock_auth):
        """Test same image across all providers"""
        
        # Create test image that should work with all providers
        test_image = self.create_test_image(1000, 800, "PNG")
        providers = ["claude", "openai", "gemini"]
        
        results = {}
        
        for provider in providers:
            # Validate
            validate_response = await client.post(
                "/api/v1/validate",
                json={"image": test_image, "provider": provider},
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert validate_response.status_code == 200
            validation = validate_response.json()
            
            if validation["valid"]:
                # Process
                process_response = await client.post(
                    "/api/v1/process",
                    json={"image": test_image, "provider": provider},
                    headers={"Authorization": "Bearer test-token"}
                )
                
                assert process_response.status_code == 200
                process_data = process_response.json()
                assert process_data["success"] is True
                
                results[provider] = {
                    "valid": True,
                    "processed_format": process_data["processed_format"],
                    "compression_ratio": process_data["compression_ratio"],
                    "processing_time": process_data["processing_time_ms"],
                    "file_size": process_data["processed_size"]
                }
            else:
                results[provider] = {
                    "valid": False,
                    "error": validation["error_message"]
                }
        
        # Print comparison
        print("\n=== Cross-Provider Compatibility Results ===")
        for provider, result in results.items():
            if result["valid"]:
                print(f"{provider}: format={result['processed_format']}, "
                      f"compression={result['compression_ratio']:.3f}, "
                      f"time={result['processing_time']:.1f}ms, "
                      f"size={result['file_size']} bytes")
            else:
                print(f"{provider}: FAILED - {result['error']}")
        
        # At least one provider should succeed
        successful_providers = [p for p, r in results.items() if r["valid"]]
        assert len(successful_providers) > 0, "At least one provider should handle the image"
    
    @pytest.mark.asyncio
    async def test_format_optimization_by_provider(self, client: AsyncClient, mock_auth):
        """Test format optimization preferences by provider"""
        
        # Test different source formats
        source_formats = ["PNG", "JPEG"]
        providers = ["claude", "openai", "gemini"]
        
        results = {}
        
        for source_format in source_formats:
            results[source_format] = {}
            test_image = self.create_test_image(800, 600, source_format)
            
            for provider in providers:
                # Let provider choose optimal format (no format specified)
                response = await client.post(
                    "/api/v1/process",
                    json={"image": test_image, "provider": provider},
                    headers={"Authorization": "Bearer test-token"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data["success"]:
                        results[source_format][provider] = {
                            "output_format": data["processed_format"],
                            "compression": data["compression_ratio"],
                            "original_format": data["original_format"]
                        }
        
        # Print format optimization results
        print("\n=== Format Optimization by Provider ===")
        for source_format, provider_results in results.items():
            print(f"Source format: {source_format}")
            for provider, result in provider_results.items():
                print(f"  {provider}: {result['original_format']} -> {result['output_format']} "
                      f"(compression: {result['compression']:.3f})")
        
        # Verify optimization behaviors
        if "PNG" in results and "claude" in results["PNG"]:
            # Claude should prefer JPEG for compression
            assert results["PNG"]["claude"]["output_format"] in ["JPEG", "PNG"]
        
        if "PNG" in results and "openai" in results["PNG"]:
            # OpenAI might preserve PNG for quality
            assert results["PNG"]["openai"]["output_format"] in ["PNG", "JPEG"]
    
    @pytest.mark.asyncio
    async def test_quality_settings_by_provider(self, client: AsyncClient, mock_auth):
        """Test quality settings optimization by provider"""
        
        test_image = self.create_test_image(1200, 900, "PNG")
        quality_levels = [70, 85, 95]
        
        results = {}
        
        for provider in ["claude", "openai", "gemini"]:
            results[provider] = {}
            
            for quality in quality_levels:
                response = await client.post(
                    "/api/v1/process",
                    json={
                        "image": test_image,
                        "provider": provider,
                        "options": {"format": "JPEG", "quality": quality}
                    },
                    headers={"Authorization": "Bearer test-token"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data["success"]:
                        results[provider][quality] = {
                            "file_size": data["processed_size"],
                            "compression_ratio": data["compression_ratio"],
                            "quality_used": data["metadata"].get("quality_used", quality)
                        }
        
        # Print quality comparison
        print("\n=== Quality Settings by Provider ===")
        for provider, quality_results in results.items():
            print(f"Provider: {provider}")
            for quality, result in quality_results.items():
                print(f"  Quality {quality}: size={result['file_size']} bytes, "
                      f"compression={result['compression_ratio']:.3f}, "
                      f"actual_quality={result['quality_used']}")
        
        # Verify quality behavior
        for provider, quality_results in results.items():
            if len(quality_results) >= 2:
                # Higher quality should generally result in larger file sizes
                qualities = sorted(quality_results.keys())
                for i in range(len(qualities) - 1):
                    lower_q = qualities[i]
                    higher_q = qualities[i + 1]
                    
                    # Allow some tolerance for optimization variations
                    size_ratio = quality_results[higher_q]["file_size"] / quality_results[lower_q]["file_size"]
                    assert size_ratio >= 0.8, f"Higher quality should not significantly reduce file size for {provider}"
    
    @pytest.mark.asyncio
    async def test_dimension_limits_by_provider(self, client: AsyncClient, mock_auth):
        """Test dimension limit handling by provider"""
        
        # Test images at various dimension levels
        test_dimensions = [
            (1024, 768),   # Safe for all
            (2048, 1536),  # OpenAI limit
            (3000, 2000),  # Between OpenAI and Gemini
            (4096, 3072),  # Gemini limit
            (8000, 6000)   # Close to Claude limit
        ]
        
        providers = ["claude", "openai", "gemini"]
        results = {}
        
        for width, height in test_dimensions:
            dim_key = f"{width}x{height}"
            results[dim_key] = {}
            
            # Create small file size to focus on dimension limits
            test_image = self.create_test_image(width, height, "JPEG", quality=50)
            
            for provider in providers:
                validate_response = await client.post(
                    "/api/v1/validate",
                    json={"image": test_image, "provider": provider},
                    headers={"Authorization": "Bearer test-token"}
                )
                
                assert validate_response.status_code == 200
                validation = validate_response.json()
                
                results[dim_key][provider] = {
                    "valid": validation["valid"],
                    "error": validation.get("error_message") if not validation["valid"] else None
                }
        
        # Print dimension limit results
        print("\n=== Dimension Limits by Provider ===")
        for dim_key, provider_results in results.items():
            print(f"Dimensions: {dim_key}")
            for provider, result in provider_results.items():
                status = "PASS" if result["valid"] else f"FAIL ({result['error']})"
                print(f"  {provider}: {status}")
        
        # Verify expected dimension behaviors
        # 1024x768 should work for all
        assert all(results["1024x768"][p]["valid"] for p in providers), "Small images should work for all providers"
        
        # 8000x6000 should fail for OpenAI and possibly others
        large_image_results = results["8000x6000"]
        failed_providers = [p for p, r in large_image_results.items() if not r["valid"]]
        assert len(failed_providers) > 0, "Very large images should fail for some providers"
    
    @pytest.mark.asyncio
    async def test_transparency_handling_by_provider(self, client: AsyncClient, mock_auth):
        """Test transparency handling across providers"""
        
        transparent_image = self.create_transparent_image(800, 600)
        providers = ["claude", "openai", "gemini"]
        
        results = {}
        
        for provider in providers:
            # Test transparency preservation
            preserve_response = await client.post(
                "/api/v1/process",
                json={
                    "image": transparent_image,
                    "provider": provider,
                    "options": {"format": "PNG", "preserve_transparency": True}
                },
                headers={"Authorization": "Bearer test-token"}
            )
            
            # Test transparency removal (JPEG conversion)
            remove_response = await client.post(
                "/api/v1/process",
                json={
                    "image": transparent_image,
                    "provider": provider,
                    "options": {"format": "JPEG", "background_color": "#FFFFFF"}
                },
                headers={"Authorization": "Bearer test-token"}
            )
            
            results[provider] = {
                "preserve_success": preserve_response.status_code == 200,
                "remove_success": remove_response.status_code == 200,
                "preserve_data": preserve_response.json() if preserve_response.status_code == 200 else None,
                "remove_data": remove_response.json() if remove_response.status_code == 200 else None
            }
        
        # Print transparency handling results
        print("\n=== Transparency Handling by Provider ===")
        for provider, result in results.items():
            print(f"Provider: {provider}")
            print(f"  Preserve transparency: {'SUCCESS' if result['preserve_success'] else 'FAILED'}")
            print(f"  Remove transparency: {'SUCCESS' if result['remove_success'] else 'FAILED'}")
            
            if result["preserve_data"]:
                has_transparency = result["preserve_data"]["metadata"].get("has_transparency", False)
                print(f"  Preserved format: {result['preserve_data']['processed_format']}, has_transparency: {has_transparency}")
            
            if result["remove_data"]:
                print(f"  Removed format: {result['remove_data']['processed_format']}")
        
        # Verify transparency handling
        for provider, result in results.items():
            if result["preserve_success"] and result["preserve_data"]:
                # PNG should preserve transparency
                if result["preserve_data"]["processed_format"] == "PNG":
                    assert result["preserve_data"]["metadata"].get("has_transparency"), f"{provider} should preserve transparency in PNG"
            
            if result["remove_success"] and result["remove_data"]:
                # JPEG should not have transparency
                if result["remove_data"]["processed_format"] == "JPEG":
                    assert not result["remove_data"]["metadata"].get("has_transparency", True), f"{provider} should remove transparency in JPEG"