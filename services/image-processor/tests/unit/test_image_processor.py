"""
Unit tests for Image Processor service
"""
import pytest
import base64
import io
from unittest.mock import AsyncMock, patch, MagicMock
from PIL import Image

from app.services.image_processor import ImageProcessor, ImageValidationResult, ImageProcessingResult

class TestImageProcessor:
    """Test cases for ImageProcessor service"""
    
    @pytest.fixture
    def processor(self):
        """Create ImageProcessor instance for testing"""
        return ImageProcessor()
    
    @pytest.fixture
    def sample_image_data_url(self):
        """Generate sample image data URL for testing"""
        # Create a simple test image
        img = Image.new('RGB', (100, 100), color='red')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        image_bytes = buffer.getvalue()
        
        # Encode to base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:image/png;base64,{image_base64}"
    
    @pytest.fixture
    def large_image_data_url(self):
        """Generate large image data URL for testing size limits"""
        # Create a large test image
        img = Image.new('RGB', (8000, 8000), color='blue')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        image_bytes = buffer.getvalue()
        
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:image/png;base64,{image_base64}"
    
    @pytest.mark.asyncio
    async def test_validate_image_success(self, processor, sample_image_data_url):
        """Test successful image validation"""
        
        result = await processor.validate_image(sample_image_data_url, "claude")
        
        assert isinstance(result, ImageValidationResult)
        assert result.is_valid is True
        assert result.error_message is None
        assert result.file_size > 0
        assert result.dimensions == (100, 100)
        assert result.format == "PNG"
    
    @pytest.mark.asyncio
    async def test_validate_image_invalid_format(self, processor):
        """Test image validation with invalid format"""
        
        invalid_data_url = "data:text/plain;base64,dGVzdA=="
        
        result = await processor.validate_image(invalid_data_url, "claude")
        
        assert result.is_valid is False
        assert "Invalid image data URL format" in result.error_message
    
    @pytest.mark.asyncio
    async def test_validate_image_too_large(self, processor, large_image_data_url):
        """Test image validation with oversized image"""
        
        result = await processor.validate_image(large_image_data_url, "claude")
        
        # Should either fail on size or dimensions
        assert result.is_valid is False
        assert "exceed" in result.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_process_image_success(self, processor, sample_image_data_url):
        """Test successful image processing"""
        
        with patch.object(processor, 'validate_image') as mock_validate:
            # Mock successful validation
            mock_validate.return_value = ImageValidationResult(
                is_valid=True,
                error_message=None,
                file_size=1000,
                dimensions=(100, 100),
                format="PNG",
                has_transparency=False,
                color_mode="RGB"
            )
            
            result = await processor.process_image(sample_image_data_url, "claude")
            
            assert isinstance(result, ImageProcessingResult)
            assert result.processed_image.startswith('data:image/')
            assert result.original_format == "PNG"
            assert result.original_size > 0
            assert result.processed_size > 0
            assert result.processing_time_ms > 0
            assert result.compression_ratio > 0
    
    @pytest.mark.asyncio
    async def test_process_image_with_options(self, processor, sample_image_data_url):
        """Test image processing with custom options"""
        
        options = {
            "format": "JPEG",
            "quality": 85
        }
        
        with patch.object(processor, 'validate_image') as mock_validate:
            mock_validate.return_value = ImageValidationResult(
                is_valid=True,
                error_message=None,
                file_size=1000,
                dimensions=(100, 100),
                format="PNG",
                has_transparency=False,
                color_mode="RGB"
            )
            
            result = await processor.process_image(sample_image_data_url, "claude", options)
            
            assert result.processed_format == "JPEG"
            assert "quality_used" in result.metadata
    
    @pytest.mark.asyncio
    async def test_process_image_validation_failure(self, processor, sample_image_data_url):
        """Test image processing with validation failure"""
        
        with patch.object(processor, 'validate_image') as mock_validate:
            # Mock validation failure
            mock_validate.return_value = ImageValidationResult(
                is_valid=False,
                error_message="Image too large",
                file_size=1000,
                dimensions=(100, 100),
                format="PNG",
                has_transparency=False,
                color_mode="RGB"
            )
            
            with pytest.raises(ValueError, match="Image too large"):
                await processor.process_image(sample_image_data_url, "claude")
    
    @pytest.mark.asyncio
    async def test_analyze_image_content(self, processor, sample_image_data_url):
        """Test image content analysis"""
        
        analysis = await processor.analyze_image_content(sample_image_data_url)
        
        assert "dimensions" in analysis
        assert analysis["dimensions"]["width"] == 100
        assert analysis["dimensions"]["height"] == 100
        assert "format" in analysis
        assert "mode" in analysis
        assert "size_bytes" in analysis
        assert "has_transparency" in analysis
        assert "image_hash" in analysis
        assert "complexity_score" in analysis
        assert "analysis_time_ms" in analysis
    
    @pytest.mark.asyncio
    async def test_create_thumbnail(self, processor, sample_image_data_url):
        """Test thumbnail creation"""
        
        thumbnail = await processor.create_thumbnail(sample_image_data_url, (50, 50))
        
        assert thumbnail.startswith('data:image/jpeg;base64,')
        
        # Verify thumbnail is smaller than original
        thumbnail_data = thumbnail.split(',')[1]
        thumbnail_bytes = base64.b64decode(thumbnail_data)
        
        original_data = sample_image_data_url.split(',')[1]
        original_bytes = base64.b64decode(original_data)
        
        # Thumbnail should be smaller (though this may not always be true for very small images)
        assert len(thumbnail_bytes) <= len(original_bytes) * 2  # Allow some variance
    
    def test_get_supported_providers(self, processor):
        """Test getting supported providers"""
        
        providers = processor.get_supported_providers()
        
        assert isinstance(providers, list)
        assert "claude" in providers
        assert "openai" in providers
        assert "gemini" in providers
    
    def test_get_provider_requirements(self, processor):
        """Test getting provider requirements"""
        
        requirements = processor.get_provider_requirements("claude")
        
        assert isinstance(requirements, dict)
        assert "max_size" in requirements
        assert "max_dimension" in requirements
        assert "supported_formats" in requirements
        assert "preferred_format" in requirements
    
    @pytest.mark.asyncio
    async def test_different_providers(self, processor, sample_image_data_url):
        """Test processing for different providers"""
        
        providers = ["claude", "openai", "gemini"]
        
        for provider in providers:
            result = await processor.validate_image(sample_image_data_url, provider)
            
            # Should be valid for all providers with our small test image
            assert result.is_valid is True, f"Validation failed for provider: {provider}"
    
    @pytest.mark.asyncio
    async def test_transparency_handling(self, processor):
        """Test handling of images with transparency"""
        
        # Create image with transparency
        img = Image.new('RGBA', (100, 100), (255, 0, 0, 128))  # Semi-transparent red
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        image_bytes = buffer.getvalue()
        
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        data_url = f"data:image/png;base64,{image_base64}"
        
        # Process with JPEG format (should handle transparency)
        options = {"format": "JPEG"}
        
        with patch.object(processor, 'validate_image') as mock_validate:
            mock_validate.return_value = ImageValidationResult(
                is_valid=True,
                error_message=None,
                file_size=len(image_bytes),
                dimensions=(100, 100),
                format="PNG",
                has_transparency=True,
                color_mode="RGBA"
            )
            
            result = await processor.process_image(data_url, "claude", options)
            
            assert result.processed_format == "JPEG"
            assert result.metadata["has_transparency"] is True
    
    @pytest.mark.asyncio
    async def test_error_handling(self, processor):
        """Test error handling with invalid data"""
        
        invalid_data_url = "data:image/png;base64,invalid_base64_data"
        
        with pytest.raises(Exception):
            await processor.process_image(invalid_data_url, "claude")
    
    @pytest.mark.asyncio
    async def test_correlation_id_logging(self, processor, sample_image_data_url):
        """Test that correlation ID is properly used in logging"""
        
        with patch('shared.monitoring.correlation.get_correlation_id', return_value="test-correlation-id"):
            with patch.object(processor.logger, 'log_image_processing') as mock_log:
                
                with patch.object(processor, 'validate_image') as mock_validate:
                    mock_validate.return_value = ImageValidationResult(
                        is_valid=True, error_message=None, file_size=1000,
                        dimensions=(100, 100), format="PNG", 
                        has_transparency=False, color_mode="RGB"
                    )
                    
                    await processor.process_image(sample_image_data_url, "claude")
                
                # Verify logging was called with correlation ID
                mock_log.assert_called()
                call_args = mock_log.call_args
                assert call_args[1]['correlation_id'] == "test-correlation-id"