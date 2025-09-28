# Image Generator Service

A FastAPI microservice for generating images from text prompts using DALL-E 3 and Flux Schnell.

## Features

- **Multi-Provider Support**: DALL-E 3 (OpenAI/Azure OpenAI) and Flux Schnell
- **Multiple Image Sizes**: Provider-specific optimal sizes
- **Batch Generation**: Generate multiple images concurrently
- **Image Storage**: Local, Azure Blob Storage, or AWS S3
- **Content Moderation**: Basic keyword filtering
- **Comprehensive Monitoring**: Structured logging, health checks, correlation tracking
- **Authentication**: Azure AD integration
- **Docker Support**: Containerized deployment

## Supported Providers

### DALL-E 3
- **Provider**: OpenAI or Azure OpenAI
- **Features**: High-quality artistic images, prompt revision, quality/style controls
- **Sizes**: 1024x1024, 1792x1024, 1024x1792
- **Max Images**: 1 per request
- **Generation Time**: 10-30 seconds

### Flux Schnell
- **Provider**: Black Forest Labs
- **Features**: Fast generation, seed control, multiple images
- **Sizes**: 512x512, 768x768, 1024x1024, 1536x1024, 1024x1536
- **Max Images**: 4 per request
- **Generation Time**: 2-8 seconds

## API Endpoints

### Image Generation

- `POST /api/v1/generate` - Generate images from text prompt
- `POST /api/v1/generate/batch` - Generate multiple sets of images
- `GET /api/v1/providers` - Get available providers

### Image Management

- `GET /api/v1/images/{image_id}` - Get image information
- `GET /api/v1/images/{image_id}/download` - Download stored image
- `DELETE /api/v1/images/{image_id}` - Delete stored image

### Health Checks

- `GET /health/` - Overall health status
- `GET /health/ready` - Readiness check
- `GET /health/live` - Liveness check

## Quick Start

### Development

1. **Clone and setup**:
   ```bash
   cd services/image-generator
   cp .env.example .env
   # Edit .env with your API keys
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the service**:
   ```bash
   python -m uvicorn app.main:app --reload --port 8003
   ```

### Docker

1. **Build and run**:
   ```bash
   docker build -t image-generator:latest .
   docker run -p 8003:8003 --env-file .env image-generator:latest
   ```

2. **Access the service**:
   - API: http://localhost:8003
   - Docs: http://localhost:8003/docs

## Configuration

### Required Environment Variables

At least one image provider must be configured:

**DALL-E 3 (OpenAI)**:
```bash
OPENAI_API_KEY=your-key-here
```

**DALL-E 3 (Azure OpenAI)**:
```bash
AZURE_OPENAI_API_KEY=your-key-here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=your-dalle3-deployment
```

**Flux Schnell**:
```bash
FLUX_API_KEY=your-key-here
```

### Optional Configuration

```bash
# Service
ENVIRONMENT=development
LOG_LEVEL=INFO
API_PORT=8003

# Providers
ENABLED_PROVIDERS=dalle3,flux_schnell
DEFAULT_PROVIDER=dalle3

# Image Generation
MAX_IMAGES_PER_REQUEST=4
ENABLE_PROMPT_ENHANCEMENT=true

# Storage
ENABLE_IMAGE_STORAGE=true
STORAGE_BACKEND=local

# Security
ENABLE_AUTHENTICATION=false
ENABLE_CONTENT_MODERATION=true
```

## API Usage Examples

### Generate Single Image

```bash
curl -X POST "http://localhost:8003/api/v1/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A futuristic city skyline at sunset",
    "provider": "dalle3",
    "size": "1024x1024",
    "quality": "hd",
    "style": "vivid",
    "num_images": 1
  }'
```

### Generate Multiple Images (Flux Schnell)

```bash
curl -X POST "http://localhost:8003/api/v1/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Abstract geometric patterns in blue and gold",
    "provider": "flux_schnell",
    "size": "1024x1024",
    "num_images": 4,
    "seed": 42
  }'
