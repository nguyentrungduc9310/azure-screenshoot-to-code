# Image Processor API Documentation

**Version**: 1.0  
**Service**: Image Processor Service  
**Base URL**: `http://localhost:8001` (development)  
**Authentication**: Azure AD Bearer Token  

---

## Overview

The Image Processor API provides comprehensive image processing capabilities optimized for AI providers (Claude, OpenAI, Gemini). It handles image validation, format conversion, optimization, content analysis, and thumbnail generation.

### Key Features

- **Multi-provider Optimization**: Provider-specific image requirements and optimizations
- **Format Conversion**: JPEG, PNG, GIF, WEBP support with quality control
- **Content Analysis**: Complexity scoring, color analysis, EXIF handling
- **Thumbnail Generation**: High-quality thumbnails with aspect ratio preservation
- **Security**: Input validation, authentication, and secure error handling
- **Performance**: Optimized processing with metrics tracking

---

## Authentication

All endpoints require Azure AD authentication via Bearer token:

```bash
Authorization: Bearer <your-azure-ad-token>
```

**Exception**: Health check endpoints (`/health/*`) are public.

---

## Endpoints Overview

| Endpoint | Method | Auth Required | Purpose |
|----------|--------|---------------|---------|
| `/health` | GET | No | Basic health check |
| `/health/ready` | GET | No | Readiness probe |
| `/health/live` | GET | No | Liveness probe |
| `/health/metrics` | GET | Yes | Detailed metrics |
| `/health/capabilities` | GET | No | Service capabilities |
| `/api/v1/process` | POST | Yes | Process images for AI providers |
| `/api/v1/validate` | POST | Yes | Validate images against provider requirements |
| `/api/v1/analyze` | POST | Yes | Analyze image content and characteristics |
| `/api/v1/thumbnail` | POST | Yes | Create optimized thumbnails |
| `/api/v1/providers` | GET | Yes | Get supported providers and requirements |
| `/api/v1/stats` | GET | Yes (Admin) | Processing statistics |

---

## API Reference

### Health Endpoints

#### GET /health

Basic health check endpoint.

**Response 200**:
```json
{
  "status": "healthy",
  "service": "image-processor",
  "version": "1.0",
  "timestamp": "2024-01-22T10:30:00Z"
}
```

#### GET /health/ready

Kubernetes readiness probe endpoint.

**Response 200**:
```json
{
  "status": "ready",
  "checks": {
    "database": "ok",
    "external_services": "ok"
  }
}
```

#### GET /health/metrics

Detailed service metrics (requires authentication).

**Response 200**:
```json
{
  "service": {
    "name": "image-processor",
    "version": "1.0",
    "uptime_seconds": 3600
  },
  "system": {
    "cpu_usage_percent": 25.5,
    "memory_usage_mb": 156.2,
    "available_memory_mb": 843.8
  },
  "application": {
    "total_requests": 1250,
    "successful_requests": 1235,
    "error_rate": 0.012
  },
  "image_processing": {
    "total_processed": 845,
    "average_processing_time_ms": 324.5,
    "compression_ratio_avg": 0.65
  }
}
```

---

### Image Processing Endpoints

#### POST /api/v1/process

Process images according to AI provider requirements.

**Request Body**:
```json
{
  "image": "data:image/png;base64,iVBORw0KGgo...",
  "provider": "claude",
  "options": {
    "format": "JPEG",
    "quality": 90,
    "max_dimension": 2048
  }
}
```

**Parameters**:
- `image` (required): Base64 data URL of the image
- `provider` (required): AI provider (`claude`, `openai`, `gemini`)
- `options` (optional): Processing options object

**Processing Options**:
- `format`: Target format (`JPEG`, `PNG`, `WEBP`)
- `quality`: JPEG quality (1-100, default: provider-optimized)
- `max_dimension`: Maximum width/height in pixels
- `preserve_transparency`: Keep transparency for formats that support it
- `background_color`: Background color for transparency removal (hex, e.g., "#FFFFFF")

**Response 200**:
```json
{
  "success": true,
  "processed_image": "data:image/jpeg;base64,/9j/4AAQ...",
  "original_format": "PNG",
  "processed_format": "JPEG",
  "original_size": 1024768,
  "processed_size": 856432,
  "dimensions": [1920, 1080],
  "processing_time_ms": 245.67,
  "compression_ratio": 0.836,
  "correlation_id": "req-123e4567-e89b-12d3-a456-426614174000",
  "metadata": {
    "provider": "claude",
    "quality_used": 90,
    "resized": false,
    "has_transparency": false,
    "image_hash": "d4d4d4d4d4d4d4d4"
  }
}
```

