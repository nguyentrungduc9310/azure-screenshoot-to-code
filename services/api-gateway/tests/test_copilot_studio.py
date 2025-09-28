"""
Test cases for Copilot Studio webhook integration
"""
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.routes.copilot_studio import (
    router, CopilotStudioWebhookHandler, CopilotStudioRequest,
    CopilotStudioActivity, verify_webhook_signature
)
from app.services.copilot_integration_service import (
    CopilotIntegrationService, Framework, CodeGenerationResult
)


# Test fixtures
@pytest.fixture
def test_app():
    """Create test FastAPI app"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(test_app):
    """Create test client"""
    return TestClient(test_app)


@pytest.fixture
def sample_message_activity():
    """Sample message activity from Copilot Studio"""
    return CopilotStudioActivity(
        type="message",
        id="activity-123",
        timestamp="2024-01-01T12:00:00Z",
        from_property={"id": "user-123", "name": "Test User"},
        recipient={"id": "bot-456", "name": "Screenshot Bot"},
        conversation={"id": "conv-789"},
        text="Generate code from this screenshot",
        attachments=[
            {
                "contentType": "image/png",
                "contentUrl": "https://example.com/image.png",
                "name": "screenshot.png"
            }
        ]
    )


@pytest.fixture
def sample_invoke_activity():
    """Sample invoke activity from Copilot Studio"""
    return CopilotStudioActivity(
        type="invoke",
        id="activity-456",
        timestamp="2024-01-01T12:01:00Z",
        from_property={"id": "user-123", "name": "Test User"},
        recipient={"id": "bot-456", "name": "Screenshot Bot"},
        conversation={"id": "conv-789"},
        value={
            "action": "generateCode",
            "framework": "react",
            "imageUrl": "https://example.com/image.png",
            "requirements": "Make it responsive"
        }
    )


@pytest.fixture
def mock_copilot_service():
    """Mock copilot integration service"""
    service = AsyncMock(spec=CopilotIntegrationService)
    
    # Mock successful code generation
    service.process_screenshot_to_code.return_value = CodeGenerationResult(
        success=True,
        generated_code={
            "Component.jsx": "import React from 'react';\n\nconst Component = () => {\n  return <div>Generated!</div>;\n};\n\nexport default Component;",
            "styles.css": ".container { padding: 20px; }"
        },
        framework="react",
        processing_time_ms=1500.0,
        preview_url="https://preview.example.com/123"
    )
    
    return service


class TestWebhookSignatureVerification:
    """Test webhook signature verification"""
    
    def test_verify_valid_signature(self):
        """Test signature verification with valid signature"""
        secret = "test-secret"
        body = b'{"test": "data"}'
        
        import hmac
        import hashlib
        expected_sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        
        assert verify_webhook_signature(body, f"sha256={expected_sig}", secret) is True
        assert verify_webhook_signature(body, expected_sig, secret) is True
    
    def test_verify_invalid_signature(self):
        """Test signature verification with invalid signature"""
        secret = "test-secret"
        body = b'{"test": "data"}'
        invalid_sig = "invalid-signature"
        
        assert verify_webhook_signature(body, invalid_sig, secret) is False
        assert verify_webhook_signature(body, "", secret) is False
        assert verify_webhook_signature(body, None, secret) is False


class TestCopilotStudioWebhookHandler:
    """Test webhook handler functionality"""
    
    @pytest.fixture
    def handler(self):
        """Create webhook handler"""
        from shared.monitoring.structured_logger import StructuredLogger
        logger = StructuredLogger()
        return CopilotStudioWebhookHandler(logger)
    
    @pytest.mark.asyncio
    async def test_process_message_activity_with_image(self, handler, sample_message_activity):
        """Test processing message activity with image attachment"""
        user_info = {"id": "user-123", "name": "Test User"}
        
        response = await handler._handle_message_activity(sample_message_activity, user_info)
        
        assert response is not None
        assert response.type == "message"
        assert len(response.attachments) == 1
        assert response.attachments[0]["contentType"] == "application/vnd.microsoft.card.adaptive"
        
        # Check adaptive card content
        card = response.attachments[0]["content"]
        assert "Screenshot Received!" in card["body"][0]["text"]
        assert len(card["actions"]) >= 3  # React, HTML, Vue buttons
    
    @pytest.mark.asyncio
    async def test_process_message_activity_text_only(self, handler):
        """Test processing text-only message activity"""
        activity = CopilotStudioActivity(
            type="message",
            id="activity-text",
            timestamp="2024-01-01T12:00:00Z",
            from_property={"id": "user-123"},
            conversation={"id": "conv-789"},
            text="help",
            attachments=[]
        )
        user_info = {"id": "user-123", "name": "Test User"}
        
        response = await handler._handle_message_activity(activity, user_info)
        
        assert response is not None
        assert response.type == "message"
        # Should return help response for "help" keyword
        assert len(response.attachments) == 1
        assert "Screenshot-to-Code Assistant" in response.attachments[0]["content"]["body"][0]["text"]
    
    @pytest.mark.asyncio
    async def test_process_invoke_activity(self, handler, sample_invoke_activity, mock_copilot_service):
        """Test processing invoke activity for code generation"""
        user_info = {"id": "user-123", "name": "Test User"}
        
        with patch("app.routes.copilot_studio.get_copilot_service", return_value=mock_copilot_service):
            response = await handler._handle_invoke_activity(sample_invoke_activity, user_info)
        
        assert response is not None
        assert response.type == "message"
        assert len(response.attachments) == 1
        
        # Check that code generation service was called
        mock_copilot_service.process_screenshot_to_code.assert_called_once_with(
            image_url="https://example.com/image.png",
            framework=Framework.REACT,
            requirements="Make it responsive",
            user_id="user-123",
            conversation_id="conv-789",
            async_processing=False
        )
        
        # Check adaptive card content
        card = response.attachments[0]["content"]
        assert "REACT Code Generated!" in card["body"][0]["text"]
        assert "Component.jsx" in str(card["body"])  # Code should be displayed
    
    @pytest.mark.asyncio
    async def test_process_event_activity_conversation_start(self, handler):
        """Test processing conversation start event"""
        activity = CopilotStudioActivity(
            type="event",
            id="activity-event",
            timestamp="2024-01-01T12:00:00Z",
            from_property={"id": "user-123"},
            conversation={"id": "conv-789"},
            value={"type": "conversationStart"}
        )
        user_info = {"id": "user-123", "name": "Test User"}
        
        response = await handler._handle_event_activity(activity, user_info)
        
        assert response is not None
        assert response.type == "message"
        assert len(response.attachments) == 1
        
        # Check welcome message
        card = response.attachments[0]["content"]
        assert "Welcome Test User!" in card["body"][0]["text"]
    
    @pytest.mark.asyncio
    async def test_process_webhook_multiple_activities(self, handler):
        """Test processing webhook with multiple activities"""
        request = CopilotStudioRequest(
            activities=[
                CopilotStudioActivity(
                    type="event",
                    id="event-1",
                    timestamp="2024-01-01T12:00:00Z",
                    from_property={"id": "user-123"},
                    conversation={"id": "conv-789"},
                    value={"type": "conversationStart"}
                ),
                CopilotStudioActivity(
                    type="message",
                    id="message-1",
                    timestamp="2024-01-01T12:00:01Z",
                    from_property={"id": "user-123"},
                    conversation={"id": "conv-789"},
                    text="help",
                    attachments=[]
                )
            ]
        )
        user_info = {"id": "user-123", "name": "Test User"}
        
        responses = await handler.process_webhook(request, user_info)
        
        assert len(responses) == 2
        assert all(response.type == "message" for response in responses)


class TestWebhookEndpoints:
    """Test webhook HTTP endpoints"""
    
    @pytest.mark.asyncio
    async def test_webhook_endpoint_success(self, client, mock_copilot_service):
        """Test successful webhook request"""
        webhook_data = {
            "activities": [
                {
                    "type": "message",
                    "id": "activity-123",
                    "timestamp": "2024-01-01T12:00:00Z",
                    "from": {"id": "user-123", "name": "Test User"},
                    "recipient": {"id": "bot-456"},
                    "conversation": {"id": "conv-789"},
                    "text": "hello",
                    "attachments": []
                }
            ]
        }
        
        with patch("app.routes.copilot_studio.get_copilot_service", return_value=mock_copilot_service):
            with patch("app.routes.copilot_studio.get_user_info") as mock_get_user:
                mock_get_user.return_value = {"id": "user-123", "name": "Test User"}
                
                response = client.post(
                    "/copilot-studio/webhook",
                    json=webhook_data,
                    headers={"Content-Type": "application/json"}
                )
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["type"] == "message"
    
    def test_webhook_endpoint_invalid_json(self, client):
        """Test webhook with invalid JSON"""
        response = client.post(
            "/copilot-studio/webhook",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 400
        assert "Invalid request format" in response.json()["detail"]
    
    def test_webhook_health_endpoint(self, client):
        """Test webhook health endpoint"""
        response = client.get("/copilot-studio/webhook/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "copilot-studio-webhook"
        assert "supported_activities" in data
    
    def test_webhook_schema_endpoint(self, client):
        """Test webhook schema endpoint"""
        response = client.get("/copilot-studio/webhook/schema")
        
        assert response.status_code == 200
        data = response.json()
        assert data["webhook_url"] == "/api/v1/copilot-studio/webhook"
        assert data["method"] == "POST"
        assert "supported_activities" in data
        assert "message" in data["supported_activities"]
        assert "invoke" in data["supported_activities"]


class TestCopilotIntegrationService:
    """Test copilot integration service"""
    
    @pytest.fixture
    def integration_service(self):
        """Create integration service"""
        return CopilotIntegrationService(
            image_processor_url="http://test-image:8001",
            code_generator_url="http://test-code:8002",
            image_generator_url="http://test-img-gen:8003"
        )
    
    @pytest.mark.asyncio
    async def test_process_screenshot_to_code_sync(self, integration_service):
        """Test synchronous screenshot processing"""
        # Mock HTTP calls
        with patch("aiohttp.ClientSession.post") as mock_post:
            # Mock image processing response
            mock_image_response = AsyncMock()
            mock_image_response.status = 200
            mock_image_response.json.return_value = {
                "success": True,
                "processed_image": "data:image/jpeg;base64,processed_image_data",
                "processing_time_ms": 150.0
            }
            
            # Mock code generation response  
            mock_code_response = AsyncMock()
            mock_code_response.status = 200
            mock_code_response.json.return_value = {
                "success": True,
                "generated_code": {
                    "Component.jsx": "import React from 'react';\n\nconst Component = () => <div>Test</div>;\n\nexport default Component;"
                },
                "framework": "react",
                "processing_time_ms": 2500.0,
                "preview_url": "https://preview.example.com/123"
            }
            
            mock_post.side_effect = [mock_image_response, mock_code_response]
            
            # Start service
            await integration_service.start()
            
            try:
                result = await integration_service.process_screenshot_to_code(
                    image_url="https://example.com/test.png",
                    framework=Framework.REACT,
                    requirements="Make it responsive",
                    user_id="test-user",
                    conversation_id="test-conv"
                )
                
                assert result.success is True
                assert result.framework == "react"
                assert "Component.jsx" in result.generated_code
                assert result.preview_url is not None
                
                # Verify service calls
                assert mock_post.call_count == 2
                
            finally:
                await integration_service.stop()
    
    @pytest.mark.asyncio
    async def test_process_screenshot_to_code_async(self, integration_service):
        """Test asynchronous screenshot processing"""
        # Mock HTTP calls
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {"success": True, "processed_image": "data:image/jpeg;base64,test"}
            mock_post.return_value = mock_response
            
            await integration_service.start()
            
            try:
                # Start async processing
                job_id = await integration_service.process_screenshot_to_code(
                    image_url="https://example.com/test.png",
                    framework=Framework.REACT,
                    user_id="test-user",
                    conversation_id="test-conv",
                    async_processing=True
                )
                
                assert isinstance(job_id, str)
                assert job_id.startswith("job_")
                
                # Check job status
                job_status = await integration_service.get_job_status(job_id)
                assert job_status is not None
                assert job_status["job_id"] == job_id
                assert job_status["user_id"] == "test-user"
                assert job_status["status"] in ["pending", "processing"]
                
                # Wait a bit for processing (in real test, you'd wait for completion)
                await asyncio.sleep(0.1)
                
            finally:
                await integration_service.stop()
    
    @pytest.mark.asyncio
    async def test_get_supported_frameworks(self, integration_service):
        """Test getting supported frameworks"""
        frameworks = await integration_service.get_supported_frameworks()
        
        assert len(frameworks) > 0
        assert any(f["id"] == "react" for f in frameworks)
        assert any(f["id"] == "html" for f in frameworks)
        assert any(f["id"] == "vue" for f in frameworks)
        
        for framework in frameworks:
            assert "id" in framework
            assert "name" in framework
            assert "description" in framework


if __name__ == "__main__":
    pytest.main([__file__])