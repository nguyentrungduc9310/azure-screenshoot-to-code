"""
Image Generation Routes
Proxy routes for image generation service
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse

from app.services.service_client import ServiceClient, RequestResult
from shared.monitoring.correlation import get_correlation_id

router = APIRouter()

# Request/Response models
class ImageGenerationRequest(BaseModel):
    """Request model for image generation"""
    prompt: str = Field(..., description="Text prompt for image generation")
    provider: Optional[str] = Field(default="dalle3", description="Image generation provider (dalle3, flux_schnell)")
    size: Optional[str] = Field(default="1024x1024", description="Image size")
    quality: Optional[str] = Field(default="standard", description="Image quality (standard, hd)")
    style: Optional[str] = Field(default="natural", description="Image style (natural, vivid)")
    num_images: int = Field(default=1, ge=1, le=4, description="Number of images to generate")
    project_id: Optional[str] = Field(None, description="Associated project ID")

class ImageGenerationResponse(BaseModel):
    """Response model for image generation"""
    id: str = Field(..., description="Generation ID")
    prompt: str = Field(..., description="Text prompt used")
    provider: str = Field(..., description="Provider used")
    status: str = Field(..., description="Generation status")
    images: List[Dict[str, Any]] = Field(..., description="Generated images with metadata")
    generation_time_ms: float = Field(..., description="Generation time in milliseconds")
    cost_estimate: Optional[float] = Field(None, description="Estimated cost in USD")

def get_service_client(request: Request) -> ServiceClient:
    """Dependency to get service client from app state"""
    return request.app.state.service_client

def get_logger(request: Request):
    """Dependency to get logger from app state"""
    return request.app.state.logger

@router.post("/images/generate", response_model=ImageGenerationResponse)
async def generate_images(
    request_data: ImageGenerationRequest,
    request: Request,
    service_client: ServiceClient = Depends(get_service_client),
    logger = Depends(get_logger)
) -> JSONResponse:
    """Generate images from text prompt"""
    correlation_id = get_correlation_id()
    
    logger.info("Image generation request received",
                prompt_length=len(request_data.prompt),
                provider=request_data.provider,
                size=request_data.size,
                num_images=request_data.num_images,
                correlation_id=correlation_id)
    
    try:
        # Add user context from authentication middleware
        payload = request_data.dict()
        if hasattr(request.state, "user_id"):
            payload["user_id"] = request.state.user_id
            payload["tenant_id"] = getattr(request.state, "tenant_id", None)
        
        # Call image generation service
        result: RequestResult = await service_client.call_image_generator(
            method="POST",
            path="/generate",
            data=payload
        )
        
        if not result.success:
            logger.error("Image generation failed",
                        error=result.error,
                        status_code=result.status_code,
                        correlation_id=correlation_id)
            
            raise HTTPException(
                status_code=result.status_code or 500,
                detail=result.error or "Image generation failed"
            )
        
        logger.info("Image generation completed successfully",
                   generation_id=result.data.get("id"),
                   images_generated=len(result.data.get("images", [])),
                   duration_ms=result.duration_ms,
                   correlation_id=correlation_id)
        
        return JSONResponse(content=result.data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in image generation",
                    error=str(e),
                    correlation_id=correlation_id)
        
        raise HTTPException(
            status_code=500,
            detail="Internal server error during image generation"
        )

@router.get("/images/generation/{generation_id}")
async def get_image_generation_status(
    generation_id: str,
    request: Request,
    service_client: ServiceClient = Depends(get_service_client),
    logger = Depends(get_logger)
) -> JSONResponse:
    """Get status of an image generation request"""
    correlation_id = get_correlation_id()
    
    try:
        result: RequestResult = await service_client.call_image_generator(
            method="GET",
            path=f"/generation/{generation_id}"
        )
        
        if not result.success:
            if result.status_code == 404:
                raise HTTPException(status_code=404, detail="Generation not found")
            
            raise HTTPException(
                status_code=result.status_code or 500,
                detail=result.error or "Failed to get generation status"
            )
        
        return JSONResponse(content=result.data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting image generation status",
                    generation_id=generation_id,
                    error=str(e),
                    correlation_id=correlation_id)
        
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )

@router.get("/images/providers")
async def get_image_providers(
    request: Request,
    service_client: ServiceClient = Depends(get_service_client)
) -> JSONResponse:
    """Get available image generation providers and their capabilities"""
    try:
        result: RequestResult = await service_client.call_image_generator(
            method="GET",
            path="/providers"
        )
        
        if not result.success:
            raise HTTPException(
                status_code=result.status_code or 500,
                detail=result.error or "Failed to get image providers"
            )
        
        return JSONResponse(content=result.data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )

@router.post("/images/batch-generate")
async def batch_generate_images(
    requests: List[ImageGenerationRequest],
    request: Request,
    service_client: ServiceClient = Depends(get_service_client),
    logger = Depends(get_logger)
) -> JSONResponse:
    """Generate multiple images in batch"""
    correlation_id = get_correlation_id()
    
    logger.info("Batch image generation request",
                batch_size=len(requests),
                correlation_id=correlation_id)
    
    try:
        # Validate batch size
        if len(requests) > 10:  # Reasonable batch limit
            raise HTTPException(
                status_code=400,
                detail="Batch size too large. Maximum 10 requests per batch."
            )
        
        # Prepare batch payload
        payload = {
            "requests": [req.dict() for req in requests],
            "batch_id": correlation_id
        }
        
        # Add user context
        if hasattr(request.state, "user_id"):
            payload["user_id"] = request.state.user_id
            payload["tenant_id"] = getattr(request.state, "tenant_id", None)
        
        result: RequestResult = await service_client.call_image_generator(
            method="POST",
            path="/batch-generate",
            data=payload
        )
        
        if not result.success:
            logger.error("Batch image generation failed",
                        error=result.error,
                        status_code=result.status_code,
                        correlation_id=correlation_id)
            
            raise HTTPException(
                status_code=result.status_code or 500,
                detail=result.error or "Batch image generation failed"
            )
        
        logger.info("Batch image generation completed",
                   batch_id=result.data.get("batch_id"),
                   total_images=result.data.get("total_images", 0),
                   duration_ms=result.duration_ms,
                   correlation_id=correlation_id)
        
        return JSONResponse(content=result.data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in batch image generation",
                    error=str(e),
                    correlation_id=correlation_id)
        
        raise HTTPException(
            status_code=500,
            detail="Internal server error during batch generation"
        )

@router.get("/images/usage/stats")
async def get_image_usage_stats(
    request: Request,
    service_client: ServiceClient = Depends(get_service_client)
) -> JSONResponse:
    """Get image generation usage statistics for the current user"""
    try:
        # Add user context
        params = {}
        if hasattr(request.state, "user_id"):
            params["user_id"] = request.state.user_id
            params["tenant_id"] = getattr(request.state, "tenant_id", None)
        
        result: RequestResult = await service_client.call_image_generator(
            method="GET",
            path="/usage/stats",
            params=params
        )
        
        if not result.success:
            raise HTTPException(
                status_code=result.status_code or 500,
                detail=result.error or "Failed to get usage statistics"
            )
        
        return JSONResponse(content=result.data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )

@router.delete("/images/generation/{generation_id}")
async def delete_generated_images(
    generation_id: str,
    request: Request,
    service_client: ServiceClient = Depends(get_service_client),
    logger = Depends(get_logger)
) -> JSONResponse:
    """Delete generated images"""
    correlation_id = get_correlation_id()
    
    try:
        result: RequestResult = await service_client.call_image_generator(
            method="DELETE",
            path=f"/generation/{generation_id}"
        )
        
        if not result.success:
            if result.status_code == 404:
                raise HTTPException(status_code=404, detail="Generation not found")
            
            raise HTTPException(
                status_code=result.status_code or 500,
                detail=result.error or "Failed to delete images"
            )
        
        logger.info("Generated images deleted",
                   generation_id=generation_id,
                   correlation_id=correlation_id)
        
        return JSONResponse(content={"message": "Images deleted successfully"})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting generated images",
                    generation_id=generation_id,
                    error=str(e),
                    correlation_id=correlation_id)
        
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )