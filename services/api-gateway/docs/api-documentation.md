# API Gateway Documentation

## Overview

The API Gateway serves as the unified entry point for all Screenshot-to-Code microservices, providing a single API interface with advanced features like authentication, rate limiting, circuit breakers, and real-time WebSocket support.

## Base URL

- **Development**: `http://localhost:8000`
- **Production**: `https://your-domain.com`

## Authentication

### JWT Bearer Token

All protected endpoints require a valid JWT token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

### Azure AD Integration

For enterprise environments, Azure AD authentication is supported. Configure your Azure tenant and client IDs in the environment variables.

## Rate Limiting

API requests are subject to rate limiting:

- **Default Limit**: 100 requests per minute per user/IP
- **Rate Limit Headers**: All responses include rate limit information
  - `X-RateLimit-Limit`: Maximum requests allowed
  - `X-RateLimit-Remaining`: Remaining requests in current window
  - `X-RateLimit-Reset`: Time when rate limit resets

## Error Handling

All API responses follow a consistent error format:

```json
{
  "error": "Description of the error",
  "status_code": 400,
  "correlation_id": "uuid-correlation-id",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Common HTTP Status Codes

- `200` - Success
- `201` - Created
- `400` - Bad Request (validation error)
- `401` - Unauthorized (missing or invalid token)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `429` - Too Many Requests (rate limited)
- `500` - Internal Server Error
- `503` - Service Unavailable (circuit breaker open)

## API Endpoints

### Health Check Endpoints

#### GET /health

Basic health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "correlation_id": "uuid-correlation-id",
  "service": "api-gateway",
  "version": "1.0.0",
  "environment": "production",
  "downstream_services": {
    "code_generator": "healthy",
    "image_generator": "healthy"
  },
  "circuit_breakers": {
    "code_generator": {
      "state": "closed",
      "failure_count": 0,
      "failure_threshold": 5
    }
  }
}
```

#### GET /health/live

Kubernetes liveness probe endpoint.

**Response:**
```json
{
  "status": "alive",
  "timestamp": "2024-01-15T10:30:00Z",
  "service": "api-gateway"
}
```

#### GET /health/ready

Kubernetes readiness probe endpoint.

**Response:**
```json
{
  "status": "ready",
  "timestamp": "2024-01-15T10:30:00Z",
  "service": "api-gateway",
  "dependencies": {
    "code_generator": "healthy",
    "image_generator": "healthy"
  }
}
```

### Code Generation Endpoints

#### POST /api/v1/code/generate

Generate code from a screenshot image.

**Request Body:**
```json
{
  "image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD...",
  "code_stack": "react_tailwind",
  "generation_type": "create",
  "additional_instructions": "Make it responsive and add dark mode support",
  "should_generate_images": true,
  "user_preferences": {
    "style": "modern",
    "accessibility": true
  }
}
```

**Response:**
```json
{
  "id": "gen_abc123",
  "code": "import React from 'react';\n\nconst Component = () => {\n  return (\n    <div className=\"container mx-auto p-4\">\n      <!-- Generated code -->\n    </div>\n  );\n};\n\nexport default Component;",
  "status": "completed",
  "code_stack": "react_tailwind",
  "provider": "openai",
  "generation_time_ms": 3500,
  "token_usage": {
    "prompt_tokens": 1200,
    "completion_tokens": 800,
    "total_tokens": 2000
  },
  "images_generated": [
    "https://storage.example.com/images/icon1.png",
    "https://storage.example.com/images/bg.jpg"
  ]
}
```

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/code/generate" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD...",
    "code_stack": "react_tailwind",
    "generation_type": "create"
  }'
```

#### POST /api/v1/code/upload-and-generate

Upload an image file and generate code.

**Form Data:**
- `file`: Image file (PNG, JPG, JPEG, WebP)
- `code_stack`: Target framework (html_tailwind, react_tailwind, vue_tailwind, etc.)
- `generation_type`: create, update, refine
- `additional_instructions`: Optional instructions
- `should_generate_images`: Boolean

**Response:** Same as `/code/generate`

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/code/upload-and-generate" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@screenshot.png" \
  -F "code_stack=react_tailwind" \
  -F "generation_type=create"
```

#### GET /api/v1/code/generation/{generation_id}

Get the status and result of a code generation request.

**Response:**
```json
{
  "id": "gen_abc123",
  "status": "completed",
  "code": "<!-- Generated code -->",
  "code_stack": "react_tailwind",
  "provider": "openai",
  "created_at": "2024-01-15T10:30:00Z",
  "completed_at": "2024-01-15T10:30:03Z",
  "generation_time_ms": 3500
}
```

#### GET /api/v1/code/variants

Get available code generation variants and templates.

**Response:**
```json
{
  "variants": [
    {
      "id": "html_tailwind",
      "name": "HTML + Tailwind CSS",
      "description": "Static HTML with Tailwind CSS classes",
      "features": ["responsive", "modern_css", "semantic_html"]
    },
    {
      "id": "react_tailwind",
      "name": "React + Tailwind CSS",
      "description": "React components with Tailwind CSS",
      "features": ["components", "hooks", "typescript", "responsive"]
    }
  ]
}
```

