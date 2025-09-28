"""
Comprehensive System Testing
Complete system integration testing with performance validation
"""
import asyncio
import time
import psutil
import pytest
import statistics
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from unittest.mock import AsyncMock, Mock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.routes.copilot_studio import router, CopilotStudioWebhookHandler
from app.conversation.conversation_manager import AdvancedConversationManager
from app.response.rich_formatter import RichResponseFormatter, CodeBlock, ResponseTheme, CodeLanguage
from app.auth.oauth import OAuthManager


@dataclass
class SystemTestMetrics:
    """System-wide test metrics"""
    test_name: str
    total_time: float
    memory_peak_mb: float
    cpu_avg_percent: float
    requests_completed: int
    requests_failed: int
    avg_response_time: float
    p95_response_time: float
    throughput_rps: float
    error_rate: float
    

class ComprehensiveSystemTester:
    """System-wide testing framework"""
    
    def __init__(self):
        self.test_results: List[SystemTestMetrics] = []
        self.baseline_metrics: Dict[str, SystemTestMetrics] = {}
        self.process = psutil.Process()
    
    async def run_system_test(
        self,
        test_name: str,
        test_operations: List[callable],
        concurrent_users: int = 5,
        duration_seconds: int = 30
    ) -> SystemTestMetrics:
        """Run comprehensive system test"""
        
        # Initialize metrics tracking
        start_time = time.perf_counter()
        initial_memory = self.process.memory_info().rss / 1024 / 1024
        response_times = []
        completed_requests = 0
        failed_requests = 0
        cpu_samples = []
        memory_samples = []
        
        # Test execution loop
        end_time = start_time + duration_seconds
        
        async def user_simulation(user_id: int):
            """Simulate concurrent user operations"""
            nonlocal completed_requests, failed_requests, response_times
            
            user_response_times = []
            user_completed = 0
            user_failed = 0
            
            while time.perf_counter() < end_time:
                for operation in test_operations:
                    if time.perf_counter() >= end_time:
                        break
                    
                    op_start = time.perf_counter()
                    try:
                        if asyncio.iscoroutinefunction(operation):
                            await operation(user_id)
                        else:
                            operation(user_id)
                        
                        op_time = time.perf_counter() - op_start
                        user_response_times.append(op_time)
                        user_completed += 1
                        
                    except Exception as e:
                        user_failed += 1
                        op_time = time.perf_counter() - op_start
                        user_response_times.append(op_time)  # Include failed operation time
                    
                    # Brief pause between operations
                    await asyncio.sleep(0.05)
            
            # Update global counters (thread-safe in asyncio)
            completed_requests += user_completed
            failed_requests += user_failed
            response_times.extend(user_response_times)
        
        # Start concurrent users
        user_tasks = [user_simulation(user_id) for user_id in range(concurrent_users)]
        
        # Monitor system resources during test
        async def resource_monitor():
            while time.perf_counter() < end_time:
                cpu_samples.append(psutil.cpu_percent(interval=None))
                memory_info = self.process.memory_info()
                memory_samples.append(memory_info.rss / 1024 / 1024)
                await asyncio.sleep(1.0)
        
        # Run test and monitoring concurrently
        monitor_task = asyncio.create_task(resource_monitor())
        await asyncio.gather(*user_tasks)
        monitor_task.cancel()
        
        # Calculate final metrics
        total_time = time.perf_counter() - start_time
        total_requests = completed_requests + failed_requests
        
        metrics = SystemTestMetrics(
            test_name=test_name,
            total_time=total_time,
            memory_peak_mb=max(memory_samples) if memory_samples else initial_memory,
            cpu_avg_percent=statistics.mean(cpu_samples) if cpu_samples else 0.0,
            requests_completed=completed_requests,
            requests_failed=failed_requests,
            avg_response_time=statistics.mean(response_times) if response_times else 0.0,
            p95_response_time=statistics.quantiles(response_times, n=20)[18] if len(response_times) > 20 else 0.0,
            throughput_rps=total_requests / total_time if total_time > 0 else 0.0,
            error_rate=failed_requests / max(total_requests, 1)
        )
        
        self.test_results.append(metrics)
        return metrics


