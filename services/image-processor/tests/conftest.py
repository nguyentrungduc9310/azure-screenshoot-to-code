"""
Pytest configuration and fixtures for Image Processor service tests
"""
import pytest
import asyncio
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch
import pytest_asyncio
from typing import Dict, Generator
import os
import tempfile

# Set test environment
os.environ["ENVIRONMENT"] = "testing"
os.environ["LOG_LEVEL"] = "DEBUG"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

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
def mock_correlation_id():
    """Mock correlation ID for testing"""
    with patch("shared.monitoring.correlation.get_correlation_id", return_value="test-correlation-id"):
        yield "test-correlation-id"

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
def temp_image_file():
    """Create temporary image file for testing"""
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        # Create a simple test image using PIL
        try:
            from PIL import Image
            img = Image.new('RGB', (100, 100), color='red')
            img.save(tmp.name, 'PNG')
            yield tmp.name
        except ImportError:
            # If PIL not available, create dummy file
            tmp.write(b'fake image data')
            yield tmp.name
        finally:
            # Cleanup
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)

@pytest.fixture
def mock_settings():
    """Mock settings for testing"""
    mock_settings = MagicMock()
    mock_settings.environment = "testing"
    mock_settings.service_name = "image-processor"
    mock_settings.log_level = "DEBUG"
    
    with patch("shared.config.settings.settings", mock_settings):
        yield mock_settings

@pytest.fixture
def mock_structured_logger():
    """Mock structured logger for testing"""
    with patch("shared.monitoring.structured_logger.StructuredLogger") as mock_logger:
        mock_instance = MagicMock()
        mock_logger.return_value = mock_instance
        yield mock_instance

@pytest.fixture
def mock_secure_data_handler():
    """Mock secure data handler for testing"""
    with patch("shared.security.data_protection.SecureDataHandler") as mock_handler:
        mock_instance = MagicMock()
        mock_handler.return_value = mock_instance
        yield mock_instance

# Test data fixtures
@pytest.fixture
def valid_image_base64():
    """Valid base64 encoded image data"""
    # Simple 1x1 PNG image
    return "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

@pytest.fixture
def valid_image_data_url(valid_image_base64):
    """Valid image data URL"""
    return f"data:image/png;base64,{valid_image_base64}"

@pytest.fixture
def invalid_image_data_url():
    """Invalid image data URL"""
    return "data:image/png;base64,invalid_base64_data"

@pytest.fixture
def large_image_dimensions():
    """Dimensions for a large test image"""
    return (8000, 8000)

# Performance test fixtures
@pytest.fixture
def performance_test_config():
    """Configuration for performance tests"""
    return {
        "max_response_time_ms": 5000,
        "concurrent_requests": 10,
        "test_iterations": 5
    }

# Mock external dependencies
@pytest.fixture(autouse=True)
def mock_external_dependencies():
    """Mock external dependencies that might not be available in test environment"""
    
    # Mock PIL if not available
    try:
        import PIL
    except ImportError:
        with patch.dict('sys.modules', {'PIL': MagicMock(), 'PIL.Image': MagicMock()}):
            yield
    else:
        yield

@pytest.fixture
def mock_health_checker():
    """Mock health checker for testing"""
    with patch("shared.health.health_checker.HealthChecker") as mock_checker:
        mock_instance = MagicMock()
        mock_checker.return_value = mock_instance
        yield mock_instance