"""
Image Generation API Routes
Handles image generation requests using DALL-E 3 and Flux Schnell
"""
import asyncio
import json
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field, validator
import structlog

from app.core.config import Settings, ImageProvider, ImageSize, ImageQuality, ImageStyle
from app.services.image_provider_manager import ImageProviderManager, ImageGenerationRequest, GenerationStatus
from app.services.storage_manager import StorageManager
from shared.monitoring.correlation import get_correlation_id, set_correlation_id
from shared.monitoring.structured_logger import StructuredLogger

router = APIRouter()

# Request/Response Models
class ImageGenerationRequestModel(BaseModel):
    """Request model for image generation"""
    prompt: str = Field(..., min_length=1, max_length=4000, description="Text prompt for image generation")
    provider: Optional[ImageProvider] = Field(None, description="Image provider to use")
    size: Optional[ImageSize] = Field(None, description="Image size")
    quality: Optional[ImageQuality] = Field(None, description="Image quality (DALL-E 3 only)")
    style: Optional[ImageStyle] = Field(None, description="Image style (DALL-E 3 only)")
    num_images: int = Field(1, ge=1, le=4, description="Number of images to generate")
    seed: Optional[int] = Field(None, description="Random seed (Flux Schnell only)")
    store_images: bool = Field(True, description="Whether to store generated images")
    
    @validator('prompt')
    def validate_prompt(cls, v):
        v = v.strip()
        if not v:
            raise ValueError('Prompt cannot be empty')
        return v

class GeneratedImageResponse(BaseModel):
    """Generated image in response"""
    image_id: Optional[str] = None
    url: Optional[str] = None
    storage_url: Optional[str] = None
    base64_data: Optional[str] = None
    revised_prompt: Optional[str] = None
    size: str
    provider: str

class ImageGenerationResponse(BaseModel):
    """Response model for image generation"""
    success: bool
    images: List[GeneratedImageResponse]
    provider: str
    model: str
    duration_seconds: float
    prompt: str
    revised_prompt: Optional[str] = None
    correlation_id: str
    error: Optional[str] = None
    status: str

class ProvidersResponse(BaseModel):
    """Response model for available providers"""
    providers: List[Dict[str, Any]]
    default_provider: str

class ImageInfoResponse(BaseModel):
    """Response model for stored image information"""
    image_id: str
    original_filename: str
    storage_path: str
    storage_url: Optional[str] = None
    content_type: str
    size_bytes: int
    created_at: str
    metadata: Dict[str, Any]

# Dependency injection
async def get_image_provider_manager(request) -> ImageProviderManager:
    """Get image provider manager from app state"""
    return request.app.state.image_provider_manager

async def get_storage_manager(request) -> Optional[StorageManager]:
    """Get storage manager from app state"""
    return request.app.state.storage_manager

async def get_logger(request) -> StructuredLogger:
    """Get logger from app state"""
    return request.app.state.logger

# REST Endpoints
@router.get("/providers", response_model=ProvidersResponse)
async def get_available_providers(
    provider_manager: ImageProviderManager = Depends(get_image_provider_manager)
):
    """Get list of available image providers"""
    available_providers = provider_manager.get_available_providers()
    default_provider = provider_manager.get_default_provider()
    
    providers_info = []
    for provider in available_providers:
        provider_info = provider_manager.get_provider_info(provider)
        providers_info.append(provider_info)
    
    return ProvidersResponse(
        providers=providers_info,
        default_provider=default_provider.value if default_provider else ""
    )

