"""
Core image processing service extracted from existing codebase
Handles image validation, processing, and optimization for AI providers
"""
import base64
import io
import time
import hashlib
from typing import Dict, Any, Tuple, Optional, List
from dataclasses import dataclass
from PIL import Image, ImageOps
import imagehash
from shared.monitoring.structured_logger import StructuredLogger
from shared.security.data_protection import SecureDataHandler
from shared.monitoring.correlation import get_correlation_id

@dataclass
class ImageProcessingResult:
    """Result of image processing operation"""
    processed_image: str  # Base64 encoded
    original_format: str
    processed_format: str
    original_size: int
    processed_size: int
    dimensions: Tuple[int, int]
    processing_time_ms: float
    compression_ratio: float
    metadata: Dict[str, Any]

@dataclass
class ImageValidationResult:
    """Result of image validation"""
    is_valid: bool
    error_message: Optional[str]
    file_size: int
    dimensions: Tuple[int, int]
    format: str
    has_transparency: bool
    color_mode: str

class ImageProcessor:
    """Enhanced image processing service extracted from existing code"""
    
    # Provider-specific image requirements
    PROVIDER_REQUIREMENTS = {
        'claude': {
            'max_size': 5 * 1024 * 1024,  # 5MB
            'max_dimension': 7990,  # pixels
            'supported_formats': ['JPEG', 'PNG', 'GIF', 'WEBP'],
            'preferred_format': 'JPEG'
        },
        'openai': {
            'max_size': 20 * 1024 * 1024,  # 20MB
            'max_dimension': 2048,  # pixels
            'supported_formats': ['JPEG', 'PNG', 'GIF', 'WEBP'],
            'preferred_format': 'PNG'
        },
        'gemini': {
            'max_size': 20 * 1024 * 1024,  # 20MB
            'max_dimension': 4096,  # pixels
            'supported_formats': ['JPEG', 'PNG', 'GIF', 'WEBP'],
            'preferred_format': 'JPEG'
        }
    }
    
    def __init__(self):
        self.logger = StructuredLogger("image-processor")
        self.data_handler = SecureDataHandler()
    
    async def validate_image(self, image_data_url: str, provider: str = 'claude') -> ImageValidationResult:
        """
        Validate image against provider requirements
        
        Args:
            image_data_url: Base64 data URL of the image
            provider: Target AI provider ('claude', 'openai', 'gemini')
            
        Returns:
            ImageValidationResult with validation status and details
        """
        
        correlation_id = get_correlation_id()
        start_time = time.time()
        
        try:
            # Parse data URL
            if not image_data_url.startswith('data:image/'):
                return ImageValidationResult(
                    is_valid=False,
                    error_message="Invalid image data URL format",
                    file_size=0,
                    dimensions=(0, 0),
                    format="unknown",
                    has_transparency=False,
                    color_mode="unknown"
                )
            
            # Extract media type and data
            header, data = image_data_url.split(',', 1)
            media_type = header.split(';')[0].split(':')[1]
            
            # Decode base64
            image_bytes = base64.b64decode(data)
            file_size = len(image_bytes)
            
            # Get provider requirements
            requirements = self.PROVIDER_REQUIREMENTS.get(provider, self.PROVIDER_REQUIREMENTS['claude'])
            
            # Check file size
            if file_size > requirements['max_size']:
                return ImageValidationResult(
                    is_valid=False,
                    error_message=f"Image size {file_size} exceeds {provider} limit of {requirements['max_size']} bytes",
                    file_size=file_size,
                    dimensions=(0, 0),
                    format="unknown",
                    has_transparency=False,
                    color_mode="unknown"
                )
            
            # Validate with PIL
            with Image.open(io.BytesIO(image_bytes)) as img:
                # Check dimensions
                if (img.width > requirements['max_dimension'] or 
                    img.height > requirements['max_dimension']):
                    return ImageValidationResult(
                        is_valid=False,
                        error_message=f"Image dimensions {img.width}x{img.height} exceed {provider} limit of {requirements['max_dimension']}px",
                        file_size=file_size,
                        dimensions=(img.width, img.height),
                        format=img.format,
                        has_transparency=img.mode in ('RGBA', 'LA') or 'transparency' in img.info,
                        color_mode=img.mode
                    )
                
                # Check format support
                if img.format not in requirements['supported_formats']:
                    return ImageValidationResult(
                        is_valid=False,
                        error_message=f"Image format {img.format} not supported by {provider}",
                        file_size=file_size,
                        dimensions=(img.width, img.height),
                        format=img.format,
                        has_transparency=img.mode in ('RGBA', 'LA') or 'transparency' in img.info,
                        color_mode=img.mode
                    )
                
                # Log validation success
                processing_time = (time.time() - start_time) * 1000
                self.logger.log_image_processing(
                    operation="validation",
                    input_size=file_size,
                    output_size=file_size,
                    duration_ms=processing_time,
                    correlation_id=correlation_id
                )
                
                return ImageValidationResult(
                    is_valid=True,
                    error_message=None,
                    file_size=file_size,
                    dimensions=(img.width, img.height),
                    format=img.format,
                    has_transparency=img.mode in ('RGBA', 'LA') or 'transparency' in img.info,
                    color_mode=img.mode
                )
                
        except Exception as e:
            self.logger.log_error(
                error=e,
                context={
                    "operation": "image_validation",
                    "provider": provider
                },
                correlation_id=correlation_id
            )
            
            return ImageValidationResult(
                is_valid=False,
                error_message=f"Image validation failed: {str(e)}",
                file_size=0,
                dimensions=(0, 0),
                format="unknown",
                has_transparency=False,
                color_mode="unknown"
            )
    
    async def process_image(self, image_data_url: str, provider: str = 'claude', 
                          options: Dict[str, Any] = None) -> ImageProcessingResult:
        """
        Process image for AI provider requirements
        Enhanced version of the existing process_image function
        
        Args:
            image_data_url: Base64 data URL of the image
            provider: Target AI provider
            options: Processing options (quality, format, etc.)
            
        Returns:
            ImageProcessingResult with processed image and metadata
        """
        
        correlation_id = get_correlation_id()
        start_time = time.time()
        options = options or {}
        
        try:
            # First validate the image
            validation_result = await self.validate_image(image_data_url, provider)
            if not validation_result.is_valid:
                raise ValueError(validation_result.error_message)
            
            # Extract image data
            header, data = image_data_url.split(',', 1)
            original_media_type = header.split(';')[0].split(':')[1]
            image_bytes = base64.b64decode(data)
            original_size = len(image_bytes)
            
            # Get provider requirements
            requirements = self.PROVIDER_REQUIREMENTS.get(provider, self.PROVIDER_REQUIREMENTS['claude'])
            
            # Load image
            with Image.open(io.BytesIO(image_bytes)) as img:
                original_format = img.format
                original_dimensions = (img.width, img.height)
                
                # Create a copy for processing
                processed_img = img.copy()
                
                # Auto-orient image based on EXIF data
                processed_img = ImageOps.exif_transpose(processed_img)
                
                # Resize if needed
                if (processed_img.width > requirements['max_dimension'] or 
                    processed_img.height > requirements['max_dimension']):
                    
                    # Calculate new dimensions maintaining aspect ratio
                    ratio = min(
                        requirements['max_dimension'] / processed_img.width,
                        requirements['max_dimension'] / processed_img.height
                    )
                    
                    new_width = int(processed_img.width * ratio)
                    new_height = int(processed_img.height * ratio)
                    
                    # Use high-quality resampling
                    processed_img = processed_img.resize(
                        (new_width, new_height), 
                        Image.Resampling.LANCZOS
                    )
                    
                    self.logger.logger.info(
                        "Image resized for provider requirements",
                        extra={
                            "original_dimensions": original_dimensions,
                            "new_dimensions": (new_width, new_height),
                            "provider": provider,
                            "correlation_id": correlation_id
                        }
                    )
                
                # Convert to preferred format if needed
                target_format = options.get('format', requirements['preferred_format'])
                quality = options.get('quality', 95)
                
                # Handle transparency for JPEG conversion
                if target_format == 'JPEG' and processed_img.mode in ('RGBA', 'LA'):
                    # Create white background for transparent images
                    background = Image.new('RGB', processed_img.size, (255, 255, 255))
                    if processed_img.mode == 'RGBA':
                        background.paste(processed_img, mask=processed_img.split()[-1])
                    else:
                        background.paste(processed_img)
                    processed_img = background
                elif target_format == 'JPEG' and processed_img.mode != 'RGB':
                    processed_img = processed_img.convert('RGB')
                
                # Save processed image
                output = io.BytesIO()
                
                if target_format == 'JPEG':
                    processed_img.save(
                        output, 
                        format='JPEG', 
                        quality=quality,
                        optimize=True,
                        progressive=True
                    )
                elif target_format == 'PNG':
                    processed_img.save(
                        output, 
                        format='PNG', 
                        optimize=True
                    )
                else:
                    processed_img.save(output, format=target_format, optimize=True)
                
                processed_bytes = output.getvalue()
                processed_size = len(processed_bytes)
                
                # Check if processed image meets size requirements
                if processed_size > requirements['max_size']:
                    # Further compress if still too large
                    quality = 85
                    while processed_size > requirements['max_size'] and quality > 10:
                        output = io.BytesIO()
                        processed_img.save(
                            output, 
                            format='JPEG', 
                            quality=quality
                        )
                        processed_bytes = output.getvalue()
                        processed_size = len(processed_bytes)
                        quality -= 10
                
                # Encode back to base64
                processed_base64 = base64.b64encode(processed_bytes).decode('utf-8')
                processed_data_url = f"data:image/{target_format.lower()};base64,{processed_base64}"
                
                # Calculate metrics
                processing_time = (time.time() - start_time) * 1000
                compression_ratio = processed_size / original_size if original_size > 0 else 1.0
                
                # Generate image hash for deduplication
                img_hash = str(imagehash.average_hash(processed_img))
                
                # Create metadata
                metadata = {
                    "provider": provider,
                    "processing_options": options,
                    "original_format": original_format,
                    "target_format": target_format,
                    "resized": original_dimensions != processed_img.size,
                    "quality_used": quality,
                    "image_hash": img_hash,
                    "has_transparency": validation_result.has_transparency,
                    "color_mode": validation_result.color_mode
                }
                
                # Log processing metrics
                self.logger.log_image_processing(
                    operation="processing",
                    input_size=original_size,
                    output_size=processed_size,
                    duration_ms=processing_time,
                    correlation_id=correlation_id
                )
                
                return ImageProcessingResult(
                    processed_image=processed_data_url,
                    original_format=original_format,
                    processed_format=target_format,
                    original_size=original_size,
                    processed_size=processed_size,
                    dimensions=processed_img.size,
                    processing_time_ms=processing_time,
                    compression_ratio=compression_ratio,
                    metadata=metadata
                )
                
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            
            self.logger.log_error(
                error=e,
                context={
                    "operation": "image_processing",
                    "provider": provider,
                    "processing_time_ms": processing_time
                },
                correlation_id=correlation_id
            )
            
            raise
    
    async def analyze_image_content(self, image_data_url: str) -> Dict[str, Any]:
        """
        Analyze image content for metadata and characteristics
        
        Args:
            image_data_url: Base64 data URL of the image
            
        Returns:
            Dictionary with image analysis results
        """
        
        correlation_id = get_correlation_id()
        start_time = time.time()
        
        try:
            # Extract image data
            header, data = image_data_url.split(',', 1)
            image_bytes = base64.b64decode(data)
            
            with Image.open(io.BytesIO(image_bytes)) as img:
                # Basic analysis
                analysis = {
                    "dimensions": {
                        "width": img.width,
                        "height": img.height,
                        "aspect_ratio": round(img.width / img.height, 2)
                    },
                    "format": img.format,
                    "mode": img.mode,
                    "size_bytes": len(image_bytes),
                    "has_transparency": img.mode in ('RGBA', 'LA') or 'transparency' in img.info,
                    "has_animation": getattr(img, 'is_animated', False),
                    "image_hash": str(imagehash.average_hash(img))
                }
                
                # Color analysis
                if img.mode in ('RGB', 'RGBA'):
                    colors = img.getcolors(maxcolors=256*256*256)
                    if colors:
                        analysis["dominant_colors"] = len(colors)
                        analysis["is_grayscale"] = len(set(c[1][:3] for c in colors[:10])) == 1
                
                # EXIF data if available
                if hasattr(img, '_getexif') and img._getexif():
                    exif_data = img._getexif()
                    analysis["has_exif"] = True
                    analysis["exif_orientation"] = exif_data.get(274, 1)  # Orientation tag
                else:
                    analysis["has_exif"] = False
                
                # Estimate content complexity
                try:
                    # Convert to grayscale for edge detection
                    gray_img = img.convert('L')
                    # Simple edge detection using histogram variation
                    histogram = gray_img.histogram()
                    variance = sum((i - 128) ** 2 * v for i, v in enumerate(histogram)) / sum(histogram)
                    analysis["complexity_score"] = min(variance / 1000, 10)  # Normalize to 0-10
                except:
                    analysis["complexity_score"] = 5  # Default value
                
                # Processing time
                processing_time = (time.time() - start_time) * 1000
                analysis["analysis_time_ms"] = processing_time
                
                # Log analysis
                self.logger.log_business_metric(
                    metric_name="image_analyzed",
                    value=1,
                    dimensions={
                        "format": img.format,
                        "has_transparency": str(analysis["has_transparency"]),
                        "complexity": "high" if analysis["complexity_score"] > 7 else "medium" if analysis["complexity_score"] > 3 else "low"
                    },
                    correlation_id=correlation_id
                )
                
                return analysis
                
        except Exception as e:
            self.logger.log_error(
                error=e,
                context={"operation": "image_analysis"},
                correlation_id=correlation_id
            )
            
            return {
                "error": str(e),
                "analysis_time_ms": (time.time() - start_time) * 1000
            }
    
    async def create_thumbnail(self, image_data_url: str, size: Tuple[int, int] = (150, 150)) -> str:
        """
        Create thumbnail version of image
        
        Args:
            image_data_url: Base64 data URL of the image
            size: Thumbnail size (width, height)
            
        Returns:
            Base64 data URL of thumbnail
        """
        
        correlation_id = get_correlation_id()
        
        try:
            # Extract image data
            header, data = image_data_url.split(',', 1)
            image_bytes = base64.b64decode(data)
            
            with Image.open(io.BytesIO(image_bytes)) as img:
                # Create thumbnail maintaining aspect ratio
                img.thumbnail(size, Image.Resampling.LANCZOS)
                
                # Convert to RGB if needed for JPEG
                if img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'RGBA':
                        background.paste(img, mask=img.split()[-1])
                    else:
                        background.paste(img)
                    img = background
                
                # Save as JPEG
                output = io.BytesIO()
                img.save(output, format='JPEG', quality=85, optimize=True)
                
                # Encode to base64
                thumbnail_bytes = output.getvalue()
                thumbnail_base64 = base64.b64encode(thumbnail_bytes).decode('utf-8')
                
                self.logger.log_image_processing(
                    operation="thumbnail",
                    input_size=len(image_bytes),
                    output_size=len(thumbnail_bytes),
                    duration_ms=0,  # Quick operation
                    correlation_id=correlation_id
                )
                
                return f"data:image/jpeg;base64,{thumbnail_base64}"
                
        except Exception as e:
            self.logger.log_error(
                error=e,
                context={"operation": "thumbnail_creation"},
                correlation_id=correlation_id
            )
            
            raise
    
    def get_supported_providers(self) -> List[str]:
        """Get list of supported AI providers"""
        return list(self.PROVIDER_REQUIREMENTS.keys())
    
    def get_provider_requirements(self, provider: str) -> Dict[str, Any]:
        """Get requirements for specific provider"""
        return self.PROVIDER_REQUIREMENTS.get(provider, {}).copy()