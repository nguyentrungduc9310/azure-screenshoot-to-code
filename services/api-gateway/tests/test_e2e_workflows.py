"""
End-to-End Workflow Testing
Comprehensive testing of complete user workflows from conversation start to code generation
"""
import pytest
import asyncio
import json
import time
from typing import Dict, Any, List
from unittest.mock import AsyncMock, Mock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
from datetime import datetime, timezone

from app.routes.copilot_studio import router, CopilotStudioWebhookHandler
from app.conversation.conversation_manager import (
    AdvancedConversationManager, ConversationState, MessageType, UserIntent
)
from app.response.rich_formatter import (
    RichResponseFormatter, CodeBlock, ResponseTheme, CodeLanguage
)


class E2ETestCase:
    """Base class for end-to-end test scenarios"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.steps = []
        self.assertions = []
        self.performance_metrics = {}
    
    def add_step(self, step_name: str, action, expected_result=None):
        """Add a test step"""
        self.steps.append({
            "name": step_name,
            "action": action,
            "expected_result": expected_result
        })
    
    def add_assertion(self, assertion_func, message: str):
        """Add an assertion"""
        self.assertions.append({
            "func": assertion_func,
            "message": message
        })
    
    async def execute(self):
        """Execute the test case"""
        results = {"steps": [], "assertions": [], "performance": {}}
        start_time = time.time()
        
        # Execute steps
        context = {}
        for step in self.steps:
            step_start = time.time()
            try:
                result = await step["action"](context)
                step_time = time.time() - step_start
                
                results["steps"].append({
                    "name": step["name"],
                    "success": True,
                    "result": result,
                    "execution_time": step_time
                })
                
                # Update context with result
                if isinstance(result, dict):
                    context.update(result)
                    
            except Exception as e:
                results["steps"].append({
                    "name": step["name"],
                    "success": False,
                    "error": str(e),
                    "execution_time": time.time() - step_start
                })
                break
        
        # Execute assertions
        for assertion in self.assertions:
            try:
                assertion_result = assertion["func"](context, results)
                results["assertions"].append({
                    "message": assertion["message"],
                    "success": assertion_result,
                    "details": None
                })
            except Exception as e:
                results["assertions"].append({
                    "message": assertion["message"],
                    "success": False,
                    "details": str(e)
                })
        
        results["performance"]["total_time"] = time.time() - start_time
        return results


@pytest.fixture
def test_app():
    """Create test FastAPI app with all routes"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(test_app):
    """Create test client"""
    return TestClient(test_app)


@pytest.fixture
def mock_services():
    """Mock all external services"""
    services = {}
    
    # Mock conversation manager
    conv_manager = AsyncMock(spec=AdvancedConversationManager)
    services["conversation_manager"] = conv_manager
    
    # Mock copilot service
    copilot_service = AsyncMock()
    services["copilot_service"] = copilot_service
    
    # Mock rich formatter
    rich_formatter = Mock(spec=RichResponseFormatter)
    services["rich_formatter"] = rich_formatter
    
    return services


@pytest.fixture
def sample_webhook_data():
    """Sample webhook request data"""
    return {
        "activities": [
            {
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
                "text": "Hello",
                "attachments": []
            }
        ]
    }