@router.post("/generate", response_model=ImageGenerationResponse)
async def generate_images(
    request: ImageGenerationRequestModel,
    background_tasks: BackgroundTasks,
    provider_manager: ImageProviderManager = Depends(get_image_provider_manager),
    storage_manager: Optional[StorageManager] = Depends(get_storage_manager),
    logger: StructuredLogger = Depends(get_logger)
):
    """Generate images from text prompt"""
    correlation_id = get_correlation_id()
    set_correlation_id(correlation_id)
    
    logger.info("Image generation request received",
                provider=request.provider.value if request.provider else "default",
                num_images=request.num_images,
                prompt_length=len(request.prompt),
                correlation_id=correlation_id)
    
    try:
        # Determine provider
        selected_provider = request.provider or provider_manager.get_default_provider()
        if not provider_manager.is_provider_available(selected_provider):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "provider_unavailable",
                    "message": f"Provider {selected_provider.value} is not available",
                    "correlation_id": correlation_id
                }
            )
        
        # Determine size based on provider
        if request.size:
            selected_size = request.size
        else:
            # Use provider default
            if selected_provider == ImageProvider.DALLE3:
                selected_size = ImageSize.DALLE3_1024x1024
            else:  # FLUX_SCHNELL
                selected_size = ImageSize.FLUX_1024x1024
        
        # Create generation request
        generation_request = ImageGenerationRequest(
            prompt=request.prompt,
            provider=selected_provider,
            size=selected_size,
            quality=request.quality.value if request.quality else None,
            style=request.style.value if request.style else None,
            num_images=request.num_images,
            seed=request.seed,
            correlation_id=correlation_id
        )
        
        # Validate request
        validation_issues = provider_manager.validate_request(generation_request)
        if validation_issues:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "validation_failed",
                    "issues": validation_issues,
                    "correlation_id": correlation_id
                }
            )
        
        # Generate images
        result = await provider_manager.generate_images(generation_request)
        
        if result.error:
            logger.error("Image generation failed", 
                        error=result.error,
                        provider=selected_provider.value,
                        correlation_id=correlation_id)
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "generation_failed", 
                    "message": result.error,
                    "correlation_id": correlation_id
                }
            )
        
        # Process generated images
        response_images = []
        for image in result.images:
            image_response = GeneratedImageResponse(
                url=image.url,
                base64_data=image.base64_data,
                revised_prompt=image.revised_prompt,
                size=image.size or selected_size.value,
                provider=image.provider or selected_provider.value
            )
            
            # Store image if requested and storage is available
            if request.store_images and storage_manager:
                try:
                    stored_image = None
                    
                    if image.url:
                        # Store from URL
                        filename = f"generated_{correlation_id}_{len(response_images)}.png"
                        stored_image = await storage_manager.store_image_from_url(
                            image.url, filename
                        )
                    elif image.base64_data:
                        # Store from base64
                        filename = f"generated_{correlation_id}_{len(response_images)}.png"
                        stored_image = await storage_manager.store_image_from_base64(
                            image.base64_data, filename
                        )
                    
                    if stored_image:
                        image_response.image_id = stored_image.storage_id
                        image_response.storage_url = stored_image.storage_url
                        
                        logger.info("Image stored successfully",
                                   image_id=stored_image.storage_id,
                                   correlation_id=correlation_id)
                
                except Exception as e:
                    logger.warning("Failed to store image",
                                 error=str(e),
                                 correlation_id=correlation_id)
                    # Continue without storing - don't fail the whole request
            
            response_images.append(image_response)
        
        logger.info("Image generation completed successfully",
                   provider=result.provider.value,
                   num_images=len(response_images),
                   duration_seconds=result.duration_seconds,
                   correlation_id=correlation_id)
        
        return ImageGenerationResponse(
            success=True,
            images=response_images,
            provider=result.provider.value,
            model=result.model,
            duration_seconds=result.duration_seconds,
            prompt=result.prompt,
            revised_prompt=result.revised_prompt,
            correlation_id=correlation_id,
            status=result.status.value
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error during image generation",
                    error=str(e),
                    correlation_id=correlation_id,
                    exc_info=e)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_server_error",
                "message": "An unexpected error occurred",
                "correlation_id": correlation_id
            }
        )

@router.get("/images/{image_id}", response_model=ImageInfoResponse)
async def get_image_info(
    image_id: str,
    storage_manager: Optional[StorageManager] = Depends(get_storage_manager),
    logger: StructuredLogger = Depends(get_logger)
):
    """Get information about a stored image"""
    if not storage_manager:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "storage_not_enabled",
                "message": "Image storage is not enabled"
            }
        )
    
    correlation_id = get_correlation_id()
    
    # This would require implementing a metadata storage system
    # For now, return a basic response
    raise HTTPException(
        status_code=501,
        detail={
            "error": "not_implemented",
            "message": "Image metadata retrieval not yet implemented"
        }
    )