# Test fixtures
@pytest.fixture
def system_tester():
    """Create system tester instance"""
    return ComprehensiveSystemTester()


@pytest.fixture
def test_app():
    """Create test FastAPI app with all components"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(test_app):
    """Create test client"""
    return TestClient(test_app)


@pytest.fixture
def comprehensive_mock_services():
    """Comprehensive mock services for system testing"""
    services = {}
    
    # Advanced conversation manager mock
    conv_manager = AsyncMock(spec=AdvancedConversationManager)
    
    # Realistic conversation processing with delays
    async def mock_process_message(conversation_id, user_id, message_content, **kwargs):
        # Simulate processing complexity based on message length
        processing_delay = min(0.1, len(message_content) / 1000)
        await asyncio.sleep(processing_delay)
        
        return Mock(
            content=f"Processed: {message_content[:50]}...",
            intent="code_generation" if "code" in message_content.lower() else "general",
            confidence=0.95,
            entities={"framework": "react"} if "react" in message_content.lower() else {}
        )
    
    async def mock_get_context(conversation_id):
        await asyncio.sleep(0.02)  # Simulate context retrieval
        return {
            "conversation_id": conversation_id,
            "user_preferences": {
                "preferred_framework": "react",
                "communication_style": "detailed",
                "experience_level": "intermediate"
            },
            "conversation_history": []
        }
    
    conv_manager.process_message.side_effect = mock_process_message
    conv_manager.get_context_for_response.side_effect = mock_get_context
    conv_manager.start_conversation.side_effect = lambda **kwargs: Mock(success=True)
    
    services["conversation_manager"] = conv_manager
    
    # Rich formatter mock with realistic processing
    rich_formatter = Mock(spec=RichResponseFormatter)
    
    def mock_create_code_response(code_blocks, framework, **kwargs):
        # Simulate formatting time based on code complexity
        time.sleep(0.03 + len(code_blocks) * 0.01)
        
        return {
            "type": "AdaptiveCard",
            "version": "1.5",
            "body": [
                {"type": "TextBlock", "text": f"✨ {framework.upper()} Code Generated!"},
                {"type": "TextBlock", "text": f"Generated {len(code_blocks)} files"}
            ],
            "actions": [
                {"type": "Action.Submit", "title": "🔄 Regenerate", "data": {"action": "regenerate"}},
                {"type": "Action.Submit", "title": "💾 Download", "data": {"action": "download"}}
            ],
            "metadata": {
                "framework": framework,
                "code_blocks_count": len(code_blocks)
            }
        }
    
    def mock_create_framework_response(image_url, **kwargs):
        time.sleep(0.02)
        return {
            "type": "AdaptiveCard",
            "version": "1.5",
            "body": [{"type": "TextBlock", "text": "Choose your framework"}],
            "actions": [
                {"type": "Action.Submit", "title": "⚛️ React", "data": {"framework": "react"}},
                {"type": "Action.Submit", "title": "💚 Vue.js", "data": {"framework": "vue"}}
            ]
        }
    
    rich_formatter.create_code_generation_response.side_effect = mock_create_code_response
    rich_formatter.create_framework_selection_response.side_effect = mock_create_framework_response
    rich_formatter.create_welcome_response.side_effect = lambda **kwargs: {
        "type": "AdaptiveCard", "body": [{"type": "TextBlock", "text": "Welcome!"}]
    }
    
    services["rich_formatter"] = rich_formatter
    
    # OAuth manager mock
    oauth_manager = AsyncMock(spec=OAuthManager)
    oauth_manager.validate_token.return_value = {
        "valid": True,
        "user_id": "system-test-user",
        "user_info": {"name": "System Test User", "email": "test@example.com"}
    }
    services["oauth_manager"] = oauth_manager
    
    # Code generation service mock
    code_gen_service = AsyncMock()
    async def mock_process_screenshot(image_url, framework, **kwargs):
        # Simulate code generation time based on framework complexity
        base_time = {"html": 0.5, "react": 1.0, "vue": 0.8, "angular": 1.2}.get(framework, 1.0)
        await asyncio.sleep(base_time * 0.1)  # Scaled down for testing
        
        return Mock(
            success=True,
            generated_code={
                f"App.{'jsx' if framework == 'react' else 'html'}": f"Generated {framework} code",
                f"styles.css": "Generated CSS styles"
            },
            processing_time_ms=base_time * 100,
            preview_url=f"https://preview.example.com/{framework}-preview"
        )
    
    code_gen_service.process_screenshot_to_code.side_effect = mock_process_screenshot
    services["code_generation"] = code_gen_service
    
    return services


class TestFullSystemIntegration:
    """Full system integration tests"""
    
    @pytest.mark.asyncio
    async def test_complete_user_journey_performance(self, system_tester, client, comprehensive_mock_services):
        """Test complete user journey from start to code generation"""
        
        async def complete_user_journey(user_id: int):
            """Simulate complete user workflow"""
            conversation_id = f"system-test-conv-{user_id}"
            
            # Step 1: Conversation start
            with patch("app.routes.copilot_studio.get_conversation_manager", 
                      return_value=comprehensive_mock_services["conversation_manager"]):
                start_response = client.post("/copilot-studio/webhook", json={
                    "activities": [{
                        "type": "event",
                        "id": f"start-{user_id}",
                        "conversation": {"id": conversation_id},
                        "from": {"id": f"user-{user_id}", "name": f"User {user_id}"},
                        "value": {"type": "conversationStart"}
                    }]
                })
                assert start_response.status_code == 200
            
            # Step 2: Upload screenshot
            with patch("app.routes.copilot_studio.get_conversation_manager", 
                      return_value=comprehensive_mock_services["conversation_manager"]), \
                 patch("app.routes.copilot_studio.get_rich_formatter",
                      return_value=comprehensive_mock_services["rich_formatter"]):
                
                upload_response = client.post("/copilot-studio/webhook", json={
                    "activities": [{
                        "type": "message",
                        "id": f"upload-{user_id}",
                        "conversation": {"id": conversation_id},
                        "from": {"id": f"user-{user_id}", "name": f"User {user_id}"},
                        "text": "Convert this screenshot to React code",
                        "attachments": [{"contentType": "image/png", "contentUrl": "https://example.com/screenshot.png"}]
                    }]
                })
                assert upload_response.status_code == 200
            
            # Step 3: Generate code
            with patch("app.routes.copilot_studio.get_conversation_manager", 
                      return_value=comprehensive_mock_services["conversation_manager"]), \
                 patch("app.routes.copilot_studio.get_rich_formatter",
                      return_value=comprehensive_mock_services["rich_formatter"]), \
                 patch("app.routes.copilot_studio.get_copilot_service",
                      return_value=comprehensive_mock_services["code_generation"]):
                
                generate_response = client.post("/copilot-studio/webhook", json={
                    "activities": [{
                        "type": "invoke",
                        "id": f"generate-{user_id}",
                        "conversation": {"id": conversation_id},
                        "from": {"id": f"user-{user_id}", "name": f"User {user_id}"},
                        "value": {
                            "action": "generateCode",
                            "framework": "react",
                            "imageUrl": "https://example.com/screenshot.png"
                        }
                    }]
                })
                assert generate_response.status_code == 200
        
        # Run system test
        metrics = await system_tester.run_system_test(
            "complete_user_journey",
            [complete_user_journey],
            concurrent_users=8,
            duration_seconds=20
        )
        
        # System performance assertions
        assert metrics.error_rate <= 0.05, f"Error rate too high: {metrics.error_rate:.2%}"
        assert metrics.throughput_rps >= 2.0, f"Throughput too low: {metrics.throughput_rps:.1f} RPS"
        assert metrics.avg_response_time <= 2.0, f"Average response time too high: {metrics.avg_response_time:.2f}s"
        assert metrics.p95_response_time <= 5.0, f"P95 response time too high: {metrics.p95_response_time:.2f}s"
        assert metrics.memory_peak_mb <= 500, f"Memory usage too high: {metrics.memory_peak_mb:.1f}MB"
    
    @pytest.mark.asyncio
    async def test_high_load_system_stability(self, system_tester, client, comprehensive_mock_services):
        """Test system stability under high load"""
        
        async def high_load_operation(user_id: int):
            """High-frequency operations for load testing"""
            conversation_id = f"load-test-conv-{user_id}-{int(time.time())}"
            
            # Rapid message processing
            with patch("app.routes.copilot_studio.get_conversation_manager", 
                      return_value=comprehensive_mock_services["conversation_manager"]):
                
                response = client.post("/copilot-studio/webhook", json={
                    "activities": [{
                        "type": "message",
                        "id": f"load-msg-{user_id}-{int(time.time())}",
                        "conversation": {"id": conversation_id},
                        "from": {"id": f"load-user-{user_id}", "name": f"Load User {user_id}"},
                        "text": f"Load test message from user {user_id}",
                        "attachments": []
                    }]
                })
                assert response.status_code == 200
        
        # High load test
        metrics = await system_tester.run_system_test(
            "high_load_stability",
            [high_load_operation],
            concurrent_users=25,
            duration_seconds=15
        )
        
        # Stability assertions under load
        assert metrics.error_rate <= 0.10, f"Error rate too high under load: {metrics.error_rate:.2%}"
        assert metrics.throughput_rps >= 10.0, f"Throughput too low under load: {metrics.throughput_rps:.1f} RPS"
        assert metrics.requests_completed >= 100, f"Too few requests completed: {metrics.requests_completed}"
        assert metrics.memory_peak_mb <= 800, f"Memory usage too high under load: {metrics.memory_peak_mb:.1f}MB"
    
    @pytest.mark.asyncio
    async def test_mixed_workload_performance(self, system_tester, client, comprehensive_mock_services):
        """Test system performance with mixed operation types"""
        
        async def conversation_start_operation(user_id: int):
            """Conversation start operations"""
            with patch("app.routes.copilot_studio.get_conversation_manager", 
                      return_value=comprehensive_mock_services["conversation_manager"]):
                response = client.post("/copilot-studio/webhook", json={
                    "activities": [{
                        "type": "event",
                        "id": f"mixed-start-{user_id}-{int(time.time())}",
                        "conversation": {"id": f"mixed-conv-{user_id}"},
                        "from": {"id": f"mixed-user-{user_id}", "name": f"Mixed User {user_id}"},
                        "value": {"type": "conversationStart"}
                    }]
                })
                assert response.status_code == 200
        
        async def message_processing_operation(user_id: int):
            """Message processing operations"""
            with patch("app.routes.copilot_studio.get_conversation_manager", 
                      return_value=comprehensive_mock_services["conversation_manager"]):
                response = client.post("/copilot-studio/webhook", json={
                    "activities": [{
                        "type": "message",
                        "id": f"mixed-msg-{user_id}-{int(time.time())}",
                        "conversation": {"id": f"mixed-conv-{user_id}"},
                        "from": {"id": f"mixed-user-{user_id}", "name": f"Mixed User {user_id}"},
                        "text": f"Mixed workload message from user {user_id}",
                        "attachments": []
                    }]
                })
                assert response.status_code == 200
        
        async def code_generation_operation(user_id: int):
            """Code generation operations"""
            with patch("app.routes.copilot_studio.get_conversation_manager", 
                      return_value=comprehensive_mock_services["conversation_manager"]), \
                 patch("app.routes.copilot_studio.get_rich_formatter",
                      return_value=comprehensive_mock_services["rich_formatter"]), \
                 patch("app.routes.copilot_studio.get_copilot_service",
                      return_value=comprehensive_mock_services["code_generation"]):
                
                framework = ["react", "vue", "html"][user_id % 3]
                response = client.post("/copilot-studio/webhook", json={
                    "activities": [{
                        "type": "invoke",
                        "id": f"mixed-gen-{user_id}-{int(time.time())}",
                        "conversation": {"id": f"mixed-conv-{user_id}"},
                        "from": {"id": f"mixed-user-{user_id}", "name": f"Mixed User {user_id}"},
                        "value": {
                            "action": "generateCode",
                            "framework": framework,
                            "imageUrl": "https://example.com/test.png"
                        }
                    }]
                })
                assert response.status_code == 200
        
        # Mixed workload test
        mixed_operations = [
            conversation_start_operation,
            message_processing_operation,
            code_generation_operation
        ]
        
        metrics = await system_tester.run_system_test(
            "mixed_workload",
            mixed_operations,
            concurrent_users=15,
            duration_seconds=25
        )
        
        # Mixed workload assertions
        assert metrics.error_rate <= 0.08, f"Error rate too high for mixed workload: {metrics.error_rate:.2%}"
        assert metrics.throughput_rps >= 5.0, f"Throughput too low for mixed workload: {metrics.throughput_rps:.1f} RPS"
        assert metrics.avg_response_time <= 1.5, f"Average response time too high: {metrics.avg_response_time:.2f}s"
        assert metrics.requests_completed >= 150, f"Too few requests completed: {metrics.requests_completed}"


class TestSystemResourceManagement:
    """Test system resource management under various conditions"""
    
    @pytest.mark.asyncio
    async def test_memory_management_under_load(self, system_tester, client, comprehensive_mock_services):
        """Test memory management during sustained load"""
        
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
        memory_samples = []
        
        async def memory_intensive_operation(user_id: int):
            """Operations that might consume memory"""
            # Create large conversation with many messages
            conversation_id = f"memory-test-{user_id}"
            
            # Multiple rapid messages
            for msg_num in range(5):
                with patch("app.routes.copilot_studio.get_conversation_manager", 
                          return_value=comprehensive_mock_services["conversation_manager"]):
                    
                    # Create message with substantial content
                    large_content = f"Memory test message {msg_num} " * 100  # ~2KB content
                    
                    response = client.post("/copilot-studio/webhook", json={
                        "activities": [{
                            "type": "message",
                            "id": f"memory-msg-{user_id}-{msg_num}",
                            "conversation": {"id": conversation_id},
                            "from": {"id": f"memory-user-{user_id}", "name": f"Memory User {user_id}"},
                            "text": large_content,
                            "attachments": []
                        }]
                    })
                    assert response.status_code == 200
                
                # Sample memory after each message
                current_memory = psutil.Process().memory_info().rss / 1024 / 1024
                memory_samples.append(current_memory - initial_memory)
                
                await asyncio.sleep(0.02)  # Small delay between messages
        
        # Run memory test
        metrics = await system_tester.run_system_test(
            "memory_management",
            [memory_intensive_operation],
            concurrent_users=10,
            duration_seconds=15
        )
        
        # Memory management assertions
        memory_growth = metrics.memory_peak_mb - initial_memory
        assert memory_growth <= 200, f"Memory growth too high: {memory_growth:.1f}MB"
        
        # Check for memory leaks (growth should be bounded)
        if len(memory_samples) >= 10:
            # Memory growth should stabilize, not keep increasing linearly
            early_avg = statistics.mean(memory_samples[:5])
            late_avg = statistics.mean(memory_samples[-5:])
            growth_rate = (late_avg - early_avg) / early_avg if early_avg > 0 else 0
            assert growth_rate <= 0.5, f"Potential memory leak detected: {growth_rate:.2%} growth rate"
    
    @pytest.mark.asyncio
    async def test_cpu_utilization_efficiency(self, system_tester, client, comprehensive_mock_services):
        """Test CPU utilization efficiency"""
        
        async def cpu_intensive_operation(user_id: int):
            """Operations that exercise CPU"""
            conversation_id = f"cpu-test-{user_id}"
            
            # Rapid-fire requests to exercise processing
            for i in range(3):
                with patch("app.routes.copilot_studio.get_conversation_manager", 
                          return_value=comprehensive_mock_services["conversation_manager"]), \
                     patch("app.routes.copilot_studio.get_rich_formatter",
                          return_value=comprehensive_mock_services["rich_formatter"]), \
                     patch("app.routes.copilot_studio.get_copilot_service",
                          return_value=comprehensive_mock_services["code_generation"]):
                    
                    response = client.post("/copilot-studio/webhook", json={
                        "activities": [{
                            "type": "invoke",
                            "id": f"cpu-gen-{user_id}-{i}",
                            "conversation": {"id": conversation_id},
                            "from": {"id": f"cpu-user-{user_id}", "name": f"CPU User {user_id}"},
                            "value": {
                                "action": "generateCode",
                                "framework": "react",
                                "imageUrl": "https://example.com/complex-ui.png"
                            }
                        }]
                    })
                    assert response.status_code == 200
                
                await asyncio.sleep(0.01)  # Minimal delay for rapid processing
        
        # Run CPU test
        metrics = await system_tester.run_system_test(
            "cpu_utilization",
            [cpu_intensive_operation],
            concurrent_users=12,
            duration_seconds=20
        )
        
        # CPU efficiency assertions
        assert metrics.cpu_avg_percent <= 80, f"Average CPU usage too high: {metrics.cpu_avg_percent:.1f}%"
        assert metrics.throughput_rps >= 8.0, f"Throughput too low for CPU test: {metrics.throughput_rps:.1f} RPS"
        
        # CPU efficiency ratio (throughput per CPU unit)
        cpu_efficiency = metrics.throughput_rps / max(metrics.cpu_avg_percent, 1)
        assert cpu_efficiency >= 0.1, f"CPU efficiency too low: {cpu_efficiency:.3f} RPS per CPU%"


class TestSystemReliability:
    """Test system reliability and error recovery"""
    
    @pytest.mark.asyncio
    async def test_error_recovery_and_resilience(self, system_tester, client, comprehensive_mock_services):
        """Test system resilience to errors and recovery"""
        
        # Modify mock to introduce controlled failures
        original_process_message = comprehensive_mock_services["conversation_manager"].process_message.side_effect
        error_count = 0
        
        async def failing_process_message(*args, **kwargs):
            nonlocal error_count
            error_count += 1
            
            # Fail every 4th request to test error handling
            if error_count % 4 == 0:
                raise Exception("Simulated service failure")
            
            return await original_process_message(*args, **kwargs)
        
        comprehensive_mock_services["conversation_manager"].process_message.side_effect = failing_process_message
        
        async def resilience_test_operation(user_id: int):
            """Operations that should be resilient to failures"""
            conversation_id = f"resilience-test-{user_id}"
            
            try:
                with patch("app.routes.copilot_studio.get_conversation_manager", 
                          return_value=comprehensive_mock_services["conversation_manager"]):
                    
                    response = client.post("/copilot-studio/webhook", json={
                        "activities": [{
                            "type": "message",
                            "id": f"resilience-msg-{user_id}-{int(time.time())}",
                            "conversation": {"id": conversation_id},
                            "from": {"id": f"resilience-user-{user_id}", "name": f"Resilience User {user_id}"},
                            "text": f"Resilience test message from user {user_id}",
                            "attachments": []
                        }]
                    })
                    
                    # Should handle errors gracefully and return valid response
                    assert response.status_code in [200, 500]  # Either success or handled error
                    
            except Exception as e:
                # If exceptions bubble up, the system isn't resilient enough
                pytest.fail(f"Unhandled exception in resilience test: {e}")
        
        # Run resilience test
        metrics = await system_tester.run_system_test(
            "error_recovery_resilience",
            [resilience_test_operation],
            concurrent_users=16,
            duration_seconds=20
        )
        
        # Resilience assertions
        # System should handle errors gracefully, not crash
        assert metrics.requests_completed > 0, "System should complete some requests despite errors"
        
        # Error rate should be reasonable (failures are handled, not propagated)
        # Note: This depends on how the webhook handler deals with service failures
        total_requests = metrics.requests_completed + metrics.requests_failed
        expected_service_failure_rate = 0.25  # We fail every 4th request
        
        # The system should either:
        # 1. Handle service failures gracefully (low error rate)
        # 2. Or properly propagate them as HTTP errors (higher but controlled error rate)
        assert metrics.error_rate <= 0.30, f"Error rate too high even with controlled failures: {metrics.error_rate:.2%}"
        
        # System should maintain reasonable throughput despite failures
        assert metrics.throughput_rps >= 5.0, f"Throughput too low with failures: {metrics.throughput_rps:.1f} RPS"


class TestSystemScalability:
    """Test system scalability characteristics"""
    
    @pytest.mark.asyncio
    async def test_scalability_characteristics(self, system_tester, client, comprehensive_mock_services):
        """Test how system performance scales with load"""
        
        scalability_results = []
        
        async def scalability_operation(user_id: int):
            """Standard operation for scalability testing"""
            conversation_id = f"scale-test-{user_id}"
            
            with patch("app.routes.copilot_studio.get_conversation_manager", 
                      return_value=comprehensive_mock_services["conversation_manager"]):
                
                response = client.post("/copilot-studio/webhook", json={
                    "activities": [{
                        "type": "message",
                        "id": f"scale-msg-{user_id}-{int(time.time())}",
                        "conversation": {"id": conversation_id},
                        "from": {"id": f"scale-user-{user_id}", "name": f"Scale User {user_id}"},
                        "text": f"Scalability test message from user {user_id}",
                        "attachments": []
                    }]
                })
                assert response.status_code == 200
        
        # Test different load levels
        load_levels = [5, 10, 20]  # concurrent users
        
        for load_level in load_levels:
            metrics = await system_tester.run_system_test(
                f"scalability_{load_level}_users",
                [scalability_operation],
                concurrent_users=load_level,
                duration_seconds=15
            )
            
            scalability_results.append({
                "load_level": load_level,
                "throughput": metrics.throughput_rps,
                "avg_response_time": metrics.avg_response_time,
                "error_rate": metrics.error_rate,
                "memory_peak": metrics.memory_peak_mb
            })
        
        # Analyze scalability characteristics
        for i, result in enumerate(scalability_results):
            load_level = result["load_level"]
            
            # Basic performance requirements at each level
            assert result["error_rate"] <= 0.10, f"Error rate too high at {load_level} users: {result['error_rate']:.2%}"
            assert result["throughput"] >= load_level * 0.8, f"Throughput too low at {load_level} users: {result['throughput']:.1f} RPS"
            
            # Memory usage should scale reasonably
            memory_per_user = result["memory_peak"] / load_level
            assert memory_per_user <= 50, f"Memory per user too high at {load_level} users: {memory_per_user:.1f}MB/user"
        
        # Compare scaling efficiency
        if len(scalability_results) >= 2:
            light_load = scalability_results[0]
            heavy_load = scalability_results[-1]
            
            # Response time degradation should be reasonable
            response_time_ratio = heavy_load["avg_response_time"] / max(light_load["avg_response_time"], 0.01)
            assert response_time_ratio <= 3.0, f"Response time degrades too much under load: {response_time_ratio:.1f}x"
            
            # Throughput should scale reasonably (not perfectly linear, but should increase)
            throughput_ratio = heavy_load["throughput"] / max(light_load["throughput"], 0.1)
            load_ratio = heavy_load["load_level"] / light_load["load_level"]
            scaling_efficiency = throughput_ratio / load_ratio
            
            assert scaling_efficiency >= 0.5, f"Scaling efficiency too low: {scaling_efficiency:.2f}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])