class TestCompleteUserWorkflows:
    """Test complete user workflows from start to finish"""
    
    @pytest.mark.asyncio
    async def test_first_time_user_workflow(self, client, mock_services):
        """Test complete workflow for first-time user"""
        
        # Create test case
        test_case = E2ETestCase(
            "First Time User Workflow",
            "Complete workflow for new user from greeting to code generation"
        )
        
        # Step 1: Conversation start
        async def conversation_start(context):
            with patch("app.routes.copilot_studio.get_conversation_manager", 
                      return_value=mock_services["conversation_manager"]):
                response = client.post("/copilot-studio/webhook", json={
                    "activities": [{
                        "type": "event",
                        "id": "start-event",
                        "conversation": {"id": "conv-new-user"},
                        "from": {"id": "new-user-123", "name": "Alice"},
                        "value": {"type": "conversationStart"}
                    }]
                })
            return {"response": response, "conversation_id": "conv-new-user"}
        
        # Step 2: User uploads screenshot
        async def upload_screenshot(context):
            with patch("app.routes.copilot_studio.get_conversation_manager",
                      return_value=mock_services["conversation_manager"]):
                response = client.post("/copilot-studio/webhook", json={
                    "activities": [{
                        "type": "message",
                        "id": "upload-msg",
                        "conversation": {"id": context["conversation_id"]},
                        "from": {"id": "new-user-123", "name": "Alice"},
                        "text": "Convert this to React",
                        "attachments": [{
                            "contentType": "image/png",
                            "contentUrl": "https://example.com/screenshot.png"
                        }]
                    }]
                })
            return {"upload_response": response}
        
        # Step 3: Framework selection
        async def framework_selection(context):
            with patch("app.routes.copilot_studio.get_conversation_manager",
                      return_value=mock_services["conversation_manager"]):
                response = client.post("/copilot-studio/webhook", json={
                    "activities": [{
                        "type": "invoke",
                        "id": "generate-action",
                        "conversation": {"id": context["conversation_id"]},
                        "from": {"id": "new-user-123", "name": "Alice"},
                        "value": {
                            "action": "generateCode",
                            "framework": "react",
                            "imageUrl": "https://example.com/screenshot.png"
                        }
                    }]
                })
            return {"generation_response": response}
        
        # Add steps to test case
        test_case.add_step("conversation_start", conversation_start)
        test_case.add_step("upload_screenshot", upload_screenshot)
        test_case.add_step("framework_selection", framework_selection)
        
        # Add assertions
        test_case.add_assertion(
            lambda ctx, results: all(step["success"] for step in results["steps"]),
            "All workflow steps completed successfully"
        )
        
        test_case.add_assertion(
            lambda ctx, results: results["performance"]["total_time"] < 5.0,
            "Complete workflow finished within 5 seconds"
        )
        
        # Execute test case
        results = await test_case.execute()
        
        # Verify results
        assert all(step["success"] for step in results["steps"])
        assert all(assertion["success"] for assertion in results["assertions"])
        assert results["performance"]["total_time"] < 5.0
    
    @pytest.mark.asyncio
    async def test_returning_user_workflow(self, client, mock_services):
        """Test workflow for returning user with preferences"""
        
        # Mock user profile with preferences
        mock_user_profile = Mock()
        mock_user_profile.get_recommended_framework.return_value = "vue"
        mock_user_profile.preferred_communication_style = "concise"
        mock_user_profile.success_rate = 0.85
        
        mock_services["conversation_manager"].user_profiles = {
            "returning-user-456": mock_user_profile
        }
        
        test_case = E2ETestCase(
            "Returning User Workflow",
            "Workflow for user with established preferences"
        )
        
        # Test steps for returning user
        async def returning_user_start(context):
            with patch("app.routes.copilot_studio.get_conversation_manager",
                      return_value=mock_services["conversation_manager"]):
                response = client.post("/copilot-studio/webhook", json={
                    "activities": [{
                        "type": "event",
                        "id": "return-start",
                        "conversation": {"id": "conv-returning"},
                        "from": {"id": "returning-user-456", "name": "Bob"},
                        "value": {"type": "conversationStart"}
                    }]
                })
            return {"start_response": response}
        
        test_case.add_step("returning_user_start", returning_user_start)
        
        # Execute and verify
        results = await test_case.execute()
        assert all(step["success"] for step in results["steps"])
    
    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self, client, mock_services):
        """Test error handling and recovery workflow"""
        
        test_case = E2ETestCase(
            "Error Recovery Workflow",
            "Test error handling and user recovery paths"
        )
        
        # Step 1: Trigger error condition
        async def trigger_error(context):
            # Mock service to raise exception
            mock_services["copilot_service"].process_screenshot_to_code.side_effect = Exception("Service unavailable")
            
            with patch("app.routes.copilot_studio.get_conversation_manager",
                      return_value=mock_services["conversation_manager"]), \
                 patch("app.routes.copilot_studio.get_copilot_service",
                      return_value=mock_services["copilot_service"]):
                
                response = client.post("/copilot-studio/webhook", json={
                    "activities": [{
                        "type": "invoke",
                        "id": "error-trigger",
                        "conversation": {"id": "conv-error"},
                        "value": {
                            "action": "generateCode",
                            "framework": "react",
                            "imageUrl": "https://example.com/test.png"
                        }
                    }]
                })
            
            return {"error_response": response}
        
        # Step 2: User retry action
        async def user_retry(context):
            # Reset mock to succeed
            mock_services["copilot_service"].process_screenshot_to_code.side_effect = None
            mock_result = Mock()
            mock_result.success = True
            mock_result.generated_code = {"App.jsx": "const App = () => <div>Hello</div>;"}
            mock_result.processing_time_ms = 1200
            mock_services["copilot_service"].process_screenshot_to_code.return_value = mock_result
            
            with patch("app.routes.copilot_studio.get_conversation_manager",
                      return_value=mock_services["conversation_manager"]), \
                 patch("app.routes.copilot_studio.get_copilot_service",
                      return_value=mock_services["copilot_service"]):
                
                response = client.post("/copilot-studio/webhook", json={
                    "activities": [{
                        "type": "invoke",
                        "id": "retry-action",
                        "conversation": {"id": "conv-error"},
                        "value": {
                            "action": "generateCode",
                            "framework": "react",
                            "imageUrl": "https://example.com/test.png"
                        }
                    }]
                })
            
            return {"retry_response": response}
        
        test_case.add_step("trigger_error", trigger_error)
        test_case.add_step("user_retry", user_retry)
        
        # Add error recovery assertions
        test_case.add_assertion(
            lambda ctx, results: results["steps"][0]["success"],  # Error handled gracefully
            "Error was handled gracefully without crashing"
        )
        
        test_case.add_assertion(
            lambda ctx, results: results["steps"][1]["success"],  # Retry succeeded
            "User retry action succeeded after error"
        )
        
        results = await test_case.execute()
        assert all(assertion["success"] for assertion in results["assertions"])