**Error Response 422**:
```json
{
  "success": false,
  "error": "validation_error",
  "message": "Image exceeds maximum size limit for claude provider",
  "details": {
    "max_size_mb": 5,
    "actual_size_mb": 8.5,
    "provider": "claude"
  },
  "correlation_id": "req-123e4567-e89b-12d3-a456-426614174000"
}
```

#### POST /api/v1/validate

Validate images against provider requirements without processing.

**Request Body**:
```json
{
  "image": "data:image/png;base64,iVBORw0KGgo...",
  "provider": "claude"
}
```

**Response 200**:
```json
{
  "valid": true,
  "provider": "claude",
  "file_size": 1024768,
  "file_size_mb": 1.02,
  "dimensions": {
    "width": 1920,
    "height": 1080,
    "aspect_ratio": 1.78
  },
  "format": "PNG",
  "color_mode": "RGBA",
  "has_transparency": true,
  "requirements_met": {
    "size_limit": true,
    "dimension_limit": true,
    "format_supported": true
  },
  "correlation_id": "req-123e4567-e89b-12d3-a456-426614174000"
}
```

**Validation Failure Response 200**:
```json
{
  "valid": false,
  "error_message": "Image dimensions exceed maximum limit for claude provider",
  "provider": "claude",
  "file_size": 25165824,
  "file_size_mb": 25.17,
  "dimensions": {
    "width": 8000,
    "height": 8000
  },
  "format": "PNG",
  "requirements_met": {
    "size_limit": false,
    "dimension_limit": false,
    "format_supported": true
  },
  "limits": {
    "max_size_mb": 5,
    "max_dimension": 7990,
    "supported_formats": ["JPEG", "PNG", "GIF", "WEBP"]
  }
}
```

#### POST /api/v1/analyze

Analyze image content and characteristics.

**Request Body**:
```json
{
  "image": "data:image/png;base64,iVBORw0KGgo..."
}
```

**Response 200**:
```json
{
  "success": true,
  "analysis": {
    "dimensions": {
      "width": 1920,
      "height": 1080,
      "aspect_ratio": 1.78
    },
    "format": "PNG",
    "mode": "RGBA",
    "size_bytes": 1024768,
    "size_mb": 1.02,
    "has_transparency": true,
    "has_animation": false,
    "complexity_score": 7.2,
    "dominant_colors": 156,
    "is_grayscale": false,
    "has_exif": true,
    "exif_orientation": 1,
    "image_hash": "d4d4d4d4d4d4d4d4",
    "estimated_compression_ratio": 0.65,
    "analysis_time_ms": 142.34
  },
  "recommendations": {
    "best_provider": "gemini",
    "suggested_format": "JPEG",
    "estimated_quality": 85,
    "processing_notes": "High complexity image, JPEG recommended for size optimization"
  },
  "correlation_id": "req-123e4567-e89b-12d3-a456-426614174000"
}
```

#### POST /api/v1/thumbnail

Create optimized thumbnails.

**Request Body**:
```json
{
  "image": "data:image/png;base64,iVBORw0KGgo...",
  "width": 150,
  "height": 150,
  "options": {
    "maintain_aspect_ratio": true,
    "quality": 80,
    "background_color": "#FFFFFF"
  }
}
```

**Parameters**:
- `image` (required): Base64 data URL of the image
- `width` (required): Target width (10-500px)
- `height` (required): Target height (10-500px)
- `options` (optional): Thumbnail options

**Thumbnail Options**:
- `maintain_aspect_ratio`: Preserve aspect ratio (default: true)
- `quality`: JPEG quality (1-100, default: 80)
- `background_color`: Background for transparent images (default: "#FFFFFF")

**Response 200**:
```json
{
  "success": true,
  "thumbnail": "data:image/jpeg;base64,/9j/4AAQ...",
  "dimensions": {
    "width": 150,
    "height": 150
  },
  "original_dimensions": {
    "width": 1920,
    "height": 1080
  },
  "file_size": 8432,
  "compression_ratio": 0.992,
  "processing_time_ms": 45.23,
  "correlation_id": "req-123e4567-e89b-12d3-a456-426614174000"
}
```

