# TASK-005: Development Environment Configuration

**Date**: January 2024  
**Assigned**: Senior Full-stack Developer 2  
**Status**: IN PROGRESS  
**Effort**: 8 hours  

---

## Prerequisites

Before starting development environment setup, ensure you have completed:
- ✅ Azure infrastructure setup (Task 4) 
- ✅ Access to Azure OpenAI services
- ✅ Microsoft 365 tenant with Power Platform access
- ✅ Service principal credentials for CI/CD

---

## Phase 1: Local Development Tools Setup

### 1.1 Required Development Tools

```bash
# Install development tools (macOS/Linux)

# Node.js & npm (for frontend development)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
source ~/.bashrc
nvm install 18.18.0
nvm use 18.18.0

# Python & Poetry (for backend development)
curl -sSL https://install.python-poetry.org | python3 -
export PATH="$HOME/.local/bin:$PATH"

# Docker & Docker Compose
# Download Docker Desktop from: https://docs.docker.com/desktop/
docker --version
docker-compose --version

# Azure CLI (if not already installed)
curl -sL https://aka.ms/InstallAzureCLI | sudo bash

# Terraform (for infrastructure as code)
curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo apt-key add -
sudo apt-add-repository "deb [arch=$(dpkg --print-architecture)] https://apt.releases.hashicorp.com $(lsb_release -cs) main"
sudo apt update && sudo apt install terraform

# GitHub CLI (for repository management)
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update && sudo apt install gh

# Kubernetes CLI (for container orchestration)
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Power Platform CLI (for Copilot Studio integration)
# Download from: https://aka.ms/PowerPlatformCLI
```

### 1.2 IDE Configuration

```bash
# VS Code Extensions for development
code --install-extension ms-python.python
code --install-extension ms-vscode.vscode-typescript-next
code --install-extension ms-azuretools.vscode-docker
code --install-extension ms-kubernetes-tools.vscode-kubernetes-tools
code --install-extension ms-vscode.azure-account
code --install-extension ms-azure-devops.azure-pipelines
code --install-extension bradlc.vscode-tailwindcss
code --install-extension esbenp.prettier-vscode
code --install-extension ms-python.flake8
code --install-extension ms-python.black-formatter

# Create VS Code workspace configuration
mkdir -p .vscode
```

### 1.3 VS Code Workspace Configuration

```json
# .vscode/settings.json
{
  "python.defaultInterpreterPath": "./.venv/bin/python",
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "typescript.preferences.importModuleSpecifier": "relative",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  },
  "files.exclude": {
    "**/.venv": true,
    "**/node_modules": true,
    "**/__pycache__": true,
    "**/.pytest_cache": true
  },
  "docker.defaultRegistryPath": "screenshottocode.azurecr.io"
}
```

---

## Phase 2: Project Structure Setup

### 2.1 Create Microservices Directory Structure

```bash
# Create new microservices architecture
mkdir -p services/{api-gateway,image-processor,code-generator,image-generator,nlp-processor,evaluation}
mkdir -p infrastructure/{terraform,k8s,docker}
mkdir -p shared/{types,utils,config}
mkdir -p tests/{integration,e2e,performance}
mkdir -p docs/{api,architecture,deployment}

# Create service-specific directories
for service in api-gateway image-processor code-generator image-generator nlp-processor evaluation; do
  mkdir -p services/$service/{app,tests,docker,docs}
  mkdir -p services/$service/app/{routes,models,services,utils}
done

# Create shared libraries
mkdir -p shared/{auth,monitoring,config,types}
```

### 2.2 Initialize Service Templates

