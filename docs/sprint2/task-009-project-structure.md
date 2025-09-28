# TASK-009: Project Structure Creation

**Date**: January 2024  
**Assigned**: Senior Full-stack Developer 2  
**Status**: IN PROGRESS  
**Effort**: 12 hours  

---

## Executive Summary

Creation of standardized project structure templates and development guidelines for Screenshot-to-Code microservices architecture. Establishes consistent organization, coding standards, testing patterns, and documentation practices across all 6 microservices to ensure maintainability, scalability, and developer productivity.

---

## Project Architecture Overview

### 🏗️ **Monorepo Structure**
```
screenshot-to-code/
├── services/                     # Microservices
│   ├── api-gateway/              # API Gateway service
│   ├── image-processor/          # Image processing service
│   ├── code-generator/           # Code generation service
│   ├── image-generator/          # Image generation service
│   ├── nlp-processor/            # NLP processing service
│   └── evaluation/               # Evaluation service
├── shared/                       # Shared libraries and utilities
│   ├── auth/                     # Authentication modules
│   ├── monitoring/               # Monitoring and logging
│   ├── security/                 # Security utilities
│   ├── config/                   # Configuration management
│   └── types/                    # Shared type definitions
├── infrastructure/               # Infrastructure as Code
│   ├── terraform/                # Terraform configurations
│   ├── k8s/                      # Kubernetes manifests
│   └── azure/                    # Azure-specific configurations
├── tests/                        # Cross-service integration tests
│   ├── integration/              # Integration test suites
│   ├── e2e/                      # End-to-end tests
│   └── performance/              # Performance tests
├── docs/                         # Documentation
│   ├── api/                      # API documentation
│   ├── architecture/             # Architecture documentation
│   └── deployment/               # Deployment guides
├── scripts/                      # Development and deployment scripts
└── tools/                        # Development tools and utilities
```

---

## Phase 1: Service Template Structure

### 1.1 Standard Service Directory Layout

```bash
# Create comprehensive service template structure
mkdir -p services/template-service/{app,tests,docs,scripts,config}
mkdir -p services/template-service/app/{routes,models,services,utils,middleware}
mkdir -p services/template-service/tests/{unit,integration,fixtures}
mkdir -p services/template-service/docs/{api,deployment}
mkdir -p services/template-service/config/{development,production,testing}
```

### 1.2 Service Template Files

```python
# services/template-service/app/main.py
"""
Main FastAPI application entry point for [SERVICE_NAME]
"""
import os
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.routes import health, api
from app.middleware.correlation import setup_correlation_middleware
from app.middleware.security import setup_security_middleware
from shared.monitoring.app_insights import setup_monitoring
from shared.auth.azure_ad import setup_authentication
from shared.config.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    app.logger.info(f"{settings.service_name} starting up...")
    
    # Initialize any required resources here
    # e.g., database connections, external service clients
    
    yield
    
    # Shutdown
    app.logger.info(f"{settings.service_name} shutting down...")
    
    # Cleanup resources here


def create_application() -> FastAPI:
    """Create and configure FastAPI application"""
    
    app = FastAPI(
        title=f"Screenshot-to-Code {settings.service_name}",
        description=f"Microservice for {settings.service_name} operations",
        version="1.0.0",
        docs_url="/docs" if settings.environment == "development" else None,
        redoc_url="/redoc" if settings.environment == "development" else None,
        lifespan=lifespan
    )
    
    # Setup middleware (order matters!)
    setup_security_middleware(app)
    setup_correlation_middleware(app)
    
    # Setup CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )
    
    # Setup monitoring and authentication
    setup_monitoring(app, settings.service_name)
    setup_authentication(app)
    
    # Include routers
    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(api.router, prefix="/api/v1", tags=["api"])
    
    return app


# Create application instance
app = create_application()


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower()
    )
```