#### GET /api/v1/providers

Get supported providers and their requirements.

**Response 200**:
```json
{
  "supported_providers": ["claude", "openai", "gemini"],
  "provider_requirements": {
    "claude": {
      "max_size": 5242880,
      "max_size_mb": 5,
      "max_dimension": 7990,
      "supported_formats": ["JPEG", "PNG", "GIF", "WEBP"],
      "preferred_format": "JPEG",
      "notes": "Optimized for text-heavy images, aggressive compression"
    },
    "openai": {
      "max_size": 20971520,
      "max_size_mb": 20,
      "max_dimension": 2048,
      "supported_formats": ["JPEG", "PNG", "GIF", "WEBP"],
      "preferred_format": "PNG",
      "notes": "Supports transparency, optimized for vision models"
    },
    "gemini": {
      "max_size": 20971520,
      "max_size_mb": 20,
      "max_dimension": 4096,
      "supported_formats": ["JPEG", "PNG", "GIF", "WEBP"],
      "preferred_format": "JPEG",
      "notes": "High-resolution support, efficient compression"
    }
  }
}
```

#### GET /api/v1/stats

Get processing statistics (Admin only).

**Response 200**:
```json
{
  "total_processed": 15234,
  "total_size_processed_mb": 45678.23,
  "average_processing_time_ms": 324.5,
  "average_compression_ratio": 0.652,
  "provider_usage": {
    "claude": 8432,
    "openai": 4521,
    "gemini": 2281
  },
  "format_distribution": {
    "JPEG": 9876,
    "PNG": 4321,
    "GIF": 654,
    "WEBP": 383
  },
  "error_rate": 0.012,
  "performance_metrics": {
    "p50_processing_time_ms": 245,
    "p95_processing_time_ms": 1200,
    "p99_processing_time_ms": 2400
  },
  "period": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-01-22T10:30:00Z"
  }
}
```

---

## Provider-Specific Guidelines

### Claude Optimization
- **Max Size**: 5MB
- **Max Dimension**: 7990px
- **Preferred Format**: JPEG with 95% quality
- **Best For**: Text-heavy images, screenshots, documents
- **Optimization**: Aggressive compression with quality preservation

### OpenAI Optimization
- **Max Size**: 20MB
- **Max Dimension**: 2048px
- **Preferred Format**: PNG for transparency support
- **Best For**: UI designs, illustrations, transparent images
- **Optimization**: Transparency preservation, metadata stripping

### Gemini Optimization
- **Max Size**: 20MB
- **Max Dimension**: 4096px
- **Preferred Format**: JPEG with variable quality
- **Best For**: High-resolution photos, detailed images
- **Optimization**: Color space optimization, efficient compression

---

## Error Handling

### HTTP Status Codes

- **200**: Success
- **400**: Bad Request - Invalid request format
- **401**: Unauthorized - Missing or invalid authentication
- **403**: Forbidden - Insufficient permissions
- **413**: Payload Too Large - Request exceeds size limit
- **422**: Unprocessable Entity - Validation errors
- **429**: Too Many Requests - Rate limit exceeded
- **500**: Internal Server Error - Processing failure

### Error Response Format

All errors follow a consistent format:

```json
{
  "success": false,
  "error": "error_code",
  "message": "Human-readable error message",
  "details": {
    "field": "specific_error_details"
  },
  "correlation_id": "req-123e4567-e89b-12d3-a456-426614174000",
  "timestamp": "2024-01-22T10:30:00Z"
}
```

### Common Error Codes

- `validation_error`: Input validation failed
- `authentication_required`: Authentication token missing
- `permission_denied`: Insufficient permissions
- `image_processing_failed`: Processing error
- `provider_not_supported`: Invalid provider
- `file_too_large`: File exceeds size limits
- `invalid_format`: Unsupported image format
- `dimension_exceeded`: Image dimensions too large

---

## Performance Guidelines

### Processing Time Expectations

| Image Size | Expected Processing Time |
|------------|-------------------------|
| < 1MB | 50-150ms |
| 1-5MB | 150-500ms |
| 5-20MB | 500-2000ms |
| Thumbnails | 10-50ms |
| Analysis | 100-300ms |

### Optimization Tips

1. **Use appropriate providers**: Match image type to provider strengths
2. **Optimize before upload**: Pre-compress large images when possible
3. **Choose efficient formats**: JPEG for photos, PNG for graphics
4. **Batch operations**: Process multiple images in sequence for efficiency
5. **Cache results**: Cache processed images to avoid reprocessing