#### POST /api/v1/code/refine/{generation_id}

Refine previously generated code with additional instructions.

**Request Body:**
```json
{
  "instructions": "Add a dark mode toggle button",
  "refinement_type": "feature_addition",
  "preserve_structure": true
}
```

### Image Generation Endpoints

#### POST /api/v1/images/generate

Generate images from a text prompt.

**Request Body:**
```json
{
  "prompt": "A modern web interface with clean design and blue color scheme",
  "provider": "dalle3",
  "size": "1024x1024",
  "quality": "hd",
  "style": "natural",
  "num_images": 1,
  "project_id": "proj_xyz789"
}
```

**Response:**
```json
{
  "id": "img_def456",
  "prompt": "A modern web interface with clean design and blue color scheme",
  "provider": "dalle3",
  "status": "completed",
  "images": [
    {
      "url": "https://storage.example.com/images/generated/img_def456_1.png",
      "size": "1024x1024",
      "format": "png",
      "metadata": {
        "created_at": "2024-01-15T10:30:00Z",
        "file_size": 2048576
      }
    }
  ],
  "generation_time_ms": 5000,
  "cost_estimate": 0.04
}
```

#### POST /api/v1/images/batch-generate

Generate multiple images in a single batch request.

**Request Body:**
```json
{
  "requests": [
    {
      "prompt": "App icon with blue gradient",
      "size": "512x512"
    },
    {
      "prompt": "Hero background image",
      "size": "1920x1080"
    }
  ]
}
```

#### GET /api/v1/images/providers

Get available image generation providers and their capabilities.

**Response:**
```json
{
  "providers": [
    {
      "id": "dalle3",
      "name": "DALL-E 3",
      "description": "OpenAI's latest image generation model",
      "supported_sizes": ["1024x1024", "1024x1792", "1792x1024"],
      "supported_qualities": ["standard", "hd"],
      "max_images_per_request": 1,
      "cost_per_image": 0.04
    },
    {
      "id": "flux_schnell",
      "name": "Flux Schnell",
      "description": "Fast image generation with Flux",
      "supported_sizes": ["512x512", "1024x1024"],
      "max_images_per_request": 4,
      "cost_per_image": 0.02
    }
  ]
}
```

### WebSocket API

#### WS /api/v1/ws

WebSocket endpoint for real-time communication.

**Connection Parameters:**
- `connection_id`: Unique identifier for the connection
- `user_id`: (Optional) User ID for authenticated connections

**Message Types:**

**Ping/Pong:**
```json
// Client -> Server
{
  "type": "ping"
}

// Server -> Client
{
  "type": "pong",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Subscribe to Generation Updates:**
```json
// Client -> Server
{
  "type": "subscribe_generation",
  "generation_id": "gen_abc123"
}

// Server -> Client
{
  "type": "subscription_confirmed",
  "generation_id": "gen_abc123",
  "message": "Subscribed to generation gen_abc123"
}
```

**Streaming Code Generation:**
```json
// Client -> Server
{
  "type": "stream_code_generation",
  "params": {
    "image": "data:image/jpeg;base64,...",
    "code_stack": "react_tailwind"
  }
}

// Server -> Client (Progress Updates)
{
  "type": "generation_progress",
  "generation_type": "code",
  "progress": 50,
  "status": "processing",
  "message": "Code generation 50% complete"
}

// Server -> Client (Completion)
{
  "type": "generation_completed",
  "generation_type": "code",
  "status": "completed",
  "result": {
    "id": "gen_abc123",
    "code": "<!-- Generated code -->",
    "generation_time_ms": 3500
  }
}
```

## SDK Examples

### JavaScript/TypeScript

```typescript
import axios from 'axios';

class ScreenshotToCodeAPI {
  private baseURL: string;
  private token: string;

  constructor(baseURL: string, token: string) {
    this.baseURL = baseURL;
    this.token = token;
  }

  async generateCode(params: {
    image: string;
    codeStack: string;
    generationType?: string;
    additionalInstructions?: string;
  }) {
    const response = await axios.post(
      `${this.baseURL}/api/v1/code/generate`,
      {
        image: params.image,
        code_stack: params.codeStack,
        generation_type: params.generationType || 'create',
        additional_instructions: params.additionalInstructions
      },
      {
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json'
        }
      }
    );
    return response.data;
  }

  async generateImage(prompt: string, options: {
    provider?: string;
    size?: string;
    quality?: string;
  } = {}) {
    const response = await axios.post(
      `${this.baseURL}/api/v1/images/generate`,
      {
        prompt,
        provider: options.provider || 'dalle3',
        size: options.size || '1024x1024',
        quality: options.quality || 'standard'
      },
      {
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json'
        }
      }
    );
    return response.data;
  }

  connectWebSocket(connectionId: string, userId?: string) {
    const wsUrl = `${this.baseURL.replace('http', 'ws')}/api/v1/ws?connection_id=${connectionId}${userId ? `&user_id=${userId}` : ''}`;
    return new WebSocket(wsUrl);
  }
}

// Usage
const api = new ScreenshotToCodeAPI('http://localhost:8000', 'your-jwt-token');

// Generate code
const codeResult = await api.generateCode({
  image: 'data:image/jpeg;base64,...',
  codeStack: 'react_tailwind'
});

// Generate image
const imageResult = await api.generateImage('A modern button design', {
  size: '512x512'
});

// WebSocket connection
const ws = api.connectWebSocket('client123', 'user456');
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('Received:', message);
};
```

### Python

```python
import requests
import websocket
import json

class ScreenshotToCodeAPI:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.token = token
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
    
    def generate_code(self, image: str, code_stack: str, **kwargs):
        data = {
            'image': image,
            'code_stack': code_stack,
            'generation_type': kwargs.get('generation_type', 'create'),
            'additional_instructions': kwargs.get('additional_instructions'),
            'should_generate_images': kwargs.get('should_generate_images', False)
        }
        
        response = requests.post(
            f'{self.base_url}/api/v1/code/generate',
            json=data,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def generate_image(self, prompt: str, **kwargs):
        data = {
            'prompt': prompt,
            'provider': kwargs.get('provider', 'dalle3'),
            'size': kwargs.get('size', '1024x1024'),
            'quality': kwargs.get('quality', 'standard'),
            'num_images': kwargs.get('num_images', 1)
        }
        
        response = requests.post(
            f'{self.base_url}/api/v1/images/generate',
            json=data,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def upload_and_generate(self, file_path: str, code_stack: str):
        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {
                'code_stack': code_stack,
                'generation_type': 'create'
            }
            
            response = requests.post(
                f'{self.base_url}/api/v1/code/upload-and-generate',
                files=files,
                data=data,
                headers={'Authorization': f'Bearer {self.token}'}
            )
        response.raise_for_status()
        return response.json()

# Usage
api = ScreenshotToCodeAPI('http://localhost:8000', 'your-jwt-token')

# Generate code
result = api.generate_code(
    image='data:image/jpeg;base64,...',
    code_stack='react_tailwind',
    additional_instructions='Make it responsive'
)

# Upload file and generate
result = api.upload_and_generate('screenshot.png', 'html_tailwind')
```

## Testing

### Health Check Test

```bash
# Test basic health
curl -f http://localhost:8000/health

# Test detailed health
curl -f http://localhost:8000/health/detailed
```

### Authentication Test

```bash
# Test without token (should return 401)
curl -X POST http://localhost:8000/api/v1/code/generate

# Test with valid token
curl -X POST "http://localhost:8000/api/v1/code/generate" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"image": "data:image/jpeg;base64,test", "code_stack": "html_tailwind"}'
```

### Rate Limiting Test

```bash
# Make multiple requests to trigger rate limiting
for i in {1..110}; do
  curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/health
done
```

### WebSocket Test

```javascript
// Browser console test
const ws = new WebSocket('ws://localhost:8000/api/v1/ws?connection_id=test123');
ws.onopen = () => console.log('Connected');
ws.onmessage = (event) => console.log('Message:', JSON.parse(event.data));
ws.send(JSON.stringify({type: 'ping'}));
```

## Monitoring and Debugging

### Correlation ID Tracking

Every request includes a correlation ID for tracking across services:

```bash
# The correlation ID is returned in response headers
curl -i http://localhost:8000/health
# Look for: X-Correlation-ID: uuid-here
```

### Circuit Breaker Status

Monitor circuit breaker status:

```bash
curl http://localhost:8000/health/detailed | jq '.circuit_breakers'
```

### Rate Limit Headers

Monitor rate limiting:

```bash
curl -i http://localhost:8000/health | grep -i ratelimit
# X-RateLimit-Limit: 100
# X-RateLimit-Remaining: 99
# X-RateLimit-Reset: 1705315800
```

## Performance Considerations

### Request Size Limits

- **Maximum request size**: 100MB (configurable)
- **Image uploads**: Recommended max 10MB per image
- **Batch requests**: Limited to 10 items per batch

### Response Times

- **Health checks**: < 100ms
- **Code generation**: 2-10 seconds (depends on complexity)
- **Image generation**: 3-15 seconds (depends on provider)

### Caching

- Circuit breaker states are cached
- Service discovery results are cached for 30 seconds
- Static responses (variants, providers) are cached for 5 minutes

## Troubleshooting

### Common Issues

**503 Service Unavailable**
- Circuit breaker is open for downstream service
- Check `/health/detailed` for service status

**429 Too Many Requests**
- Rate limit exceeded
- Check rate limit headers for reset time

**401 Unauthorized**
- Missing or invalid JWT token
- Verify token is properly formatted and not expired

**Connection Refused (WebSocket)**
- WebSocket support may be disabled
- Check `ENABLE_WEBSOCKET=true` in configuration

### Debug Mode

Enable debug logging:
```bash
LOG_LEVEL=DEBUG uvicorn app.main:app --reload
```

### Health Monitoring

```bash
# Monitor all services
watch -n 5 'curl -s http://localhost:8000/health/detailed | jq .downstream_services'

# Monitor circuit breakers
watch -n 5 'curl -s http://localhost:8000/health/detailed | jq .circuit_breakers'
```