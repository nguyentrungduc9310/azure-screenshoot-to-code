"""
Image processing API routes
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, validator

from shared.auth.azure_ad import get_current_user, require_role
from shared.security.input_validation import SecurityValidator
from shared.monitoring.correlation import get_correlation_id
from app.services.image_processor import ImageProcessor, ImageProcessingResult, ImageValidationResult

router = APIRouter()

# Initialize image processor
image_processor = ImageProcessor()


class ImageProcessingRequest(BaseModel):
    """Request model for image processing"""
    image: str
    provider: str = "claude"
    options: Dict[str, Any] = {}
    
    @validator('image')
    def validate_image(cls, v):
        """Validate image data URL"""
        if not v.startswith('data:image/'):
            raise ValueError("Invalid image data URL format")
        return v
    
    @validator('provider')
    def validate_provider(cls, v):
        """Validate AI provider"""
        supported_providers = ['claude', 'openai', 'gemini']
        if v.lower() not in supported_providers:
            raise ValueError(f"Provider must be one of: {supported_providers}")
        return v.lower()
    
    @validator('options')
    def sanitize_options(cls, v):
        """Sanitize options dictionary"""
        if not isinstance(v, dict):
            return {}
        
        # Sanitize option values
        sanitized_options = {}
        for key, value in v.items():
            if isinstance(value, str):
                sanitized_options[key] = SecurityValidator.sanitize_string(value)
            else:
                sanitized_options[key] = value
        
        return sanitized_options


class ImageValidationRequest(BaseModel):
    """Request model for image validation"""
    image: str
    provider: str = "claude"
    
    @validator('image')
    def validate_image(cls, v):
        if not v.startswith('data:image/'):
            raise ValueError("Invalid image data URL format")
        return v
    
    @validator('provider')
    def validate_provider(cls, v):
        supported_providers = ['claude', 'openai', 'gemini']
        if v.lower() not in supported_providers:
            raise ValueError(f"Provider must be one of: {supported_providers}")
        return v.lower()


class ImageAnalysisRequest(BaseModel):
    """Request model for image analysis"""
    image: str
    
    @validator('image')
    def validate_image(cls, v):
        if not v.startswith('data:image/'):
            raise ValueError("Invalid image data URL format")
        return v


class ThumbnailRequest(BaseModel):
    """Request model for thumbnail creation"""
    image: str
    width: int = 150
    height: int = 150
    
    @validator('image')
    def validate_image(cls, v):
        if not v.startswith('data:image/'):
            raise ValueError("Invalid image data URL format")
        return v
    
    @validator('width', 'height')
    def validate_dimensions(cls, v):
        if v < 10 or v > 500:
            raise ValueError("Dimensions must be between 10 and 500 pixels")
        return v


class ImageProcessingResponse(BaseModel):
    """Response model for image processing"""
    success: bool
    processed_image: Optional[str] = None
    original_format: Optional[str] = None
    processed_format: Optional[str] = None
    original_size: Optional[int] = None
    processed_size: Optional[int] = None
    dimensions: Optional[List[int]] = None
    processing_time_ms: Optional[float] = None
    compression_ratio: Optional[float] = None
    metadata: Dict[str, Any] = {}
    correlation_id: Optional[str] = None


@router.post("/process", response_model=ImageProcessingResponse)
async def process_image(
    request: ImageProcessingRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict = Depends(get_current_user)
):
    """
    Process image for AI provider requirements
    
    This endpoint processes images to meet specific AI provider requirements including:
    - Size optimization and compression
    - Format conversion
    - Dimension adjustment
    - Quality optimization
    """
    
    correlation_id = get_correlation_id()
    
    try:
        # Process the image
        result = await image_processor.process_image(
            image_data_url=request.image,
            provider=request.provider,
            options=request.options
        )
        
        # Log successful processing in background
        background_tasks.add_task(
            log_image_processing_success,
            user_id=current_user.get("id"),
            provider=request.provider,
            original_size=result.original_size,
            processed_size=result.processed_size,
            processing_time=result.processing_time_ms
        )
        
        return ImageProcessingResponse(
            success=True,
            processed_image=result.processed_image,
            original_format=result.original_format,
            processed_format=result.processed_format,
            original_size=result.original_size,
            processed_size=result.processed_size,
            dimensions=[result.dimensions[0], result.dimensions[1]],
            processing_time_ms=result.processing_time_ms,
            compression_ratio=result.compression_ratio,
            metadata=result.metadata,
            correlation_id=correlation_id
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Image processing failed: {str(e)}"
        )


@router.post("/validate")
async def validate_image(
    request: ImageValidationRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    Validate image against AI provider requirements
    
    Checks if image meets provider-specific requirements without processing:
    - File size limits
    - Dimension limits  
    - Format support
    - Content validation
    """
    
    try:
        result = await image_processor.validate_image(
            image_data_url=request.image,
            provider=request.provider
        )
        
        return {
            "valid": result.is_valid,
            "error_message": result.error_message,
            "file_size": result.file_size,
            "dimensions": {
                "width": result.dimensions[0],
                "height": result.dimensions[1]
            },
            "format": result.format,
            "has_transparency": result.has_transparency,
            "color_mode": result.color_mode,
            "provider": request.provider
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Image validation failed: {str(e)}"
        )