```

### Batch Generation

```bash
curl -X POST "http://localhost:8003/api/v1/generate/batch" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "prompt": "Mountain landscape",
      "provider": "dalle3",
      "size": "1792x1024"
    },
    {
      "prompt": "Ocean waves",
      "provider": "flux_schnell",
      "size": "1024x1536",
      "num_images": 2
    }
  ]'
```

### Get Available Providers

```bash
curl "http://localhost:8003/api/v1/providers"
```

Response:
```json
{
  "providers": [
    {
      "id": "dalle3",
      "name": "DALL-E 3",
      "description": "OpenAI's advanced image generation model",
      "supported_sizes": ["1024x1024", "1792x1024", "1024x1792"],
      "max_images": 1,
      "supports_quality": true,
      "supports_style": true,
      "typical_generation_time": "10-30 seconds"
    },
    {
      "id": "flux_schnell",
      "name": "Flux Schnell",
      "description": "Fast image generation model optimized for speed",
      "supported_sizes": ["512x512", "768x768", "1024x1024", "1536x1024", "1024x1536"],
      "max_images": 4,
      "supports_seed": true,
      "typical_generation_time": "2-8 seconds"
    }
  ],
  "default_provider": "dalle3"
}
```

## Storage Backends

### Local Storage
- **Path**: `./generated_images/YYYY/MM/DD/`
- **Files**: `{storage_id}.png`, `{storage_id}.json` (metadata)

### Azure Blob Storage
- **Container**: Configurable (default: `generated-images`)
- **Path**: `YYYY/MM/DD/{storage_id}.png`
- **Metadata**: Stored as blob metadata

### AWS S3
- **Bucket**: Configurable
- **Key**: `YYYY/MM/DD/{storage_id}.png`
- **Metadata**: Stored as object metadata

## Content Moderation

Basic content moderation is available through keyword filtering:

```bash
ENABLE_CONTENT_MODERATION=true
BLOCKED_WORDS=inappropriate,word1,word2
```

## Error Handling

All API responses include:
- Success/error status
- Correlation ID for tracing
- Detailed error messages
- HTTP status codes

Example error response:
```json
{
  "success": false,
  "error": "validation_failed",
  "message": "Prompt cannot be empty",
  "correlation_id": "abc123-def456-ghi789"
}
```

## Monitoring

The service includes comprehensive monitoring:

- **Structured Logging**: JSON-formatted logs with correlation IDs
- **Application Insights**: Integration with Azure Application Insights
- **Health Checks**: Kubernetes-compatible health endpoints
- **Request Tracking**: Correlation IDs for request tracing
- **Performance Metrics**: Generation time, success rates

## Development

### Project Structure

```
app/
├── core/
│   └── config.py              # Configuration settings
├── middleware/
│   └── validation.py          # Request validation
├── routes/
│   ├── image_generation.py    # Image generation endpoints
│   └── health.py              # Health check endpoints
├── services/
│   ├── image_provider_manager.py  # Provider management
│   └── storage_manager.py     # Image storage
└── main.py                    # FastAPI application
```

### Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=app tests/

# Lint code
black app/
isort app/
flake8 app/
```

## Deployment

### Docker

```bash
# Build
docker build -t image-generator:latest .

# Run
docker run -p 8003:8003 --env-file .env image-generator:latest
```

### Kubernetes

Kubernetes manifests available in `k8s/` directory:

```bash
kubectl apply -f k8s/
```

## Performance

- **Concurrent Requests**: Configurable (default: 5)
- **Request Timeout**: 300 seconds (5 minutes)
- **Batch Processing**: Up to 10 requests per batch
- **Image Storage**: Async with background tasks
- **Provider Failover**: Automatic fallback to available providers

## Security

- **Authentication**: Azure AD integration
- **CORS**: Configurable origins
- **Input Validation**: Request size and content validation
- **Content Moderation**: Basic keyword filtering
- **Secure Storage**: Encrypted cloud storage options