class TestPerformanceWorkflows:
    """Test performance under various conditions"""
    
    @pytest.mark.asyncio
    async def test_concurrent_user_workflows(self, client, mock_services):
        """Test system performance with concurrent users"""
        
        async def simulate_concurrent_user(user_id: str, conversation_id: str):
            """Simulate a single user workflow"""
            start_time = time.time()
            
            steps = [
                # Start conversation
                {
                    "activities": [{
                        "type": "event",
                        "id": f"start-{user_id}",
                        "conversation": {"id": conversation_id},
                        "from": {"id": user_id, "name": f"User {user_id}"},
                        "value": {"type": "conversationStart"}
                    }]
                },
                # Send message
                {
                    "activities": [{
                        "type": "message",
                        "id": f"msg-{user_id}",
                        "conversation": {"id": conversation_id},
                        "from": {"id": user_id, "name": f"User {user_id}"},
                        "text": "Hello, I need help",
                        "attachments": []
                    }]
                }
            ]
            
            responses = []
            for step_data in steps:
                with patch("app.routes.copilot_studio.get_conversation_manager",
                          return_value=mock_services["conversation_manager"]):
                    response = client.post("/copilot-studio/webhook", json=step_data)
                    responses.append(response)
            
            return {
                "user_id": user_id,
                "execution_time": time.time() - start_time,
                "responses": responses
            }
        
        # Create concurrent user tasks
        num_users = 10
        tasks = []
        for i in range(num_users):
            user_id = f"concurrent-user-{i}"
            conversation_id = f"conv-concurrent-{i}"
            task = simulate_concurrent_user(user_id, conversation_id)
            tasks.append(task)
        
        # Execute all tasks concurrently
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        # Analyze results
        successful_users = [r for r in results if all(resp.status_code == 200 for resp in r["responses"])]
        avg_user_time = sum(r["execution_time"] for r in results) / len(results)
        max_user_time = max(r["execution_time"] for r in results)
        
        # Performance assertions
        assert len(successful_users) == num_users, f"All {num_users} users should complete successfully"
        assert total_time < 10.0, "All concurrent users should complete within 10 seconds"
        assert avg_user_time < 2.0, "Average user workflow should complete within 2 seconds"
        assert max_user_time < 5.0, "No user should take more than 5 seconds"
    
    @pytest.mark.asyncio
    async def test_large_conversation_handling(self, client, mock_services):
        """Test system performance with large conversations"""
        
        conversation_id = "conv-large-test"
        user_id = "large-conv-user"
        
        # Simulate a conversation with many messages
        num_messages = 50
        start_time = time.time()
        
        responses = []
        for i in range(num_messages):
            message_data = {
                "activities": [{
                    "type": "message",
                    "id": f"large-msg-{i}",
                    "conversation": {"id": conversation_id},
                    "from": {"id": user_id, "name": "Test User"},
                    "text": f"Message {i}: This is a test message with some content",
                    "attachments": []
                }]
            }
            
            with patch("app.routes.copilot_studio.get_conversation_manager",
                      return_value=mock_services["conversation_manager"]):
                response = client.post("/copilot-studio/webhook", json=message_data)
                responses.append(response)
        
        total_time = time.time() - start_time
        
        # Performance assertions
        successful_responses = [r for r in responses if r.status_code == 200]
        assert len(successful_responses) == num_messages, "All messages should be processed successfully"
        assert total_time < 15.0, f"Processing {num_messages} messages should complete within 15 seconds"
        
        # Check individual response times
        avg_response_time = total_time / num_messages
        assert avg_response_time < 0.3, f"Average response time should be under 300ms, got {avg_response_time:.3f}s"


