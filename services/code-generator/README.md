# Code Generator Service

A FastAPI microservice for generating code from screenshots using multiple AI providers (OpenAI, Azure OpenAI, Anthropic Claude, Google Gemini).

## Features

- **Multi-Provider Support**: OpenAI, Azure OpenAI, Claude, Gemini
- **Multiple Code Stacks**: HTML+Tailwind, React+Tailwind, Vue+Tailwind, Bootstrap, Ionic+Tailwind, SVG
- **Streaming Support**: Real-time code generation via WebSocket and HTTP streaming
- **Multi-Variant Generation**: Generate multiple code variants simultaneously
- **Comprehensive Monitoring**: Structured logging, health checks, correlation tracking
- **Authentication**: Azure AD integration
- **Docker Support**: Containerized deployment

## API Endpoints

### REST API

- `GET /` - Service information
- `GET /health/` - Health check
- `GET /health/ready` - Readiness check
- `GET /health/live` - Liveness check
- `GET /api/v1/providers` - Available AI providers
- `GET /api/v1/stacks` - Supported code stacks
- `POST /api/v1/generate` - Generate code from image
- `POST /api/v1/generate/stream` - Stream code generation

### WebSocket API

- `WS /api/v1/ws/generate` - Real-time code generation
- `WS /api/v1/ws/multi-generate` - Multi-variant generation

## Quick Start

### Development

1. **Clone and setup**:
   ```bash
   cd services/code-generator
   cp .env.example .env
   # Edit .env with your API keys
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the service**:
   ```bash
   python -m uvicorn app.main:app --reload --port 8002
   ```

### Docker

1. **Build and run**:
   ```bash
   docker-compose up --build
   ```

2. **Access the service**:
   - API: http://localhost:8002
   - Docs: http://localhost:8002/docs

## Configuration

### Required Environment Variables

At least one AI provider must be configured:

**OpenAI**:
```bash
OPENAI_API_KEY=your-key-here
```

**Anthropic Claude**:
```bash
ANTHROPIC_API_KEY=your-key-here
```

**Google Gemini**:
```bash
GEMINI_API_KEY=your-key-here
```

**Azure OpenAI**:
```bash
AZURE_OPENAI_API_KEY=your-key-here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment-name
```

### Optional Configuration

```bash
# Service
ENVIRONMENT=development
LOG_LEVEL=INFO
API_PORT=8002

# AI Providers
ENABLED_PROVIDERS=claude,openai,gemini
DEFAULT_PROVIDER=claude

# Code Generation
DEFAULT_STACK=html_tailwind
MAX_VARIANTS=2
ENABLE_CACHING=true

# Security
ENABLE_AUTHENTICATION=false
ALLOWED_ORIGINS=http://localhost:3000
```

## API Usage Examples

### Generate Code (REST)

```bash
curl -X POST "http://localhost:8002/api/v1/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "image_data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
    "code_stack": "html_tailwind",
    "provider": "claude",
    "additional_instructions": "Make it responsive"
  }'
```

### Stream Code Generation

```bash
curl -X POST "http://localhost:8002/api/v1/generate/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "image_data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
    "code_stack": "react_tailwind",
    "stream": true
  }'
```

### WebSocket Usage

```javascript
const ws = new WebSocket('ws://localhost:8002/api/v1/ws/generate');

ws.onopen = () => {
  ws.send(JSON.stringify({
    image_data_url: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...',
    code_stack: 'html_tailwind',
    provider: 'claude'
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'chunk') {
    console.log('Code chunk:', data.content);
  } else if (data.type === 'complete') {
    console.log('Final code:', data.code);
  }
};
```

## Supported Code Stacks

- **html_tailwind**: HTML with Tailwind CSS
- **html_css**: HTML with vanilla CSS
- **react_tailwind**: React with Tailwind CSS
- **vue_tailwind**: Vue.js with Tailwind CSS
- **bootstrap**: HTML with Bootstrap
- **ionic_tailwind**: Ionic with Tailwind CSS
- **svg**: SVG graphics

## Health Checks

- **Health**: `GET /health/` - Overall service health
- **Readiness**: `GET /health/ready` - Ready to accept requests
- **Liveness**: `GET /health/live` - Service is alive

## Monitoring

The service includes comprehensive monitoring:

- **Structured Logging**: JSON-formatted logs with correlation IDs
- **Application Insights**: Integration with Azure Application Insights
- **Health Checks**: Kubernetes-compatible health endpoints
- **Request Tracking**: Correlation IDs for request tracing

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
  "message": "Invalid image data URL format",
  "correlation_id": "abc123-def456-ghi789"
}
```

## Development

### Project Structure

```
app/
├── core/
│   └── config.py          # Configuration settings
├── middleware/
│   └── validation.py      # Request validation
├── routes/
│   ├── code_generation.py # Code generation endpoints
│   └── health.py          # Health check endpoints
├── services/
│   ├── provider_manager.py # AI provider management
│   └── prompt_engine.py   # Prompt generation
└── main.py                # FastAPI application
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

The service is containerized and can be deployed using Docker:

```bash
# Build image
docker build -t code-generator:latest .

# Run container
docker run -p 8002:8002 --env-file .env code-generator:latest
```

### Kubernetes

Kubernetes manifests are available in the `k8s/` directory:

```bash
kubectl apply -f k8s/
```

## Performance

- **Concurrent Requests**: Configurable (default: 10)
- **Request Timeout**: 120 seconds default
- **Streaming**: Real-time response streaming
- **Caching**: Optional response caching
- **Multi-Variant**: Parallel generation support

## Security

- **Authentication**: Azure AD integration
- **CORS**: Configurable origins
- **Input Validation**: Request size and format validation
- **Error Handling**: Secure error responses without sensitive data