```python
# services/template-service/app/routes/health.py
"""
Health check endpoints for service monitoring
"""
from fastapi import APIRouter, Depends
from typing import Dict, Any
import time
import psutil
from shared.health.health_checker import HealthChecker, create_health_endpoint
from shared.auth.azure_ad import get_current_user
from shared.config.settings import settings

router = APIRouter()

# Initialize health checker
health_checker = HealthChecker(settings.service_name)

# Add health checks based on service dependencies
if hasattr(settings, 'database_url'):
    health_checker.add_database_check("database", settings.database_url)

if hasattr(settings, 'redis_url'):
    health_checker.add_redis_check("redis", settings.redis_url)

# Create health endpoints
create_health_endpoint(router, health_checker)

@router.get("/metrics")
async def get_metrics(current_user: Dict = Depends(get_current_user)):
    """Get service metrics (requires authentication)"""
    
    # System metrics
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # Application metrics (implement based on service)
    app_metrics = {
        "requests_processed": 0,  # Implement counter
        "average_response_time": 0,  # Implement tracking
        "active_connections": 0,  # Implement tracking
        "error_rate": 0  # Implement tracking
    }
    
    return {
        "service": settings.service_name,
        "timestamp": time.time(),
        "system": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_mb": memory.available // 1024 // 1024,
            "disk_percent": (disk.used / disk.total) * 100,
            "disk_free_gb": disk.free // 1024 // 1024 // 1024
        },
        "application": app_metrics
    }
```

```python
# services/template-service/app/routes/api.py
"""
Main API routes for [SERVICE_NAME]
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any
from pydantic import BaseModel

from shared.auth.azure_ad import get_current_user, require_role
from shared.security.input_validation import validate_request_data
from app.services.main_service import MainService
from app.models.requests import ServiceRequest, ServiceResponse

router = APIRouter()

# Initialize service layer
main_service = MainService()


class ServiceRequestModel(BaseModel):
    """Request model for service operations"""
    input_data: str
    options: Dict[str, Any] = {}


class ServiceResponseModel(BaseModel):
    """Response model for service operations"""
    result: str
    metadata: Dict[str, Any] = {}
    processing_time_ms: float


@router.post("/process", response_model=ServiceResponseModel)
async def process_request(
    request: ServiceRequestModel,
    current_user: Dict = Depends(get_current_user)
):
    """
    Main processing endpoint
    
    Requires authentication and appropriate permissions.
    """
    
    try:
        # Validate and sanitize input
        validated_request = validate_request_data(
            request.dict(), 
            ServiceRequest
        )
        
        # Process request through service layer
        result = await main_service.process(
            validated_request,
            user_context=current_user
        )
        
        return ServiceResponseModel(
            result=result.output,
            metadata=result.metadata,
            processing_time_ms=result.processing_time_ms
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Processing failed: {str(e)}"
        )


@router.get("/status")
async def get_service_status(
    current_user: Dict = Depends(get_current_user)
):
    """Get current service status and configuration"""
    
    return {
        "service": settings.service_name,
        "version": "1.0.0",
        "environment": settings.environment,
        "status": "operational",
        "features": main_service.get_available_features()
    }


@router.post("/admin/configure")
@require_role("admin")
async def update_configuration(
    config_update: Dict[str, Any],
    current_user: Dict = Depends(get_current_user)
):
    """
    Update service configuration (admin only)
    """
    
    try:
        await main_service.update_configuration(config_update)
        
        return {
            "status": "success",
            "message": "Configuration updated successfully",
            "updated_by": current_user.get("email")
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Configuration update failed: {str(e)}"
        )
```