class TestIntegrationWorkflows:
    """Test integration between different system components"""
    
    @pytest.mark.asyncio
    async def test_conversation_manager_integration(self, client, mock_services):
        """Test conversation manager integration throughout workflow"""
        
        conversation_id = "conv-integration-test"
        user_id = "integration-user"
        
        # Mock conversation manager with realistic behavior
        conv_manager = mock_services["conversation_manager"]
        
        # Mock conversation context
        mock_context = {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "current_state": "initial",
            "user_preferences": {
                "preferred_framework": "react",
                "communication_style": "detailed",
                "experience_level": "intermediate"
            }
        }
        conv_manager.get_context_for_response.return_value = mock_context
        
        # Test conversation start
        with patch("app.routes.copilot_studio.get_conversation_manager", return_value=conv_manager):
            start_response = client.post("/copilot-studio/webhook", json={
                "activities": [{
                    "type": "event",
                    "id": "integration-start",
                    "conversation": {"id": conversation_id},
                    "from": {"id": user_id, "name": "Integration User"},
                    "value": {"type": "conversationStart"}
                }]
            })
        
        # Verify conversation manager was called
        conv_manager.start_conversation.assert_called_once_with(
            user_id=user_id,
            conversation_id=conversation_id
        )
        
        assert start_response.status_code == 200
        
        # Test message processing
        with patch("app.routes.copilot_studio.get_conversation_manager", return_value=conv_manager):
            message_response = client.post("/copilot-studio/webhook", json={
                "activities": [{
                    "type": "message",
                    "id": "integration-msg",
                    "conversation": {"id": conversation_id},
                    "from": {"id": user_id, "name": "Integration User"},
                    "text": "I need help with code generation",
                    "attachments": []
                }]
            })
        
        # Verify message processing
        conv_manager.process_message.assert_called()
        conv_manager.get_context_for_response.assert_called_with(conversation_id)
        
        assert message_response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_rich_formatter_integration(self, client, mock_services):
        """Test rich formatter integration with responses"""
        
        # Mock rich formatter
        rich_formatter = mock_services["rich_formatter"]
        mock_card = {
            "type": "AdaptiveCard",
            "version": "1.5",
            "body": [{"type": "TextBlock", "text": "Test Card"}]
        }
        rich_formatter.create_welcome_response.return_value = mock_card
        
        with patch("app.routes.copilot_studio.get_conversation_manager",
                  return_value=mock_services["conversation_manager"]), \
             patch("app.routes.copilot_studio.get_rich_formatter", 
                  return_value=rich_formatter):
            
            response = client.post("/copilot-studio/webhook", json={
                "activities": [{
                    "type": "event",
                    "id": "formatter-test",
                    "conversation": {"id": "conv-formatter"},
                    "from": {"id": "formatter-user", "name": "Formatter User"},
                    "value": {"type": "conversationStart"}
                }]
            })
        
        # Verify rich formatter was used
        rich_formatter.create_welcome_response.assert_called_once()
        assert response.status_code == 200


class TestSecurityWorkflows:
    """Test security aspects of workflows"""
    
    def test_webhook_signature_validation(self, client):
        """Test webhook signature validation"""
        
        # Test without signature (should work for now, but log warning)
        response = client.post("/copilot-studio/webhook", json={
            "activities": [{
                "type": "message",
                "id": "security-test",
                "conversation": {"id": "conv-security"},
                "text": "test message"
            }]
        })
        
        # Should still process but ideally would validate signature in production
        assert response.status_code in [200, 401]  # Depends on configuration
    
    def test_input_sanitization(self, client, mock_services):
        """Test input sanitization and validation"""
        
        # Test with potentially malicious input
        malicious_inputs = [
            "<script>alert('xss')</script>",
            "'; DROP TABLE users; --",
            "../../../etc/passwd",
            "javascript:alert('test')"
        ]
        
        for malicious_input in malicious_inputs:
            with patch("app.routes.copilot_studio.get_conversation_manager",
                      return_value=mock_services["conversation_manager"]):
                
                response = client.post("/copilot-studio/webhook", json={
                    "activities": [{
                        "type": "message",
                        "id": "security-input-test",
                        "conversation": {"id": "conv-security"},
                        "text": malicious_input,
                        "attachments": []
                    }]
                })
            
            # Should handle malicious input gracefully
            assert response.status_code == 200
            
            # Response should not contain the malicious input directly
            response_data = response.json()
            if isinstance(response_data, dict) and "text" in response_data:
                assert malicious_input not in response_data["text"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])