```bash
# Create FastAPI service template
cat > services/api-gateway/app/main.py << 'EOF'
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import uvicorn
import os
from shared.monitoring import setup_monitoring
from shared.auth import setup_authentication

app = FastAPI(
    title="Screenshot-to-Code API Gateway",
    description="API Gateway for Screenshot-to-Code microservices",
    version="1.0.0"
)

# Security middleware
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["localhost", "*.azurecontainerapps.io"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "https://copilotstudio.microsoft.com").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Setup monitoring and auth
setup_monitoring(app)
setup_authentication(app)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "api-gateway"}

@app.get("/")
async def root():
    return {"message": "Screenshot-to-Code API Gateway", "version": "1.0.0"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
EOF

# Create Docker template
cat > services/api-gateway/docker/Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY shared/ ./shared/

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Start application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

# Create requirements.txt template
cat > services/api-gateway/requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
python-multipart==0.0.6
python-jose[cryptography]==3.3.0
azure-identity==1.15.0
azure-keyvault-secrets==4.7.0
opencensus-ext-azure==1.1.11
opencensus-ext-flask==0.8.0
redis==5.0.1
httpx==0.25.2
EOF
```

---

## Phase 3: Development Environment Configuration

### 3.1 Create Development Docker Compose

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  api-gateway:
    build: 
      context: .
      dockerfile: services/api-gateway/docker/Dockerfile
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=development
      - LOG_LEVEL=debug
    volumes:
      - ./services/api-gateway:/app
      - ./shared:/app/shared
    depends_on:
      - redis-dev
      - postgres-dev

  image-processor:
    build:
      context: .
      dockerfile: services/image-processor/docker/Dockerfile  
    ports:
      - "8001:8000"
    environment:
      - ENVIRONMENT=development
    volumes:
      - ./services/image-processor:/app
      - ./shared:/app/shared

  code-generator:
    build:
      context: .
      dockerfile: services/code-generator/docker/Dockerfile
    ports:
      - "8002:8000" 
    environment:
      - ENVIRONMENT=development
    volumes:
      - ./services/code-generator:/app
      - ./shared:/app/shared

  # Development databases
  redis-dev:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
    volumes:
      - redis-dev-data:/data

  postgres-dev:
    image: postgres:15-alpine
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_DB=screenshot_to_code_dev
      - POSTGRES_USER=dev_user
      - POSTGRES_PASSWORD=dev_password
    volumes:
      - postgres-dev-data:/var/lib/postgresql/data

volumes:
  redis-dev-data:
  postgres-dev-data:
```

### 3.2 Environment Configuration

```bash
# Create environment template files
cat > .env.template << 'EOF'
# Development Environment Configuration
ENVIRONMENT=development
LOG_LEVEL=info

# Azure Configuration
AZURE_CLIENT_ID=your-managed-identity-client-id
AZURE_KEY_VAULT_NAME=your-key-vault-name
AZURE_TENANT_ID=your-tenant-id
AZURE_SUBSCRIPTION_ID=your-subscription-id

# Database Configuration
DATABASE_URL=postgresql://dev_user:dev_password@localhost:5432/screenshot_to_code_dev
REDIS_URL=redis://localhost:6379/0

# API Keys (retrieved from Key Vault in production)
OPENAI_API_KEY=from-key-vault
ANTHROPIC_API_KEY=from-key-vault
GEMINI_API_KEY=from-key-vault
REPLICATE_API_KEY=from-key-vault

# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY=from-key-vault
AZURE_OPENAI_ENDPOINT=from-key-vault
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Storage Configuration
AZURE_STORAGE_CONNECTION_STRING=from-key-vault
AZURE_STORAGE_CONTAINER_NAME=images

# Monitoring
APPLICATION_INSIGHTS_CONNECTION_STRING=from-key-vault

# Security
JWT_SECRET_KEY=your-jwt-secret-key
CORS_ALLOWED_ORIGINS=http://localhost:3000,https://copilotstudio.microsoft.com

# Power Platform
COPILOT_STUDIO_TENANT_ID=your-copilot-studio-tenant
COPILOT_STUDIO_ENVIRONMENT_ID=your-environment-id
EOF

# Create development environment file
cp .env.template .env.development

# Create production environment template
cat > .env.production.template << 'EOF'
# Production Environment Configuration
ENVIRONMENT=production
LOG_LEVEL=warning

# Azure Configuration (from Azure Key Vault)
AZURE_CLIENT_ID=${MANAGED_IDENTITY_CLIENT_ID}
AZURE_KEY_VAULT_NAME=${KEY_VAULT_NAME}