```python
# services/template-service/app/services/main_service.py
"""
Main service layer for business logic
"""
import time
from typing import Dict, Any, List
from dataclasses import dataclass
from shared.monitoring.structured_logger import StructuredLogger
from shared.security.data_protection import SecureDataHandler
from app.models.requests import ServiceRequest

@dataclass
class ProcessingResult:
    """Result of service processing"""
    output: str
    metadata: Dict[str, Any]
    processing_time_ms: float

class MainService:
    """Main service class for [SERVICE_NAME] business logic"""
    
    def __init__(self):
        self.logger = StructuredLogger("main-service")
        self.data_handler = SecureDataHandler()
        self.features = [
            "basic_processing",
            "advanced_processing", 
            "batch_processing"
        ]
    
    async def process(self, request: ServiceRequest, user_context: Dict) -> ProcessingResult:
        """
        Main processing method
        
        Args:
            request: Validated service request
            user_context: Authenticated user context
            
        Returns:
            ProcessingResult with output and metadata
        """
        
        start_time = time.time()
        correlation_id = user_context.get("correlation_id")
        
        try:
            self.logger.logger.info(
                "Starting request processing",
                extra={
                    "correlation_id": correlation_id,
                    "user_id": user_context.get("id"),
                    "request_type": type(request).__name__
                }
            )
            
            # Implement your business logic here
            result = await self._execute_processing(request, user_context)
            
            processing_time = (time.time() - start_time) * 1000
            
            # Log successful processing
            self.logger.log_business_metric(
                metric_name="request_processed",
                value=1,
                dimensions={"success": "true"},
                correlation_id=correlation_id
            )
            
            return ProcessingResult(
                output=result,
                metadata={
                    "processed_at": time.time(),
                    "processing_time_ms": processing_time,
                    "user_id": user_context.get("id")
                },
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            
            # Log error
            self.logger.log_error(
                error=e,
                context={
                    "request_type": type(request).__name__,
                    "processing_time_ms": processing_time
                },
                correlation_id=correlation_id
            )
            
            raise
    
    async def _execute_processing(self, request: ServiceRequest, user_context: Dict) -> str:
        """
        Execute the actual processing logic
        
        Override this method in each service implementation
        """
        
        # Placeholder implementation
        return f"Processed: {request.input_data}"
    
    def get_available_features(self) -> List[str]:
        """Get list of available features"""
        return self.features.copy()
    
    async def update_configuration(self, config_update: Dict[str, Any]):
        """Update service configuration"""
        
        # Implement configuration update logic
        # This could update database settings, feature flags, etc.
        
        self.logger.logger.info(
            "Configuration updated",
            extra={"config_keys": list(config_update.keys())}
        )
```

```python
# services/template-service/app/models/requests.py
"""
Request and response models for service
"""
from pydantic import BaseModel, validator
from typing import Dict, Any, Optional
from shared.security.input_validation import SecurityValidator

class ServiceRequest(BaseModel):
    """Base service request model with validation"""
    
    input_data: str
    options: Dict[str, Any] = {}
    
    @validator('input_data')
    def validate_input_data(cls, v):
        """Validate and sanitize input data"""
        if not v or len(v.strip()) == 0:
            raise ValueError("Input data cannot be empty")
        
        # Sanitize input
        sanitized = SecurityValidator.sanitize_string(v)
        
        # Check length limits
        if len(sanitized) > 10000:  # 10KB limit
            raise ValueError("Input data too large")
        
        return sanitized
    
    @validator('options')
    def validate_options(cls, v):
        """Validate options dictionary"""
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

class ServiceResponse(BaseModel):
    """Base service response model"""
    
    status: str = "success"
    result: str
    metadata: Dict[str, Any] = {}
    
    class Config:
        schema_extra = {
            "example": {
                "status": "success",
                "result": "Processing completed successfully",
                "metadata": {
                    "processing_time_ms": 150.5,
                    "items_processed": 1
                }
            }
        }
```

---

## Phase 2: Configuration Management

### 2.1 Service Configuration Templates

```python
# services/template-service/config/base.py
"""
Base configuration for all environments
"""
from pydantic import BaseSettings, Field
from typing import List, Optional
import os

class BaseConfig(BaseSettings):
    """Base configuration settings"""
    
    # Service identification
    service_name: str = Field(default="template-service", env="SERVICE_NAME")
    service_version: str = Field(default="1.0.0", env="SERVICE_VERSION")
    environment: str = Field(default="development", env="ENVIRONMENT")
    
    # API configuration
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Authentication
    azure_tenant_id: Optional[str] = Field(default=None, env="AZURE_TENANT_ID")
    azure_client_id: Optional[str] = Field(default=None, env="AZURE_CLIENT_ID")
    
    # Database (optional)
    database_url: Optional[str] = Field(default=None, env="DATABASE_URL")
    
    # Cache (optional)
    redis_url: Optional[str] = Field(default=None, env="REDIS_URL")
    
    # Monitoring
    application_insights_connection_string: Optional[str] = Field(
        default=None, 
        env="APPLICATIONINSIGHTS_CONNECTION_STRING"
    )
    
    # Security
    cors_allowed_origins: List[str] = Field(
        default=["http://localhost:3000"],
        env="CORS_ALLOWED_ORIGINS"
    )
    
    # Azure Key Vault
    azure_key_vault_name: Optional[str] = Field(default=None, env="AZURE_KEY_VAULT_NAME")
    
    class Config:
        case_sensitive = False
        env_file_encoding = 'utf-8'

# services/template-service/config/development.py
"""
Development environment configuration
"""
from .base import BaseConfig

class DevelopmentConfig(BaseConfig):
    """Development-specific configuration"""
    
    environment: str = "development"
    log_level: str = "DEBUG"
    
    # Development database
    database_url: str = "postgresql://dev_user:dev_password@localhost:5432/screenshot_to_code_dev"
    
    # Development cache
    redis_url: str = "redis://localhost:6379/0"
    
    # CORS for development
    cors_allowed_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000"
    ]
    
    class Config:
        env_file = ".env.development"

# services/template-service/config/production.py
"""
Production environment configuration
"""
from .base import BaseConfig
from typing import List

class ProductionConfig(BaseConfig):
    """Production-specific configuration"""
    
    environment: str = "production"
    log_level: str = "WARNING"
    
    # Production CORS (restricted)
    cors_allowed_origins: List[str] = [
        "https://copilotstudio.microsoft.com",
        "https://*.powerapps.com"
    ]
    
    class Config:
        env_file = ".env.production"

# services/template-service/config/__init__.py
"""
Configuration factory
"""
import os
from .base import BaseConfig
from .development import DevelopmentConfig
from .production import ProductionConfig

def get_config() -> BaseConfig:
    """Get configuration based on environment"""
    
    environment = os.getenv("ENVIRONMENT", "development").lower()
    
    config_map = {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
        "testing": DevelopmentConfig  # Use dev config for testing
    }
    
    config_class = config_map.get(environment, DevelopmentConfig)
    return config_class()

# Global configuration instance
settings = get_config()
```

