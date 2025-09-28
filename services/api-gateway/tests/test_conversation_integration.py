"""
Test cases for Conversation Manager integration with Copilot Studio webhook
"""
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
from datetime import datetime, timezone

from app.routes.copilot_studio import router, CopilotStudioWebhookHandler
from app.conversation.conversation_manager import (
    AdvancedConversationManager, ConversationState, MessageType, UserIntent,
    ConversationMessage, ConversationContext
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
def mock_conversation_manager():
    """Mock conversation manager"""
    manager = AsyncMock(spec=AdvancedConversationManager)
    
    # Mock conversation context
    mock_context = ConversationContext(
        conversation_id="test-conv-123",
        user_id="test-user-456",
        state=ConversationState.INITIAL,
        started_at=datetime.now(timezone.utc),
        last_activity=datetime.now(timezone.utc)
    )
    
    manager.start_conversation.return_value = mock_context
    manager.get_conversation_context.return_value = mock_context
    
    # Mock processed message
    mock_message = ConversationMessage(
        id="msg-123",
        timestamp=datetime.now(timezone.utc),
        user_id="test-user-456",
        conversation_id="test-conv-123",
        message_type=MessageType.TEXT,
        content="Hello",
        intent=UserIntent.REQUEST_HELP,
        confidence=0.8
    )
    
    manager.process_message.return_value = mock_message
    
    # Mock context for response
    manager.get_context_for_response.return_value = {
        "conversation_id": "test-conv-123",
        "user_id": "test-user-456",
        "current_state": "initial",
        "current_framework": None,
        "uploaded_images": [],
        "generated_code": {},
        "recent_messages": [],
        "user_preferences": {
            "preferred_framework": "react",
            "communication_style": "detailed",
            "experience_level": "beginner"
        },
        "session_data": {}
    }
    
    # Mock analytics
    manager.get_conversation_analytics.return_value = {
        "total_conversations": 10,
        "total_users": 5,
        "total_messages": 50,
        "total_successes": 20,
        "total_errors": 2,
        "average_quality_score": 0.85,
        "success_rate": 0.4,
        "error_rate": 0.04
    }
    
    manager.end_conversation.return_value = {
        "conversation_summary": {
            "conversation_id": "test-conv-123",
            "message_count": 5,
            "successful_generations": 1,
            "last_activity": "2024-01-01T12:00:00Z"
        },
        "analytics": {
            "quality_score": 0.9,
            "avg_confidence": 0.8,
            "error_rate": 0.0,
            "success_rate": 0.2
        },
        "user_insights": {
            "experience_level": "beginner",
            "framework_expertise": {"react": 1.0}
        }
    }
    
    return manager


@pytest.fixture
def sample_copilot_activity():
    """Sample Copilot Studio activity"""
    return {
        "type": "message",
        "id": "activity-123",
        "timestamp": "2024-01-01T12:00:00Z",
        "from": {
            "id": "user-456",
            "name": "Test User"
        },
        "recipient": {
            "id": "bot-789",
            "name": "Screenshot Bot"
        },
        "conversation": {
            "id": "conv-123"
        },
        "text": "Hello, I need help with code generation",
        "attachments": [],
        "channelData": {}
    }


class TestConversationIntegration:
    """Test conversation manager integration with webhook handler"""
    
    @pytest.mark.asyncio
    async def test_webhook_handler_conversation_initialization(self, mock_conversation_manager):
        """Test webhook handler initializes conversation manager"""
        from app.routes.copilot_studio import logger
        
        with patch("app.routes.copilot_studio.get_conversation_manager", return_value=mock_conversation_manager):
            handler = CopilotStudioWebhookHandler(logger)
            
            # Ensure conversation manager is initialized
            conv_manager = await handler._ensure_conversation_manager()
            assert conv_manager is not None
            assert conv_manager == mock_conversation_manager
    
    @pytest.mark.asyncio
    async def test_message_processing_with_context(self, mock_conversation_manager, sample_copilot_activity):
        """Test message processing with conversation context"""
        from app.routes.copilot_studio import logger, CopilotStudioActivity
        
        with patch("app.routes.copilot_studio.get_conversation_manager", return_value=mock_conversation_manager):
            handler = CopilotStudioWebhookHandler(logger)
            
            activity = CopilotStudioActivity(**sample_copilot_activity)
            user_info = {"id": "test-user-456", "name": "Test User"}
            
            response = await handler._handle_message_activity(activity, user_info)
            
            # Verify conversation manager was called
            mock_conversation_manager.process_message.assert_called_once()
            call_args = mock_conversation_manager.process_message.call_args
            
            assert call_args[1]["conversation_id"] == "conv-123"
            assert call_args[1]["user_id"] == "test-user-456"
            assert call_args[1]["message_content"] == "Hello, I need help with code generation"
            assert call_args[1]["message_type"] == MessageType.TEXT
            
            # Verify context was retrieved
            mock_conversation_manager.get_context_for_response.assert_called_once_with("conv-123")
            
            # Verify response is generated
            assert response is not None
            assert response.type == "message"
    
    @pytest.mark.asyncio
    async def test_image_processing_with_user_preferences(self, mock_conversation_manager):
        """Test image processing uses user preferences"""
        from app.routes.copilot_studio import logger, CopilotStudioActivity
        
        # Activity with image attachment
        activity_data = {
            "type": "message",
            "id": "activity-123",
            "timestamp": "2024-01-01T12:00:00Z",
            "from": {"id": "user-456", "name": "Test User"},
            "recipient": {"id": "bot-789", "name": "Screenshot Bot"},
            "conversation": {"id": "conv-123"},
            "text": "Convert this screenshot to React",
            "attachments": [
                {
                    "contentType": "image/png",
                    "contentUrl": "https://example.com/screenshot.png"
                }
            ]
        }
        
        with patch("app.routes.copilot_studio.get_conversation_manager", return_value=mock_conversation_manager):
            handler = CopilotStudioWebhookHandler(logger)
            
            activity = CopilotStudioActivity(**activity_data)
            user_info = {"id": "test-user-456", "name": "Test User"}
            
            response = await handler._handle_message_activity(activity, user_info)
            
            # Verify image message was processed
            mock_conversation_manager.process_message.assert_called_once()
            call_args = mock_conversation_manager.process_message.call_args
            
            assert call_args[1]["message_type"] == MessageType.IMAGE
            assert call_args[1]["message_content"] == "https://example.com/screenshot.png"
            
            # Verify response contains framework actions
            assert response is not None
            assert len(response.attachments) > 0
            
            card_content = response.attachments[0]["content"]
            assert "React" in str(card_content)  # Should show React as recommended
    
    @pytest.mark.asyncio
    async def test_conversation_start_event(self, mock_conversation_manager):
        """Test conversation start event initializes context"""
        from app.routes.copilot_studio import logger, CopilotStudioActivity
        
        activity_data = {
            "type": "event",
            "id": "activity-123",
            "timestamp": "2024-01-01T12:00:00Z",
            "from": {"id": "user-456", "name": "Test User"},
            "conversation": {"id": "conv-123"},
            "value": {"type": "conversationStart"}
        }
        
        with patch("app.routes.copilot_studio.get_conversation_manager", return_value=mock_conversation_manager):
            handler = CopilotStudioWebhookHandler(logger)
            
            activity = CopilotStudioActivity(**activity_data)
            user_info = {"id": "test-user-456", "name": "Test User"}
            
            response = await handler._handle_conversation_start(activity, user_info)
            
            # Verify conversation was started
            mock_conversation_manager.start_conversation.assert_called_once_with(
                user_id="test-user-456",
                conversation_id="conv-123"
            )
            
            # Verify welcome response
            assert response is not None
            assert response.type == "message"
            assert len(response.attachments) > 0
    
    @pytest.mark.asyncio
    async def test_conversation_end_with_analytics(self, mock_conversation_manager):
        """Test conversation end event generates analytics"""
        from app.routes.copilot_studio import logger, CopilotStudioActivity
        
        activity_data = {
            "type": "event",
            "id": "activity-123",
            "timestamp": "2024-01-01T12:00:00Z",
            "from": {"id": "user-456", "name": "Test User"},
            "conversation": {"id": "conv-123"},
            "value": {"type": "conversationEnd"}
        }
        
        with patch("app.routes.copilot_studio.get_conversation_manager", return_value=mock_conversation_manager):
            handler = CopilotStudioWebhookHandler(logger)
            
            activity = CopilotStudioActivity(**activity_data)
            user_info = {"id": "test-user-456", "name": "Test User"}
            
            response = await handler._handle_conversation_end(activity, user_info)
            
            # Verify conversation was ended
            mock_conversation_manager.end_conversation.assert_called_once_with("conv-123")
            
            # Verify no response for end event
            assert response is None
    
    @pytest.mark.asyncio
    async def test_successful_code_generation_recorded(self, mock_conversation_manager):
        """Test successful code generation is recorded in conversation manager"""
        from app.routes.copilot_studio import logger, CopilotStudioActivity
        from app.services.copilot_integration_service import Framework
        
        activity_data = {
            "type": "invoke",
            "id": "activity-123",
            "timestamp": "2024-01-01T12:00:00Z",
            "conversation": {"id": "conv-123"},
            "value": {
                "action": "generateCode",
                "framework": "react",
                "imageUrl": "https://example.com/screenshot.png",
                "requirements": "Make it responsive"
            }
        }
        
        # Mock successful code generation
        mock_result = Mock()
        mock_result.success = True
        mock_result.generated_code = {
            "App.jsx": "const App = () => <div>Hello</div>;",
            "App.css": ".app { color: blue; }"
        }
        mock_result.processing_time_ms = 1500
        mock_result.preview_url = "https://preview.example.com/123"
        
        with patch("app.routes.copilot_studio.get_conversation_manager", return_value=mock_conversation_manager), \
             patch("app.routes.copilot_studio.get_copilot_service") as mock_service:
            
            mock_copilot_service = AsyncMock()
            mock_copilot_service.process_screenshot_to_code.return_value = mock_result
            mock_service.return_value = mock_copilot_service
            
            handler = CopilotStudioWebhookHandler(logger)
            
            activity = CopilotStudioActivity(**activity_data)
            user_info = {"id": "test-user-456", "name": "Test User"}
            
            response = await handler._handle_code_generation_action(activity, user_info)
            
            # Verify successful generation was recorded
            mock_conversation_manager.record_successful_generation.assert_called_once_with(
                conversation_id="conv-123",
                framework="react",
                code=mock_result.generated_code
            )
            
            # Verify response contains generated code
            assert response is not None
            assert len(response.attachments) > 0
            
            card_content = response.attachments[0]["content"]
            assert "REACT Code Generated!" in str(card_content)
    
    @pytest.mark.asyncio
    async def test_code_generation_error_recorded(self, mock_conversation_manager):
        """Test code generation errors are recorded in conversation manager"""
        from app.routes.copilot_studio import logger, CopilotStudioActivity
        
        activity_data = {
            "type": "invoke",
            "id": "activity-123",
            "timestamp": "2024-01-01T12:00:00Z",
            "conversation": {"id": "conv-123"},
            "value": {
                "action": "generateCode",
                "framework": "react",
                "imageUrl": "https://example.com/screenshot.png"
            }
        }
        
        with patch("app.routes.copilot_studio.get_conversation_manager", return_value=mock_conversation_manager), \
             patch("app.routes.copilot_studio.get_copilot_service") as mock_service:
            
            # Mock service to raise exception
            mock_service.side_effect = Exception("API service unavailable")
            
            handler = CopilotStudioWebhookHandler(logger)
            
            activity = CopilotStudioActivity(**activity_data)
            user_info = {"id": "test-user-456", "name": "Test User"}
            
            response = await handler._handle_code_generation_action(activity, user_info)
            
            # Verify error was recorded
            mock_conversation_manager.record_error.assert_called_once_with(
                conversation_id="conv-123",
                error_type="code_generation_error",
                error_message="API service unavailable"
            )
            
            # Verify error response
            assert response is not None
            assert "code generation failed" in response.text.lower()


class TestConversationEndpoints:
    """Test conversation-related API endpoints"""
    
    def test_get_conversation_analytics(self, client, mock_conversation_manager):
        """Test getting conversation analytics"""
        with patch("app.routes.copilot_studio.get_conversation_manager", return_value=mock_conversation_manager):
            response = client.get("/copilot-studio/analytics")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert "analytics" in data
            assert data["analytics"]["total_conversations"] == 10
            assert data["analytics"]["average_quality_score"] == 0.85
    
    def test_get_conversation_context(self, client, mock_conversation_manager):
        """Test getting conversation context"""
        with patch("app.routes.copilot_studio.get_conversation_manager", return_value=mock_conversation_manager):
            response = client.get("/copilot-studio/conversations/test-conv-123/context")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert "context" in data
            assert data["context"]["conversation_id"] == "test-conv-123"
    
    def test_get_conversation_context_not_found(self, client):
        """Test getting context for non-existent conversation"""
        mock_manager = AsyncMock()
        mock_manager.get_conversation_context.return_value = None
        
        with patch("app.routes.copilot_studio.get_conversation_manager", return_value=mock_manager):
            response = client.get("/copilot-studio/conversations/nonexistent/context")
            
            assert response.status_code == 404
    
    def test_end_conversation_manually(self, client, mock_conversation_manager):
        """Test manually ending a conversation"""
        with patch("app.routes.copilot_studio.get_conversation_manager", return_value=mock_conversation_manager):
            response = client.post("/copilot-studio/conversations/test-conv-123/end")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert "analytics" in data
            assert data["analytics"]["conversation_summary"]["conversation_id"] == "test-conv-123"
    
    def test_end_nonexistent_conversation(self, client):
        """Test ending non-existent conversation"""
        mock_manager = AsyncMock()
        mock_manager.end_conversation.return_value = None
        
        with patch("app.routes.copilot_studio.get_conversation_manager", return_value=mock_manager):
            response = client.post("/copilot-studio/conversations/nonexistent/end")
            
            assert response.status_code == 404


class TestContextAwareResponses:
    """Test context-aware response generation"""
    
    @pytest.mark.asyncio
    async def test_help_response_based_on_state(self, mock_conversation_manager):
        """Test help response varies based on conversation state"""
        from app.routes.copilot_studio import CopilotStudioWebhookHandler, logger
        
        # Mock context with code review state
        mock_conversation_manager.get_context_for_response.return_value = {
            "current_state": "code_review",
            "user_preferences": {"communication_style": "detailed"}
        }
        
        with patch("app.routes.copilot_studio.get_conversation_manager", return_value=mock_conversation_manager):
            handler = CopilotStudioWebhookHandler(logger)
            
            context = await mock_conversation_manager.get_context_for_response("test-conv")
            response = await handler._create_contextual_help_response(context, "detailed")
            
            # Should mention code modification options when in code review state
            assert "modify the generated code" in response.text
            assert "regenerate" in response.text
    
    @pytest.mark.asyncio
    async def test_concise_vs_detailed_communication(self, mock_conversation_manager):
        """Test different communication styles"""
        from app.routes.copilot_studio import CopilotStudioWebhookHandler, logger
        
        with patch("app.routes.copilot_studio.get_conversation_manager", return_value=mock_conversation_manager):
            handler = CopilotStudioWebhookHandler(logger)
            
            context = {"current_state": "initial", "user_preferences": {}}
            
            # Test concise style
            response_concise = await handler._create_contextual_help_response(context, "concise")
            assert len(response_concise.text) < 100
            assert "That's it!" in response_concise.text
            
            # Test detailed style
            response_detailed = await handler._create_contextual_help_response(context, "detailed")
            assert len(response_detailed.text) > 100
            assert "working code" in response_detailed.text
    
    @pytest.mark.asyncio
    async def test_framework_recommendation_based_on_preferences(self, mock_conversation_manager):
        """Test framework actions show user preferences"""
        from app.routes.copilot_studio import CopilotStudioWebhookHandler, logger
        
        with patch("app.routes.copilot_studio.get_conversation_manager", return_value=mock_conversation_manager):
            handler = CopilotStudioWebhookHandler(logger)
            
            # Test with Vue preference
            actions = handler._create_framework_actions(
                content_url="https://example.com/image.png",
                requirements="Make it responsive",
                preferred_framework="vue"
            )
            
            # Find Vue action
            vue_action = next(action for action in actions if action["data"]["framework"] == "vue")
            assert "(Recommended)" in vue_action["title"]
            
            # Other actions should not have recommendation
            react_action = next(action for action in actions if action["data"]["framework"] == "react")
            assert "(Recommended)" not in react_action["title"]


if __name__ == "__main__":
    pytest.main([__file__])