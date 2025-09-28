"""
Test configuration and fixtures for API Gateway tests
"""
import asyncio
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
import jwt
from datetime import datetime, timedelta

from app.main import create_app
from app.core.config import Settings
from app.services.service_client import ServiceClient
from shared.monitoring.structured_logger import StructuredLogger

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def test_settings():
    """Test settings with authentication disabled for easier testing"""
    return Settings(
        environment="testing",
        enable_authentication=False,
        enable_rate_limiting=False,
        enable_swagger_ui=True,
        code_generator_service_url="http://mock-code-generator:8002",
        image_generator_service_url="http://mock-image-generator:8003",
        jwt_secret="test-secret-key"
    )

@pytest.fixture
def auth_settings():
    """Test settings with authentication enabled"""
    return Settings(
        environment="testing",
        enable_authentication=True,
        enable_rate_limiting=False,
        code_generator_service_url="http://mock-code-generator:8002",
        image_generator_service_url="http://mock-image-generator:8003",
        jwt_secret="test-secret-key"
    )

@pytest.fixture
def mock_logger():
    """Mock structured logger"""
    logger = MagicMock(spec=StructuredLogger)
    logger._get_timestamp.return_value = "2024-01-15T10:30:00Z"
    return logger

@pytest.fixture
def mock_service_client():
    """Mock service client with predefined responses"""
    client = AsyncMock(spec=ServiceClient)
    
    # Mock health check responses
    client.health_check.return_value = True
    client.get_service_health.return_value = {
        "code_generator": "healthy",
        "image_generator": "healthy"
    }
    client.get_circuit_breaker_status.return_value = {
        "code_generator": {
            "state": "closed",
            "failure_count": 0,
            "failure_threshold": 5,
            "last_failure_time": 0
        },
        "image_generator": {
            "state": "closed", 
            "failure_count": 0,
            "failure_threshold": 5,
            "last_failure_time": 0
        }
    }
    
    # Mock successful code generation response
    from app.services.service_client import RequestResult
    client.call_code_generator.return_value = RequestResult(
        success=True,
        status_code=200,
        data={
            "id": "gen_test123",
            "code": "<html><body>Test generated code</body></html>",
            "status": "completed",
            "code_stack": "html_tailwind",
            "provider": "openai",
            "generation_time_ms": 3500,
            "token_usage": {
                "prompt_tokens": 1200,
                "completion_tokens": 800,
                "total_tokens": 2000
            }
        },
        duration_ms=3500
    )
    
    # Mock successful image generation response
    client.call_image_generator.return_value = RequestResult(
        success=True,
        status_code=200,
        data={
            "id": "img_test456",
            "prompt": "Test image prompt",
            "provider": "dalle3",
            "status": "completed",
            "images": [
                {
                    "url": "https://test.com/image.png",
                    "size": "1024x1024",
                    "format": "png"
                }
            ],
            "generation_time_ms": 5000,
            "cost_estimate": 0.04
        },
        duration_ms=5000
    )
    
    return client

@pytest.fixture
def app_with_mocks(test_settings, mock_service_client, mock_logger):
    """FastAPI app with mocked dependencies"""
    app = create_app()
    
    # Override settings and dependencies
    app.state.settings = test_settings
    app.state.service_client = mock_service_client
    app.state.logger = mock_logger
    
    return app

@pytest.fixture
def auth_app_with_mocks(auth_settings, mock_service_client, mock_logger):
    """FastAPI app with authentication enabled and mocked dependencies"""
    app = create_app()
    
    # Override settings and dependencies
    app.state.settings = auth_settings
    app.state.service_client = mock_service_client
    app.state.logger = mock_logger
    
    return app

@pytest.fixture
def client(app_with_mocks):
    """Test client for the API"""
    return TestClient(app_with_mocks)

@pytest.fixture
def auth_client(auth_app_with_mocks):
    """Test client with authentication enabled"""
    return TestClient(auth_app_with_mocks)

@pytest.fixture
def valid_jwt_token(auth_settings):
    """Generate a valid JWT token for testing"""
    payload = {
        "sub": "test-user-123",
        "email": "test@example.com",
        "roles": ["user"],
        "tenant_id": "test-tenant",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    
    return jwt.encode(payload, auth_settings.jwt_secret, algorithm=auth_settings.jwt_algorithm)

@pytest.fixture
def expired_jwt_token(auth_settings):
    """Generate an expired JWT token for testing"""
    payload = {
        "sub": "test-user-123",
        "email": "test@example.com",
        "roles": ["user"],
        "tenant_id": "test-tenant",
        "iat": datetime.utcnow() - timedelta(hours=2),
        "exp": datetime.utcnow() - timedelta(hours=1)  # Expired 1 hour ago
    }
    
    return jwt.encode(payload, auth_settings.jwt_secret, algorithm=auth_settings.jwt_algorithm)

@pytest.fixture
def code_generation_request():
    """Sample code generation request payload"""
    return {
        "image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD//test-image-data",
        "code_stack": "react_tailwind",
        "generation_type": "create",
        "additional_instructions": "Make it responsive",
        "should_generate_images": False
    }

@pytest.fixture
def image_generation_request():
    """Sample image generation request payload"""
    return {
        "prompt": "A modern web interface with clean design",
        "provider": "dalle3",
        "size": "1024x1024",
        "quality": "standard",
        "style": "natural",
        "num_images": 1
    }

@pytest.fixture
def failed_service_client():
    """Mock service client that simulates downstream service failures"""
    client = AsyncMock(spec=ServiceClient)
    
    # Simulate service unavailable
    client.health_check.return_value = False
    client.get_service_health.return_value = {
        "code_generator": "unhealthy",
        "image_generator": "circuit_open"
    }
    
    # Simulate failed requests
    from app.services.service_client import RequestResult
    client.call_code_generator.return_value = RequestResult(
        success=False,
        status_code=503,
        error="Service unavailable",
        duration_ms=1000
    )
    
    client.call_image_generator.return_value = RequestResult(
        success=False,
        status_code=503,
        error="Circuit breaker open",
        duration_ms=100
    )
    
    return client

@pytest.fixture
def auth_headers(valid_jwt_token):
    """Authorization headers with valid JWT token"""
    return {
        "Authorization": f"Bearer {valid_jwt_token}",
        "Content-Type": "application/json"
    }

@pytest.fixture
def invalid_auth_headers():
    """Authorization headers with invalid JWT token"""
    return {
        "Authorization": "Bearer invalid-token",
        "Content-Type": "application/json"
    }

@pytest.fixture
def sample_image_file():
    """Sample image file for upload testing"""
    import io
    from PIL import Image
    
    # Create a small test image
    img = Image.new('RGB', (100, 100), color='red')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    return ("test_image.png", img_bytes, "image/png")