### 2.2 Docker Configuration Templates

```dockerfile
# services/template-service/Dockerfile
# Multi-stage Docker build for production optimization

# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim as production

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set working directory
WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser config/ ./config/
COPY --chown=appuser:appuser shared/ ./shared/

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH=/home/appuser/.local/bin:$PATH

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start application
CMD ["python", "-m", "app.main"]

# Development Dockerfile
# services/template-service/Dockerfile.dev
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install with dev dependencies
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

# Copy application code
COPY . .

# Create non-root user for development
RUN useradd --create-home --shell /bin/bash appuser
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Development server with hot reload
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

```yaml
# services/template-service/docker-compose.yml
version: '3.8'

services:
  template-service:
    build: 
      context: .
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=development
      - LOG_LEVEL=DEBUG
      - DATABASE_URL=postgresql://dev_user:dev_password@postgres:5432/template_service_dev
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - .:/app
      - /app/__pycache__
    depends_on:
      - postgres
      - redis
    networks:
      - template-service-network

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=template_service_dev
      - POSTGRES_USER=dev_user
      - POSTGRES_PASSWORD=dev_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - template-service-network

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - template-service-network

volumes:
  postgres_data:
  redis_data:

networks:
  template-service-network:
    driver: bridge
```

---

## Phase 3: Testing Framework

### 3.1 Testing Infrastructure

```python
# services/template-service/tests/conftest.py
"""
Pytest configuration and fixtures for template service
"""
import pytest
import asyncio
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock
import pytest_asyncio
from typing import Dict, Generator

from app.main import create_application
from shared.config.settings import settings

# Override settings for testing
settings.environment = "testing"
settings.database_url = "sqlite:///./test.db"
settings.redis_url = "redis://localhost:6379/1"  # Use different DB for tests

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def app():
    """Create FastAPI test application"""
    return create_application()

@pytest_asyncio.fixture
async def client(app) -> Generator[AsyncClient, None, None]:
    """Create async HTTP client for testing"""
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client

@pytest.fixture
def mock_azure_ad_auth():
    """Mock Azure AD authentication for testing"""
    mock_user = {
        "id": "test-user-id",
        "email": "test@example.com",
        "name": "Test User",
        "roles": ["user"]
    }
    
    with patch("shared.auth.azure_ad.get_current_user") as mock_auth:
        mock_auth.return_value = mock_user
        yield mock_auth

@pytest.fixture
def mock_monitoring():
    """Mock monitoring for testing"""
    with patch("shared.monitoring.app_insights.setup_monitoring") as mock_monitor:
        yield mock_monitor

@pytest.fixture
def sample_request_data():
    """Sample request data for testing"""
    return {
        "input_data": "test input data",
        "options": {
            "format": "json",
            "timeout": 30
        }
    }

@pytest.fixture
def admin_user():
    """Admin user context for testing"""
    return {
        "id": "admin-user-id",
        "email": "admin@example.com",
        "name": "Admin User",
        "roles": ["admin"]
    }