# All secrets retrieved from Key Vault at runtime
# No sensitive values stored in environment variables
EOF
```

### 3.3 Create Shared Configuration Module

```python
# shared/config/settings.py
from pydantic import BaseSettings, Field
from typing import Optional, List
import os

class Settings(BaseSettings):
    # Environment
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="info", env="LOG_LEVEL")
    
    # Azure Configuration
    azure_client_id: Optional[str] = Field(default=None, env="AZURE_CLIENT_ID")
    azure_tenant_id: Optional[str] = Field(default=None, env="AZURE_TENANT_ID")
    azure_key_vault_name: Optional[str] = Field(default=None, env="AZURE_KEY_VAULT_NAME")
    
    # Database
    database_url: str = Field(env="DATABASE_URL")
    redis_url: str = Field(env="REDIS_URL")
    
    # API Configuration
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")
    
    # CORS
    cors_allowed_origins: List[str] = Field(
        default=["http://localhost:3000"], 
        env="CORS_ALLOWED_ORIGINS"
    )
    
    # Security
    jwt_secret_key: str = Field(env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=30, env="JWT_EXPIRE_MINUTES")
    
    class Config:
        env_file = ".env.development" if os.getenv("ENVIRONMENT", "development") == "development" else ".env.production"
        case_sensitive = False

# Create singleton instance
settings = Settings()
```

---

## Phase 4: CI/CD Pipeline Templates

### 4.1 GitHub Actions Workflow

```yaml
# .github/workflows/build-and-deploy.yml
name: Build and Deploy Screenshot-to-Code

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

env:
  REGISTRY: screenshottocode.azurecr.io
  RESOURCE_GROUP: screenshot-to-code-dev

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        service: [api-gateway, image-processor, code-generator, image-generator, nlp-processor, evaluation]
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        cd services/${{ matrix.service }}
        pip install -r requirements.txt
        pip install pytest pytest-asyncio pytest-cov
    
    - name: Run tests
      run: |
        cd services/${{ matrix.service }}
        pytest tests/ --cov=app --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: services/${{ matrix.service }}/coverage.xml
        flags: ${{ matrix.service }}

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    strategy:
      matrix:
        service: [api-gateway, image-processor, code-generator, image-generator, nlp-processor, evaluation]
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Login to Azure
      uses: azure/login@v1
      with:
        creds: ${{ secrets.AZURE_CREDENTIALS }}
    
    - name: Login to ACR
      run: |
        az acr login --name ${REGISTRY%%.azurecr.io}
    
    - name: Build and push Docker image
      run: |
        docker build -t $REGISTRY/${{ matrix.service }}:${{ github.sha }} -f services/${{ matrix.service }}/docker/Dockerfile .
        docker push $REGISTRY/${{ matrix.service }}:${{ github.sha }}
        docker tag $REGISTRY/${{ matrix.service }}:${{ github.sha }} $REGISTRY/${{ matrix.service }}:latest
        docker push $REGISTRY/${{ matrix.service }}:latest

  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Login to Azure
      uses: azure/login@v1
      with:
        creds: ${{ secrets.AZURE_CREDENTIALS }}
    
    - name: Deploy to Container Apps
      run: |
        # Deploy each service to Azure Container Apps
        for service in api-gateway image-processor code-generator image-generator nlp-processor evaluation; do
          az containerapp update \
            --name screenshot-to-code-$service \
            --resource-group $RESOURCE_GROUP \
            --image $REGISTRY/$service:${{ github.sha }}
        done
```

### 4.2 Azure DevOps Pipeline

```yaml
# azure-pipelines.yml
trigger:
  branches:
    include:
    - main
    - develop

variables:
  azureServiceConnection: 'screenshot-to-code-service-connection'
  containerRegistry: 'screenshottocode.azurecr.io'
  resourceGroup: 'screenshot-to-code-dev'

