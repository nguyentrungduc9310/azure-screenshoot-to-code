# API Gateway Service

A comprehensive API Gateway for the Screenshot to Code application, providing unified access to all microservices with advanced features like circuit breakers, load balancing, rate limiting, and real-time WebSocket support.

## Features

- **Service Orchestration**: Unified API for all downstream microservices
- **Circuit Breakers**: Fault tolerance with automatic failover
- **Load Balancing**: Multiple strategies (round-robin, weighted, least connections)
- **Rate Limiting**: Request throttling with Redis backend
- **Authentication**: JWT and Azure AD integration
- **WebSocket Support**: Real-time streaming for code and image generation
- **Comprehensive Monitoring**: Structured logging, metrics, and health checks
- **API Documentation**: Auto-generated OpenAPI/Swagger documentation

## Architecture

### Core Components

- **FastAPI Application**: Main API gateway with ASGI support
- **Service Client**: HTTP client with circuit breakers and retry logic
- **Middleware Stack**: Authentication, rate limiting, logging, CORS
- **WebSocket Manager**: Real-time connection management
- **Health Monitoring**: Multi-level health checks and diagnostics

### Downstream Services

- **Code Generator Service**: AI-powered code generation from screenshots  
- **Image Generator Service**: AI image generation (DALL-E, Flux)
- **Data Layer**: Database, caching, and storage services

## Quick Start

### Installation

```bash
cd services/api-gateway
pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
# Edit .env with your configuration
```

### Development

```bash
# Start in development mode
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or using the FastAPI CLI
fastapi dev app/main.py --host 0.0.0.0 --port 8000
```

### Production

```bash
# Build Docker image
docker build -t api-gateway .

# Run container
docker run -p 8000:8000 --env-file .env api-gateway
```

## Configuration

### Required Environment Variables

**Service Configuration**:
```bash
SERVICE_NAME=api-gateway
ENVIRONMENT=production  # development, testing, staging, production
LOG_LEVEL=INFO
```

**API Configuration**:
```bash
API_HOST=0.0.0.0
API_PORT=8000
API_PREFIX=/api/v1
```

**Downstream Services**:
```bash
CODE_GENERATOR_SERVICE_URL=http://localhost:8002
IMAGE_GENERATOR_SERVICE_URL=http://localhost:8003
```

### Optional Configuration

**Authentication**:
```bash
ENABLE_AUTHENTICATION=true
JWT_SECRET=your-jwt-secret
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
```

**Circuit Breakers**:
```bash
CIRCUIT_BREAKER_ENABLED=true
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_TIMEOUT_SECONDS=60
```

**Rate Limiting**:
```bash
ENABLE_RATE_LIMITING=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60
```

## API Endpoints

### Health Endpoints

- `GET /health` - Basic health check
- `GET /health/live` - Kubernetes liveness probe
- `GET /health/ready` - Kubernetes readiness probe  
- `GET /health/detailed` - Detailed health with metrics

### Code Generation

- `POST /api/v1/code/generate` - Generate code from screenshot
- `POST /api/v1/code/upload-and-generate` - Upload image and generate code
- `GET /api/v1/code/generation/{id}` - Get generation status
- `GET /api/v1/code/variants` - Get available code variants
- `POST /api/v1/code/refine/{id}` - Refine generated code

### Image Generation

- `POST /api/v1/images/generate` - Generate images from prompt
- `GET /api/v1/images/generation/{id}` - Get generation status
- `GET /api/v1/images/providers` - Get available providers
- `POST /api/v1/images/batch-generate` - Batch image generation
- `GET /api/v1/images/usage/stats` - Usage statistics
- `DELETE /api/v1/images/generation/{id}` - Delete generated images

### WebSocket

- `WS /api/v1/ws` - WebSocket endpoint for real-time updates

## Usage Examples

### Code Generation

```python
import requests

# Generate code from screenshot
response = requests.post('http://localhost:8000/api/v1/code/generate', json={
    "image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD...",
    "code_stack": "react_tailwind",
    "generation_type": "create",
    "should_generate_images": true
})

print(response.json())
```

### Image Generation

```python
import requests

# Generate image from prompt
response = requests.post('http://localhost:8000/api/v1/images/generate', json={
    "prompt": "A modern web interface with clean design",
    "provider": "dalle3",
    "size": "1024x1024",
    "num_images": 1
})

print(response.json())
```

### WebSocket Connection

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws?connection_id=client123');

ws.onopen = function() {
    console.log('Connected to API Gateway');
    
    // Subscribe to generation updates
    ws.send(JSON.stringify({
        type: 'subscribe_generation',
        generation_id: 'gen_123'
    }));
};

ws.onmessage = function(event) {
    const message = JSON.parse(event.data);
    console.log('Received:', message);
};
```

## Circuit Breaker Configuration

The API Gateway includes sophisticated circuit breaker functionality:

```python
# Circuit breaker states
CLOSED    # Normal operation
OPEN      # Failing, requests blocked
HALF_OPEN # Testing recovery

# Configuration options
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5      # Failures before opening
CIRCUIT_BREAKER_TIMEOUT_SECONDS=60       # How long to stay open
CIRCUIT_BREAKER_RETRY_TIMEOUT=30         # When to try half-open
```

## Load Balancing Strategies

Multiple load balancing algorithms are supported:

- **Round Robin**: Distributes requests evenly across endpoints
- **Weighted Round Robin**: Uses weights to favor certain endpoints
- **Least Connections**: Routes to endpoint with fewest active connections
- **Random**: Randomly selects endpoints

```bash
LOAD_BALANCING_STRATEGY=round_robin  # round_robin, weighted_round_robin, least_connections, random
```

## Rate Limiting

Flexible rate limiting with Redis backend:

- **Per-User Limiting**: Authenticated users get individual limits
- **IP-Based Limiting**: Fallback for unauthenticated requests
- **Sliding Window**: More accurate than fixed windows
- **Custom Headers**: Returns limit information in response headers

## Authentication

Supports multiple authentication methods:

### JWT Authentication

```bash
ENABLE_AUTHENTICATION=true
JWT_SECRET=your-secret-key
JWT_ALGORITHM=HS256
```

### Azure AD Integration

```bash
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
```

## WebSocket Features

Real-time communication with advanced features:

- **Connection Management**: Automatic connection tracking
- **User-Based Messaging**: Send messages to specific users
- **Generation Streaming**: Real-time progress updates
- **Error Handling**: Graceful error recovery
- **Connection Persistence**: Automatic reconnection support

## Monitoring and Observability

### Structured Logging

All logs include:
- Correlation IDs for request tracking
- Performance metrics (response times)
- User context and security events
- Error details with stack traces

### Health Checks

Multiple health check levels:
- **Liveness**: Service is running
- **Readiness**: Service can handle requests
- **Detailed**: Full diagnostic information

### Metrics

Built-in metrics collection:
- Request/response times
- Circuit breaker states
- Rate limiting statistics
- WebSocket connection counts

## Security Features

### Input Validation
- Pydantic models for request validation
- File type validation for uploads
- Size limits on requests and files

### Security Headers
- CORS configuration
- Security header middleware
- Trusted host validation

### Rate Limiting
- IP and user-based limiting
- Configurable time windows
- Redis-backed storage

## Docker Support

### Building

```bash
docker build -t api-gateway .
```

### Running

```bash
docker run -p 8000:8000 \
  -e CODE_GENERATOR_SERVICE_URL=http://code-generator:8002 \
  -e IMAGE_GENERATOR_SERVICE_URL=http://image-generator:8003 \
  api-gateway
```

### Docker Compose

```yaml
version: '3.8'
services:
  api-gateway:
    build: .
    ports:
      - "8000:8000"
    environment:
      - CODE_GENERATOR_SERVICE_URL=http://code-generator:8002
      - IMAGE_GENERATOR_SERVICE_URL=http://image-generator:8003
    depends_on:
      - code-generator
      - image-generator
      - redis
```

## Development

### Project Structure

```
app/
├── core/
│   └── config.py          # Configuration management
├── middleware/
│   ├── auth.py           # Authentication middleware
│   ├── logging.py        # Request logging
│   ├── rate_limit.py     # Rate limiting
│   └── request_id.py     # Request ID tracking
├── routes/
│   ├── health.py         # Health check endpoints
│   ├── code_generation.py # Code generation routes
│   ├── image_generation.py # Image generation routes
│   └── websocket.py      # WebSocket endpoints
├── services/
│   └── service_client.py # Downstream service client
└── main.py              # FastAPI application
```

### Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_health.py
```

### Code Quality

```bash
# Format code
black app/

# Sort imports
isort app/

# Lint code
flake8 app/

# Type checking
mypy app/
```

## Performance Optimization

### Connection Pooling
- HTTP connection reuse
- Configurable pool sizes
- Automatic cleanup

### Caching
- Response caching for static endpoints
- Circuit breaker state caching
- Service discovery caching

### Compression
- GZip compression for responses
- Request/response optimization
- WebSocket message compression

## Troubleshooting

### Common Issues

**Circuit Breaker Open**:
```bash
# Check downstream service health
curl http://localhost:8000/api/v1/health/detailed

# Reset circuit breaker (restart service)
docker restart api-gateway
```

**Rate Limiting Issues**:
```bash
# Check Redis connection
redis-cli ping

# Monitor rate limit headers
curl -i http://localhost:8000/api/v1/health
```

**Authentication Failures**:
```bash
# Verify JWT secret configuration
echo $JWT_SECRET

# Test token validation
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/v1/health
```

### Debugging

Enable debug logging:
```bash
LOG_LEVEL=DEBUG uvicorn app.main:app --reload
```

Monitor real-time logs:
```bash
docker logs -f api-gateway
```

## License

MIT License - see LICENSE file for details.