@router.post("/analyze")
async def analyze_image(
    request: ImageAnalysisRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    Analyze image content and characteristics
    
    Provides detailed analysis including:
    - Image dimensions and format
    - Color information
    - Complexity analysis
    - EXIF data
    - Content characteristics
    """
    
    try:
        analysis = await image_processor.analyze_image_content(request.image)
        
        return {
            "success": True,
            "analysis": analysis,
            "correlation_id": get_correlation_id()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Image analysis failed: {str(e)}"
        )


@router.post("/thumbnail")
async def create_thumbnail(
    request: ThumbnailRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    Create thumbnail version of image
    
    Generates optimized thumbnail maintaining aspect ratio:
    - Configurable dimensions
    - JPEG optimization
    - Fast processing
    """
    
    try:
        thumbnail = await image_processor.create_thumbnail(
            image_data_url=request.image,
            size=(request.width, request.height)
        )
        
        return {
            "success": True,
            "thumbnail": thumbnail,
            "dimensions": {
                "width": request.width,
                "height": request.height
            },
            "correlation_id": get_correlation_id()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Thumbnail creation failed: {str(e)}"
        )


@router.get("/providers")
async def get_supported_providers(
    current_user: Dict = Depends(get_current_user)
):
    """
    Get list of supported AI providers and their requirements
    """
    
    providers = image_processor.get_supported_providers()
    provider_info = {}
    
    for provider in providers:
        requirements = image_processor.get_provider_requirements(provider)
        provider_info[provider] = {
            "max_size_mb": requirements.get("max_size", 0) / (1024 * 1024),
            "max_dimension": requirements.get("max_dimension", 0),
            "supported_formats": requirements.get("supported_formats", []),
            "preferred_format": requirements.get("preferred_format", "JPEG")
        }
    
    return {
        "supported_providers": providers,
        "provider_requirements": provider_info
    }


@router.get("/stats")
@require_role("admin")
async def get_processing_stats(
    current_user: Dict = Depends(get_current_user)
):
    """
    Get image processing statistics (admin only)
    
    Provides analytics on:
    - Processing volume
    - Average processing times
    - Provider usage
    - Error rates
    """
    
    # This would typically query a metrics database
    # For now, return placeholder data
    return {
        "total_processed": 0,
        "average_processing_time_ms": 0,
        "provider_usage": {},
        "error_rate": 0,
        "success_rate": 100
    }


# Background task functions
async def log_image_processing_success(
    user_id: str,
    provider: str, 
    original_size: int,
    processed_size: int,
    processing_time: float
):
    """Log successful image processing for analytics"""
    
    # This would typically save to database or analytics service
    image_processor.logger.log_business_metric(
        metric_name="image_processing_success",
        value=1,
        dimensions={
            "provider": provider,
            "size_reduction": f"{((original_size - processed_size) / original_size * 100):.1f}%",
            "processing_time_bucket": "fast" if processing_time < 500 else "medium" if processing_time < 2000 else "slow"
        }
    )