@router.get("/images/{image_id}/download")
async def download_image(
    image_id: str,
    storage_manager: Optional[StorageManager] = Depends(get_storage_manager),
    logger: StructuredLogger = Depends(get_logger)
):
    """Download a stored image"""
    if not storage_manager:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "storage_not_enabled",
                "message": "Image storage is not enabled"
            }
        )
    
    correlation_id = get_correlation_id()
    
    try:
        # Retrieve image data
        image_data = await storage_manager.retrieve_image(image_id)
        
        if not image_data:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "image_not_found",
                    "message": f"Image with ID {image_id} not found"
                }
            )
        
        # Create temporary file for download
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
            temp_file.write(image_data)
            temp_path = temp_file.name
        
        # Schedule cleanup
        background_tasks = BackgroundTasks()
        background_tasks.add_task(os.unlink, temp_path)
        
        return FileResponse(
            temp_path,
            media_type="image/png",
            filename=f"{image_id}.png",
            background=background_tasks
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to download image",
                    image_id=image_id,
                    error=str(e),
                    correlation_id=correlation_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "download_failed",
                "message": "Failed to download image"
            }
        )

@router.delete("/images/{image_id}")
async def delete_image(
    image_id: str,
    storage_manager: Optional[StorageManager] = Depends(get_storage_manager),
    logger: StructuredLogger = Depends(get_logger)
):
    """Delete a stored image"""
    if not storage_manager:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "storage_not_enabled",
                "message": "Image storage is not enabled"
            }
        )
    
    correlation_id = get_correlation_id()
    
    try:
        # Delete image
        deleted = await storage_manager.delete_image(image_id)
        
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "image_not_found",
                    "message": f"Image with ID {image_id} not found"
                }
            )
        
        logger.info("Image deleted successfully",
                   image_id=image_id,
                   correlation_id=correlation_id)
        
        return {
            "success": True,
            "message": f"Image {image_id} deleted successfully",
            "correlation_id": correlation_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete image",
                    image_id=image_id,
                    error=str(e),
                    correlation_id=correlation_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "delete_failed",
                "message": "Failed to delete image"
            }
        )

@router.post("/generate/batch")
async def generate_images_batch(
    requests: List[ImageGenerationRequestModel],
    background_tasks: BackgroundTasks,
    provider_manager: ImageProviderManager = Depends(get_image_provider_manager),
    storage_manager: Optional[StorageManager] = Depends(get_storage_manager),
    logger: StructuredLogger = Depends(get_logger)
):
    """Generate multiple sets of images in batch"""
    correlation_id = get_correlation_id()
    set_correlation_id(correlation_id)
    
    if len(requests) > 10:  # Limit batch size
        raise HTTPException(
            status_code=400,
            detail={
                "error": "batch_too_large",
                "message": "Maximum 10 requests per batch"
            }
        )
    
    logger.info("Batch image generation request received",
                batch_size=len(requests),
                correlation_id=correlation_id)
    
    results = []
    
    # Process requests concurrently
    async def process_request(req: ImageGenerationRequestModel, index: int):
        try:
            # Create a new request with the same parameters
            single_response = await generate_images(
                req, background_tasks, provider_manager, storage_manager, logger
            )
            return {"index": index, "result": single_response, "error": None}
        except Exception as e:
            return {"index": index, "result": None, "error": str(e)}
    
    # Execute all requests concurrently
    tasks = [process_request(req, i) for i, req in enumerate(requests)]
    batch_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Format results
    for result in batch_results:
        if isinstance(result, Exception):
            results.append({
                "success": False,
                "error": str(result),
                "correlation_id": correlation_id
            })
        else:
            results.append(result["result"] if result["error"] is None else {
                "success": False,
                "error": result["error"],
                "correlation_id": correlation_id
            })
    
    logger.info("Batch image generation completed",
               batch_size=len(requests),
               successful=sum(1 for r in results if r.get("success", False)),
               correlation_id=correlation_id)
    
    return {
        "success": True,
        "batch_size": len(requests),
        "results": results,
        "correlation_id": correlation_id
    }