stages:
- stage: Test
  displayName: 'Run Tests'
  jobs:
  - job: UnitTests
    displayName: 'Unit Tests'
    pool:
      vmImage: 'ubuntu-latest'
    strategy:
      matrix:
        ApiGateway:
          serviceName: 'api-gateway'
        ImageProcessor:
          serviceName: 'image-processor'
        CodeGenerator:
          serviceName: 'code-generator'
    steps:
    - task: UsePythonVersion@0
      inputs:
        versionSpec: '3.11'
    - script: |
        cd services/$(serviceName)
        pip install -r requirements.txt
        pip install pytest pytest-cov
        pytest tests/ --cov=app --cov-report=xml --junitxml=test-results.xml
      displayName: 'Run Tests'
    - task: PublishTestResults@2
      inputs:
        testResultsFiles: 'services/$(serviceName)/test-results.xml'
    - task: PublishCodeCoverageResults@1
      inputs:
        codeCoverageTool: 'Cobertura'
        summaryFileLocation: 'services/$(serviceName)/coverage.xml'

- stage: Build
  displayName: 'Build Images'
  dependsOn: Test
  condition: and(succeeded(), eq(variables['Build.SourceBranch'], 'refs/heads/main'))
  jobs:
  - job: BuildImages
    displayName: 'Build Docker Images'
    pool:
      vmImage: 'ubuntu-latest'
    strategy:
      matrix:
        ApiGateway:
          serviceName: 'api-gateway'
        ImageProcessor:
          serviceName: 'image-processor'
        CodeGenerator:
          serviceName: 'code-generator'
    steps:
    - task: Docker@2
      displayName: 'Build and Push'
      inputs:
        containerRegistry: $(azureServiceConnection)
        repository: '$(serviceName)'
        command: 'buildAndPush'
        Dockerfile: 'services/$(serviceName)/docker/Dockerfile'
        tags: |
          $(Build.BuildId)
          latest
```

---

## Phase 5: Development Scripts and Tools

### 5.1 Development Utility Scripts

```bash
# scripts/dev-setup.sh
#!/bin/bash
set -e

echo "🚀 Setting up Screenshot-to-Code development environment..."

# Load Azure configuration
if [ ! -f "azure-dev-config.env" ]; then
    echo "❌ azure-dev-config.env not found. Please run Azure setup first."
    exit 1
fi

source azure-dev-config.env

# Install dependencies for all services
echo "📦 Installing service dependencies..."
for service in api-gateway image-processor code-generator image-generator nlp-processor evaluation; do
    if [ -f "services/$service/requirements.txt" ]; then
        echo "Installing dependencies for $service..."
        cd services/$service
        python -m venv .venv
        source .venv/bin/activate
        pip install -r requirements.txt
        cd ../..
    fi
done

# Setup development environment file
echo "⚙️ Configuring development environment..."
cp .env.template .env.development

# Replace placeholders with actual Azure values
sed -i "s|your-managed-identity-client-id|$MANAGED_IDENTITY_CLIENT_ID|g" .env.development
sed -i "s|your-key-vault-name|$KEY_VAULT_NAME|g" .env.development
sed -i "s|your-tenant-id|$(az account show --query tenantId -o tsv)|g" .env.development
sed -i "s|your-subscription-id|$SUBSCRIPTION_ID|g" .env.development

# Start development services
echo "🐳 Starting development services..."
docker-compose -f docker-compose.dev.yml up -d redis-dev postgres-dev

echo "✅ Development environment setup complete!"
echo ""
echo "Next steps:"
echo "1. Configure your API keys in .env.development"
echo "2. Run 'scripts/start-dev.sh' to start all services"
echo "3. Access API Gateway at http://localhost:8000"

# scripts/start-dev.sh
#!/bin/bash
set -e

echo "🏃 Starting development services..."

# Start infrastructure services
docker-compose -f docker-compose.dev.yml up -d redis-dev postgres-dev

# Wait for services to be ready
echo "⏳ Waiting for infrastructure services..."
sleep 10

# Start all microservices
echo "🚀 Starting microservices..."
for service in api-gateway image-processor code-generator; do
    if [ -d "services/$service" ]; then
        echo "Starting $service..."
        cd services/$service
        source .venv/bin/activate
        uvicorn app.main:app --host 0.0.0.0 --port $((8000 + $(echo $service | tr -cd '[:digit:]'))) --reload &
        cd ../..
    fi