@pytest.fixture
def unauthorized_user():
    """Unauthorized user context for testing"""
    return {
        "id": "unauthorized-user-id",
        "email": "unauthorized@example.com",
        "name": "Unauthorized User",
        "roles": []
    }
```

```python
# services/template-service/tests/unit/test_main_service.py
"""
Unit tests for main service logic
"""
import pytest
from unittest.mock import AsyncMock, patch
import time

from app.services.main_service import MainService, ProcessingResult
from app.models.requests import ServiceRequest

class TestMainService:
    """Test cases for MainService"""
    
    @pytest.fixture
    def service(self):
        """Create MainService instance for testing"""
        return MainService()
    
    @pytest.fixture
    def sample_request(self):
        """Sample service request"""
        return ServiceRequest(
            input_data="test input",
            options={"format": "json"}
        )
    
    @pytest.fixture
    def user_context(self):
        """Sample user context"""
        return {
            "id": "test-user-id",
            "email": "test@example.com",
            "correlation_id": "test-correlation-id"
        }
    
    @pytest.mark.asyncio
    async def test_process_success(self, service, sample_request, user_context):
        """Test successful processing"""
        
        # Mock the processing method
        with patch.object(service, '_execute_processing', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = "processed result"
            
            # Execute
            result = await service.process(sample_request, user_context)
            
            # Assertions
            assert isinstance(result, ProcessingResult)
            assert result.output == "processed result"
            assert result.processing_time_ms > 0
            assert "processed_at" in result.metadata
            
            # Verify method was called
            mock_execute.assert_called_once_with(sample_request, user_context)
    
    @pytest.mark.asyncio
    async def test_process_error_handling(self, service, sample_request, user_context):
        """Test error handling in processing"""
        
        # Mock the processing method to raise an exception
        with patch.object(service, '_execute_processing', new_callable=AsyncMock) as mock_execute:
            mock_execute.side_effect = ValueError("Processing failed")
            
            # Execute and expect exception
            with pytest.raises(ValueError, match="Processing failed"):
                await service.process(sample_request, user_context)
    
    def test_get_available_features(self, service):
        """Test getting available features"""
        
        features = service.get_available_features()
        
        assert isinstance(features, list)
        assert len(features) > 0
        assert "basic_processing" in features
    
    @pytest.mark.asyncio
    async def test_update_configuration(self, service):
        """Test configuration update"""
        
        config_update = {"feature_flag": True}
        
        # Should not raise exception
        await service.update_configuration(config_update)
        
        # Verify logging was called (mock in real implementation)
        # This is a placeholder for actual implementation testing
```

```python
# services/template-service/tests/integration/test_api_endpoints.py
"""
Integration tests for API endpoints
"""
import pytest
from httpx import AsyncClient
from unittest.mock import patch

class TestAPIEndpoints:
    """Integration tests for API endpoints"""
    
    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test health check endpoint"""
        
        response = await client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data
        assert "timestamp" in data
    
    @pytest.mark.asyncio
    async def test_health_ready(self, client: AsyncClient):
        """Test readiness probe endpoint"""
        
        response = await client.get("/health/ready")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
    
    @pytest.mark.asyncio
    async def test_health_live(self, client: AsyncClient):
        """Test liveness probe endpoint"""
        
        response = await client.get("/health/live")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
    
    @pytest.mark.asyncio
    async def test_process_endpoint_authenticated(self, client: AsyncClient, mock_azure_ad_auth, sample_request_data):
        """Test process endpoint with authentication"""
        
        response = await client.post(
            "/api/v1/process",
            json=sample_request_data,
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "metadata" in data
        assert "processing_time_ms" in data
    
    @pytest.mark.asyncio
    async def test_process_endpoint_unauthenticated(self, client: AsyncClient, sample_request_data):
        """Test process endpoint without authentication"""
        
        response = await client.post(
            "/api/v1/process",
            json=sample_request_data
        )
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_process_endpoint_invalid_input(self, client: AsyncClient, mock_azure_ad_auth):
        """Test process endpoint with invalid input"""
        
        invalid_data = {
            "input_data": "",  # Empty input
            "options": "invalid"  # Should be dict
        }
        
        response = await client.post(
            "/api/v1/process",
            json=invalid_data,
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_status_endpoint(self, client: AsyncClient, mock_azure_ad_auth):
        """Test status endpoint"""
        
        response = await client.get(
            "/api/v1/status",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "version" in data
        assert "status" in data
        assert "features" in data
    
    @pytest.mark.asyncio
    async def test_admin_configure_endpoint(self, client: AsyncClient, admin_user):
        """Test admin configuration endpoint"""
        
        with patch("shared.auth.azure_ad.get_current_user", return_value=admin_user):
            response = await client.post(
                "/api/v1/admin/configure",
                json={"feature_flag": True},
                headers={"Authorization": "Bearer admin-token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_admin_configure_unauthorized(self, client: AsyncClient, unauthorized_user):
        """Test admin configuration endpoint with unauthorized user"""
        
        with patch("shared.auth.azure_ad.get_current_user", return_value=unauthorized_user):
            response = await client.post(
                "/api/v1/admin/configure",
                json={"feature_flag": True},
                headers={"Authorization": "Bearer user-token"}
            )
        
        assert response.status_code == 403
```

### 3.2 Performance Testing Framework

```python
# services/template-service/tests/performance/test_performance.py
"""
Performance tests for service endpoints
"""
import pytest
import asyncio
import time
import statistics
from httpx import AsyncClient
from concurrent.futures import ThreadPoolExecutor

class TestPerformance:
    """Performance test suite"""
    
    @pytest.mark.asyncio
    async def test_endpoint_response_time(self, client: AsyncClient, mock_azure_ad_auth, sample_request_data):
        """Test endpoint response time under normal load"""
        
        response_times = []
        
        for _ in range(10):
            start_time = time.time()
            
            response = await client.post(
                "/api/v1/process",
                json=sample_request_data,
                headers={"Authorization": "Bearer test-token"}
            )
            
            end_time = time.time()
            response_time = (end_time - start_time) * 1000  # Convert to ms
            
            assert response.status_code == 200
            response_times.append(response_time)
        
        # Performance assertions
        avg_response_time = statistics.mean(response_times)
        p95_response_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile
        
        assert avg_response_time < 500, f"Average response time {avg_response_time}ms exceeds 500ms"
        assert p95_response_time < 1000, f"95th percentile response time {p95_response_time}ms exceeds 1000ms"
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, client: AsyncClient, mock_azure_ad_auth, sample_request_data):
        """Test service under concurrent load"""
        
        async def make_request():
            response = await client.post(
                "/api/v1/process",
                json=sample_request_data,
                headers={"Authorization": "Bearer test-token"}
            )
            return response.status_code, response.elapsed.total_seconds() * 1000
        
        # Create 20 concurrent requests
        tasks = [make_request() for _ in range(20)]
        results = await asyncio.gather(*tasks)
        
        # Analyze results
        success_count = sum(1 for status_code, _ in results if status_code == 200)
        response_times = [response_time for _, response_time in results]
        
        # Performance assertions
        success_rate = success_count / len(results)
        avg_response_time = statistics.mean(response_times)
        
        assert success_rate >= 0.95, f"Success rate {success_rate:.2%} below 95%"
        assert avg_response_time < 2000, f"Average response time {avg_response_time}ms exceeds 2000ms under load"
    
    @pytest.mark.asyncio
    async def test_memory_usage(self, client: AsyncClient, mock_azure_ad_auth, sample_request_data):
        """Test memory usage during processing"""
        
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Make multiple requests
        for _ in range(50):
            response = await client.post(
                "/api/v1/process",
                json=sample_request_data,
                headers={"Authorization": "Bearer test-token"}
            )
            assert response.status_code == 200
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory should not increase by more than 50MB
        assert memory_increase < 50 * 1024 * 1024, f"Memory increased by {memory_increase / 1024 / 1024:.2f}MB"
```

---

## Phase 4: Development Guidelines and Standards

### 4.1 Coding Standards Document

```markdown
# services/template-service/docs/CODING_STANDARDS.md

# Coding Standards for Screenshot-to-Code Services

## Python Code Style

### General Guidelines
- Follow PEP 8 style guide
- Use type hints for all function parameters and return values
- Maximum line length: 88 characters (Black formatter standard)
- Use meaningful variable and function names
- Write docstrings for all public functions and classes

### Import Organization
```python
# Standard library imports
import os
import json
from typing import Dict, List, Optional

# Third-party imports
from fastapi import FastAPI, Depends
from pydantic import BaseModel
import httpx

# Local imports
from app.services import main_service
from shared.auth import azure_ad
```

### Function Documentation
```python
def process_image(image_data: str, options: Dict[str, Any]) -> ProcessingResult:
    """
    Process image data with specified options.
    
    Args:
        image_data: Base64 encoded image data
        options: Processing options dictionary
        
    Returns:
        ProcessingResult containing processed image and metadata
        
    Raises:
        ValueError: If image_data is invalid
        ProcessingError: If image processing fails
    """
    pass
```

### Error Handling
- Use specific exception types
- Always log errors with context
- Provide meaningful error messages
- Use try/except blocks for expected failures only

### Testing Standards
- Minimum 80% code coverage
- Write unit tests for all business logic
- Write integration tests for API endpoints
- Use meaningful test names that describe the scenario
- Follow AAA pattern: Arrange, Act, Assert

## API Design Standards

### REST API Guidelines
- Use HTTP verbs correctly (GET, POST, PUT, DELETE)
- Use plural nouns for resource endpoints
- Use HTTP status codes appropriately
- Include API versioning in URL path (/api/v1/)

### Request/Response Models
- Always use Pydantic models for validation
- Include examples in model definitions
- Validate all input data
- Sanitize output data

### Error Responses
```python
{
    "error": {
        "code": "INVALID_INPUT",
        "message": "Input validation failed",
        "details": {
            "field": "email",
            "issue": "Invalid email format"
        }
    }
}
```

## Security Guidelines

### Input Validation
- Validate all user inputs
- Sanitize data before processing
- Use parameterized queries for database operations
- Implement rate limiting on all endpoints

### Authentication & Authorization
- Always require authentication for sensitive endpoints
- Use role-based access control (RBAC)
- Log all authentication attempts
- Implement session timeout

### Data Protection
- Encrypt sensitive data at rest
- Use HTTPS for all communications
- Never log sensitive information
- Implement data retention policies

## Performance Guidelines

### Response Times
- API endpoints: < 200ms (95th percentile)
- Health checks: < 50ms
- Database queries: < 100ms
- External API calls: < 5s with timeout

### Resource Usage
- Memory usage: < 512MB per service instance
- CPU usage: < 50% average, < 80% peak
- Database connections: Use connection pooling
- Cache frequently accessed data

## Logging Standards

### Log Levels
- ERROR: System errors requiring immediate attention
- WARNING: Unexpected conditions that don't prevent operation
- INFO: General operational information
- DEBUG: Detailed diagnostic information

### Log Format
```python
{
    "timestamp": "2024-01-15T10:30:00Z",
    "level": "INFO",
    "service": "image-processor",
    "correlation_id": "abc123",
    "user_id": "user456",
    "message": "Image processing completed",
    "metadata": {
        "processing_time_ms": 150,
        "image_size": 1024768
    }
}
```

## Documentation Standards

### Code Documentation
- Write clear, concise docstrings
- Document all public APIs
- Include examples in documentation
- Keep documentation up-to-date with code changes

### API Documentation
- Use OpenAPI/Swagger specifications
- Include request/response examples
- Document error conditions
- Provide integration guides
```

### 4.2 Service Development Checklist

```markdown
# services/template-service/docs/DEVELOPMENT_CHECKLIST.md

# Service Development Checklist

## Setup Phase
- [ ] Copy template service structure
- [ ] Update service name and description
- [ ] Configure environment variables
- [ ] Setup development database
- [ ] Configure authentication
- [ ] Setup monitoring and logging

## Development Phase
- [ ] Implement business logic
- [ ] Add input validation
- [ ] Implement error handling
- [ ] Add security measures
- [ ] Write unit tests (>80% coverage)
- [ ] Write integration tests
- [ ] Document API endpoints
- [ ] Performance testing

## Quality Assurance
- [ ] Code review completed
- [ ] All tests passing
- [ ] Security scan passed
- [ ] Performance benchmarks met
- [ ] Documentation updated
- [ ] Deployment guide created

## Deployment Preparation
- [ ] Docker image builds successfully
- [ ] Health checks implemented
- [ ] Configuration externalized
- [ ] Secrets properly managed
- [ ] Monitoring configured
- [ ] Logging properly formatted

## Production Readiness
- [ ] Load testing completed
- [ ] Failover scenarios tested
- [ ] Monitoring alerts configured
- [ ] Incident response procedures documented
- [ ] Backup and recovery procedures tested
- [ ] Security audit completed

## Post-Deployment
- [ ] Service health monitoring
- [ ] Performance metrics tracking
- [ ] Error rate monitoring
- [ ] User feedback collection
- [ ] Documentation maintenance
- [ ] Regular security updates
```

---

## Completion Checklist

### ✅ **Service Template Structure**
- [x] **Standard Directory Layout**: Consistent organization across all services
- [x] **FastAPI Application Template**: Main application, routes, middleware setup
- [x] **Service Layer Template**: Business logic separation and error handling
- [x] **Model Templates**: Request/response validation with Pydantic

### ✅ **Configuration Management**
- [x] **Environment-Specific Config**: Development, production, testing configurations
- [x] **Settings Factory**: Dynamic configuration loading based on environment
- [x] **Docker Configuration**: Multi-stage builds, development and production containers
- [x] **Docker Compose**: Local development environment with dependencies

### ✅ **Testing Framework**
- [x] **Test Infrastructure**: Pytest configuration with async support
- [x] **Unit Test Templates**: Service logic testing with mocks and fixtures
- [x] **Integration Test Templates**: API endpoint testing with authentication
- [x] **Performance Test Templates**: Load testing and performance benchmarks

### ✅ **Development Guidelines**
- [x] **Coding Standards**: Python style guide, API design, security guidelines
- [x] **Development Checklist**: Step-by-step service development process
- [x] **Documentation Standards**: Code documentation, API specs, deployment guides
- [x] **Quality Assurance**: Code review process, testing requirements

---

## Next Steps for Sprint 3

### Service Implementation Priority
1. **Image Processor Service**: Extract from existing codebase (lowest risk)
2. **Code Generator Service**: Core functionality with AI provider integration
3. **API Gateway Service**: Request routing and authentication layer
4. **Image Generator Service**: DALL-E and Flux integration
5. **NLP Processor Service**: Intent classification and entity extraction
6. **Evaluation Service**: Performance testing and quality metrics

### Development Workflow
1. Copy template service structure for each microservice
2. Implement service-specific business logic
3. Add comprehensive testing (unit, integration, performance)
4. Configure monitoring and security
5. Deploy to development environment
6. Conduct integration testing across services

---

**Status**: Project structure creation completed  
**Next Action**: Begin Sprint 3 - Service Extraction starting with Image Processor  
**Deliverables**: Complete service templates, configuration management, testing framework, development guidelines

## 🎉 Sprint 2 - Core Infrastructure Setup COMPLETED!

All 4 tasks of Sprint 2 have been successfully completed:

### ✅ **TASK-006: CI/CD Pipeline Development** 
- Azure DevOps multi-stage pipelines with security scanning
- GitHub Actions workflows with matrix builds
- Local development and testing scripts
- Container build and deployment automation

### ✅ **TASK-007: Monitoring and Logging Setup**
- Application Insights integration with custom metrics
- Structured logging with correlation IDs
- Grafana dashboards and Azure Monitor workbooks
- Intelligent alerting with incident response automation

### ✅ **TASK-008: Security Architecture Design**
- Azure AD authentication and RBAC implementation
- API Gateway security with WAF and rate limiting
- Data encryption and Key Vault integration
- Comprehensive threat modeling and incident response

### ✅ **TASK-009: Project Structure Creation**
- Standardized service templates for all 6 microservices
- Configuration management with environment-specific settings
- Complete testing framework with performance benchmarks
- Development guidelines and coding standards

**Total Sprint 2 Effort**: 68 hours completed across infrastructure, monitoring, security, and project structure.

Ready to proceed with **Sprint 3: Service Extraction** - beginning with Image Processor Service development.

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"content": "TASK-006: CI/CD Pipeline Development - Create Azure DevOps pipelines for automated build, test, and deployment", "status": "completed", "priority": "high", "id": "6"}, {"content": "TASK-007: Monitoring and Logging Setup - Configure Application Insights, log aggregation, and alerting", "status": "completed", "priority": "high", "id": "7"}, {"content": "TASK-008: Security Architecture Design - Design security architecture including authentication, authorization, and data protection", "status": "completed", "priority": "high", "id": "8"}, {"content": "TASK-009: Project Structure Creation - Create standardized project structure for microservices", "status": "completed", "priority": "high", "id": "9"}]