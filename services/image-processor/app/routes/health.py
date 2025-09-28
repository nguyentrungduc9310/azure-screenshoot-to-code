"""
Health check endpoints for Image Processor service
"""
from fastapi import APIRouter, Depends
from typing import Dict, Any
import time
import psutil
from shared.health.health_checker import HealthChecker, create_health_endpoint
from shared.auth.azure_ad import get_current_user
from shared.config.settings import settings

router = APIRouter()

# Initialize health checker for image processor
health_checker = HealthChecker("image-processor")

# Add health checks based on dependencies
# Note: Image processor is primarily stateless, but we check basic dependencies

# Create health endpoints using shared health checker
create_health_endpoint(router, health_checker)

@router.get("/metrics")
async def get_metrics(current_user: Dict = Depends(get_current_user)):
    """Get image processor service metrics (requires authentication)"""
    
    # System metrics
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # Image processing specific metrics
    app_metrics = {
        "images_processed_total": 0,  # Would be tracked in real implementation
        "average_processing_time_ms": 0,  # Would be calculated from metrics
        "average_compression_ratio": 0,  # Would be tracked
        "supported_providers": ["claude", "openai", "gemini"],
        "active_connections": 0,  # Current API connections
        "error_rate_percent": 0  # Error rate tracking
    }
    
    # PIL/Image processing capabilities
    try:
        from PIL import Image
        pil_info = {
            "pil_available": True,
            "pil_version": getattr(Image, 'VERSION', 'unknown'),
            "supported_formats": list(Image.registered_extensions().keys())[:10]  # First 10 formats
        }
    except ImportError:
        pil_info = {
            "pil_available": False,
            "error": "PIL/Pillow not available"
        }
    
    return {
        "service": "image-processor",
        "timestamp": time.time(),
        "system": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_mb": memory.available // 1024 // 1024,
            "disk_percent": (disk.used / disk.total) * 100,
            "disk_free_gb": disk.free // 1024 // 1024 // 1024
        },
        "application": app_metrics,
        "image_processing": pil_info
    }

@router.get("/capabilities")
async def get_capabilities():
    """Get image processing capabilities (public endpoint)"""
    
    try:
        from PIL import Image
        import imagehash
        
        # Get supported formats
        read_formats = list(Image.registered_extensions().keys())
        write_formats = list(Image.registered_save().keys())
        
        capabilities = {
            "pil_available": True,
            "imagehash_available": True,
            "read_formats": sorted(read_formats),
            "write_formats": sorted(write_formats),
            "supported_providers": ["claude", "openai", "gemini"],
            "features": [
                "image_validation",
                "image_processing", 
                "format_conversion",
                "compression",
                "thumbnail_generation",
                "content_analysis",
                "exif_handling",
                "transparency_support"
            ],
            "max_image_size": "Varies by provider",
            "processing_modes": ["standard", "optimized", "high_quality"]
        }
        
    except ImportError as e:
        capabilities = {
            "pil_available": False,
            "error": f"Required libraries not available: {str(e)}",
            "supported_providers": [],
            "features": []
        }
    
    return capabilities