done

echo "✅ All services started!"
echo "🌐 API Gateway: http://localhost:8000"
echo "🖼️  Image Processor: http://localhost:8001" 
echo "💻 Code Generator: http://localhost:8002"

# scripts/test-all.sh
#!/bin/bash
set -e

echo "🧪 Running tests for all services..."

# Run tests for each service
for service in api-gateway image-processor code-generator image-generator nlp-processor evaluation; do
    if [ -d "services/$service/tests" ]; then
        echo "Testing $service..."
        cd services/$service
        source .venv/bin/activate
        pytest tests/ -v --cov=app --cov-report=term-missing
        cd ../..
    fi
done

echo "✅ All tests completed!"

# scripts/build-all.sh  
#!/bin/bash
set -e

echo "🔨 Building Docker images for all services..."

# Build images for each service
for service in api-gateway image-processor code-generator image-generator nlp-processor evaluation; do
    if [ -f "services/$service/docker/Dockerfile" ]; then
        echo "Building $service..."
        docker build -t screenshot-to-code-$service:latest -f services/$service/docker/Dockerfile .
    fi
done

echo "✅ All images built successfully!"

# Make scripts executable
chmod +x scripts/*.sh
```

### 5.2 Development Monitoring and Debugging

```python
# shared/monitoring/health.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Dict, Any
import psutil
import time

class HealthResponse(BaseModel):
    status: str
    timestamp: float
    service: str
    version: str
    system: Dict[str, Any]

def create_health_router(service_name: str, version: str = "1.0.0") -> APIRouter:
    router = APIRouter()
    
    @router.get("/health", response_model=HealthResponse)
    async def health_check():
        system_info = {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent,
            "uptime": time.time()
        }
        
        return HealthResponse(
            status="healthy",
            timestamp=time.time(),
            service=service_name,
            version=version,
            system=system_info
        )
    
    return router

# shared/monitoring/logging.py
import logging
import json
from datetime import datetime
from typing import Any, Dict

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "service": getattr(record, 'service', 'unknown'),
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_entry)

def setup_logging(service_name: str, log_level: str = "INFO"):
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))
    
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    
    logger.addHandler(handler)
    
    # Add service name to all log records
    logging.getLogger().addFilter(lambda record: setattr(record, 'service', service_name) or True)
```

---

## Phase 6: Testing Infrastructure

### 6.1 Integration Testing Setup

```python
# tests/conftest.py
import pytest
import asyncio
from httpx import AsyncClient
from typing import AsyncGenerator
import pytest_asyncio

# Shared test configuration
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for testing."""
    async with AsyncClient(base_url="http://localhost:8000") as client:
        yield client

@pytest.fixture
def sample_image_data():
    """Sample base64 image data for testing."""
    return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

# tests/integration/test_image_processing.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_image_processing_endpoint(client: AsyncClient, sample_image_data: str):
    response = await client.post(
        "/api/v1/process-image",
        json={"image": sample_image_data, "provider_requirements": {"max_size": 5242880}}
    )
    assert response.status_code == 200
    data = response.json()
    assert "processed_image" in data
    assert "metadata" in data

@pytest.mark.asyncio
async def test_health_endpoints(client: AsyncClient):
    services = ["api-gateway", "image-processor", "code-generator"]
    for i, service in enumerate(services):
        port = 8000 + i
        async with AsyncClient(base_url=f"http://localhost:{port}") as service_client:
            response = await service_client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert service in data["service"]
```

### 6.2 Performance Testing Setup

```python
# tests/performance/load_test.py
import asyncio
import aiohttp
import time
from typing import List

async def make_request(session: aiohttp.ClientSession, url: str, data: dict) -> dict:
    start_time = time.time()
    async with session.post(url, json=data) as response:
        result = await response.json()
        end_time = time.time()
        return {
            "status": response.status,
            "response_time": end_time - start_time,
            "success": response.status == 200
        }

async def load_test(url: str, concurrent_requests: int, total_requests: int):
    sample_data = {
        "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        "provider_requirements": {"max_size": 5242880}
    }
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i in range(total_requests):
            if i % concurrent_requests == 0 and i > 0:
                # Wait for current batch to complete
                results = await asyncio.gather(*tasks)
                tasks = []
                
                # Process results
                success_count = sum(1 for r in results if r["success"])
                avg_response_time = sum(r["response_time"] for r in results) / len(results)
                print(f"Batch {i//concurrent_requests}: {success_count}/{len(results)} successful, avg response time: {avg_response_time:.2f}s")
            
            task = make_request(session, url, sample_data)
            tasks.append(task)
        
        # Process final batch
        if tasks:
            results = await asyncio.gather(*tasks)
            success_count = sum(1 for r in results if r["success"])
            avg_response_time = sum(r["response_time"] for r in results) / len(results)
            print(f"Final batch: {success_count}/{len(results)} successful, avg response time: {avg_response_time:.2f}s")

if __name__ == "__main__":
    asyncio.run(load_test("http://localhost:8001/api/v1/process-image", 10, 100))
```

---

## Phase 7: Documentation Templates

### 7.1 Service Documentation Template

```markdown
# Service Documentation Template

## Service Name: [SERVICE_NAME]

### Overview
Brief description of the service's purpose and functionality.

### API Endpoints

#### POST /api/v1/[endpoint]
**Description**: What this endpoint does
**Request Body**:
```json
{
  "field": "type - description"
}
```
**Response**:
```json
{
  "result": "type - description"
}
```
**Error Responses**:
- 400: Bad Request - Invalid input data
- 500: Internal Server Error - Service unavailable

### Environment Variables
| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| VAR_NAME | Yes | - | Variable description |

### Docker Configuration
```dockerfile
FROM python:3.11-slim
# ... configuration
```

### Testing
```bash
# Run unit tests
pytest tests/

# Run integration tests
pytest tests/integration/

# Run with coverage
pytest --cov=app tests/
```

### Monitoring
- Health check: GET /health
- Metrics: GET /metrics
- Logs: Structured JSON logging
```

---

## Completion Checklist

### ✅ Development Environment Setup
- [x] **Local Development Tools**: Node.js, Python, Docker, Azure CLI installed
- [x] **IDE Configuration**: VS Code with extensions and workspace settings
- [x] **Project Structure**: Microservices directory structure created
- [x] **Service Templates**: FastAPI templates for all 6 services
- [x] **Development Configuration**: Docker Compose and environment files

### ✅ CI/CD Pipeline Setup  
- [x] **GitHub Actions**: Build, test, and deploy workflows
- [x] **Azure DevOps**: Alternative pipeline configuration
- [x] **Docker Registry**: Azure Container Registry integration
- [x] **Environment Management**: Development and production configurations

### ✅ Development Tools & Scripts
- [x] **Setup Scripts**: Automated development environment setup
- [x] **Development Scripts**: Start, test, and build automation
- [x] **Monitoring Setup**: Health checks, logging, and metrics
- [x] **Testing Infrastructure**: Unit, integration, and performance tests

### ✅ Documentation & Templates
- [x] **Service Documentation**: API documentation templates
- [x] **Development Guides**: Setup and contribution guidelines
- [x] **Architecture Documentation**: Service interface specifications

---

## Next Steps for Sprint 2

### Week 2 Immediate Actions
1. **Finalize Azure OpenAI Access**: Complete approval process and deploy models
2. **Configure Development Secrets**: Setup Key Vault integration for development
3. **Team Onboarding**: Share development environment setup with team
4. **Code Repository**: Initialize Git repository with initial service structure
5. **Monitoring Setup**: Configure Application Insights for development environment

### Integration Readiness
1. **Service Interfaces**: All REST API specifications defined
2. **Authentication Flow**: Azure AD integration patterns established  
3. **Container Registry**: Ready for microservice deployments
4. **CI/CD Pipelines**: Automated build and deployment workflows configured
5. **Development Workflow**: Local development and testing procedures documented

---

**Status**: Development environment configuration completed  
**Next Action**: Begin Sprint 2 - Core Infrastructure Setup  
**Deliverables**: 6 service templates, CI/CD pipelines, development tools, testing infrastructure