### Rate Limits

- **Default**: 60 requests/minute per user
- **Admin**: 300 requests/minute
- **Burst**: Up to 10 concurrent requests

---

## Integration Examples

### JavaScript/TypeScript

```typescript
import axios from 'axios';

const imageProcessor = {
  baseURL: 'http://localhost:8001',
  
  async processImage(imageDataUrl: string, provider: string, options?: any) {
    try {
      const response = await axios.post(`${this.baseURL}/api/v1/process`, {
        image: imageDataUrl,
        provider,
        options
      }, {
        headers: {
          'Authorization': `Bearer ${getAccessToken()}`,
          'Content-Type': 'application/json'
        },
        timeout: 30000 // 30 second timeout
      });
      
      return response.data;
    } catch (error) {
      console.error('Image processing failed:', error.response?.data);
      throw error;
    }
  },
  
  async validateImage(imageDataUrl: string, provider: string) {
    const response = await axios.post(`${this.baseURL}/api/v1/validate`, {
      image: imageDataUrl,
      provider
    }, {
      headers: { 'Authorization': `Bearer ${getAccessToken()}` }
    });
    
    return response.data;
  }
};

// Usage
const result = await imageProcessor.processImage(
  'data:image/png;base64,iVBORw0KGgo...',
  'claude',
  { format: 'JPEG', quality: 90 }
);
```

### Python

```python
import requests
import base64
from typing import Optional, Dict, Any

class ImageProcessor:
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        
    def _get_headers(self, token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def process_image(
        self, 
        image_data_url: str, 
        provider: str, 
        token: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        payload = {
            "image": image_data_url,
            "provider": provider
        }
        if options:
            payload["options"] = options
            
        response = requests.post(
            f"{self.base_url}/api/v1/process",
            json=payload,
            headers=self._get_headers(token),
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    
    def validate_image(self, image_data_url: str, provider: str, token: str) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/api/v1/validate",
            json={"image": image_data_url, "provider": provider},
            headers=self._get_headers(token)
        )
        response.raise_for_status()
        return response.json()

# Usage
processor = ImageProcessor()
result = processor.process_image(
    image_data_url="data:image/png;base64,iVBORw0KGgo...",
    provider="claude",
    token="your-access-token",
    options={"format": "JPEG", "quality": 90}
)
```

### cURL Examples

```bash
# Process image
curl -X POST http://localhost:8001/api/v1/process \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "image": "data:image/png;base64,iVBORw0KGgo...",
    "provider": "claude",
    "options": {
      "format": "JPEG",
      "quality": 90
    }
  }'

# Validate image
curl -X POST http://localhost:8001/api/v1/validate \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "image": "data:image/png;base64,iVBORw0KGgo...",
    "provider": "claude"
  }'

# Create thumbnail
curl -X POST http://localhost:8001/api/v1/thumbnail \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "image": "data:image/png;base64,iVBORw0KGgo...",
    "width": 150,
    "height": 150
  }'

# Health check
curl -X GET http://localhost:8001/health
```

---

## Testing

### Test Environment

Development server runs on `http://localhost:8001` with Docker Compose:

```bash
# Start service
docker-compose up image-processor

# Run tests
docker-compose run --rm image-processor-test

# Health check
curl http://localhost:8001/health
```

### Sample Test Images

For testing, you can use these sample base64 data URLs:

**Small PNG (1x1 pixel)**:
```
data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==
```

**Test with different providers**:
```bash
# Test all providers
for provider in claude openai gemini; do
  curl -X POST http://localhost:8001/api/v1/validate \
    -H "Authorization: Bearer YOUR_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"image\": \"data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==\", \"provider\": \"$provider\"}"
done
```

---

## Changelog

### Version 1.0 (January 2024)
- Initial API release
- Multi-provider support (Claude, OpenAI, Gemini)
- Image processing, validation, analysis, thumbnails
- Azure AD authentication
- Comprehensive error handling
- Performance monitoring

---

## Support

For API issues or questions:
- **Documentation**: [Project Repository](https://github.com/your-org/screenshot-to-code)
- **Issues**: Create GitHub issue with API tag
- **Logs**: Check correlation ID in responses for troubleshooting

---

**Last Updated**: January 22, 2024  
**API Version**: 1.0  
**Documentation Version**: 1.0