"""
Tests for monitoring and observability components
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

from app.monitoring.prometheus_metrics import PrometheusMetrics, MetricLabels
from app.monitoring.opentelemetry_tracing import TracingManager, TraceConfig
from app.monitoring.alerting import AlertManager, AlertRule, AlertSeverity, Alert
from app.middleware.monitoring import MonitoringMiddleware


class TestPrometheusMetrics:
    """Test Prometheus metrics collection"""
    
    def test_metrics_initialization(self, test_settings, mock_logger):
        """Test metrics initialization"""
        metrics = PrometheusMetrics(test_settings, mock_logger)
        
        assert metrics.settings == test_settings
        assert metrics.logger == mock_logger
        assert len(metrics.registry._collector_to_names) > 0
        
        # Check base labels
        assert metrics.base_labels.service == test_settings.service_name
        assert metrics.base_labels.environment == test_settings.environment.value
    
    def test_http_request_recording(self, test_settings, mock_logger):
        """Test HTTP request metrics recording"""
        metrics = PrometheusMetrics(test_settings, mock_logger)
        
        # Record a successful request
        metrics.record_http_request(
            method="GET",
            endpoint="/api/v1/health",
            status_code=200,
            duration=0.25,
            request_size=1024,
            response_size=2048
        )
        
        # Check that metrics were recorded
        prometheus_output = metrics.get_metrics()
        assert "http_requests_total" in prometheus_output
        assert "http_request_duration_seconds" in prometheus_output
        assert "http_request_size_bytes" in prometheus_output
        assert "http_response_size_bytes" in prometheus_output
    
    def test_business_metrics_recording(self, test_settings, mock_logger):
        """Test business metrics recording"""
        metrics = PrometheusMetrics(test_settings, mock_logger)
        
        # Record code generation
        metrics.record_code_generation(
            framework="react",
            duration=5.0,
            success=True
        )
        
        # Record image generation
        metrics.record_image_generation(
            duration=2.0,
            success=False
        )
        
        prometheus_output = metrics.get_metrics()
        assert "code_generations_total" in prometheus_output
        assert "code_generation_duration_seconds" in prometheus_output
        assert "image_generations_total" in prometheus_output
        assert "image_generation_duration_seconds" in prometheus_output
    
    def test_infrastructure_metrics(self, test_settings, mock_logger):
        """Test infrastructure metrics recording"""
        metrics = PrometheusMetrics(test_settings, mock_logger)
        
        # Record circuit breaker metrics
        metrics.record_circuit_breaker_request("test_service", "closed", "success")
        metrics.update_circuit_breaker_state("test_service", "open")
        metrics.update_circuit_breaker_failure_rate("test_service", 0.15)
        
        # Record service discovery metrics
        metrics.update_service_instances("test_service", "healthy", 2)
        metrics.record_health_check("test_service", True)
        
        prometheus_output = metrics.get_metrics()
        assert "circuit_breaker_requests_total" in prometheus_output
        assert "circuit_breaker_state" in prometheus_output
        assert "circuit_breaker_failure_rate" in prometheus_output
        assert "service_instances_total" in prometheus_output
        assert "service_health_checks_total" in prometheus_output
    
    def test_security_metrics(self, test_settings, mock_logger):
        """Test security metrics recording"""
        metrics = PrometheusMetrics(test_settings, mock_logger)
        
        # Record authentication attempts
        metrics.record_auth_attempt(True, "jwt")
        metrics.record_auth_attempt(False, "jwt")
        
        # Record rate limiting
        metrics.record_rate_limit_check(True)
        metrics.record_rate_limit_check(False, "client_123")
        
        # Record security events
        metrics.record_security_event("suspicious_activity", "high")
        
        prometheus_output = metrics.get_metrics()
        assert "auth_attempts_total" in prometheus_output
        assert "rate_limit_requests_total" in prometheus_output
        assert "rate_limit_violations_total" in prometheus_output
        assert "security_events_total" in prometheus_output
    
    def test_summary_stats(self, test_settings, mock_logger):
        """Test summary statistics"""
        metrics = PrometheusMetrics(test_settings, mock_logger)
        
        # Record some requests
        metrics.record_http_request("GET", "/test", 200, 0.1)
        metrics.record_http_request("POST", "/test", 500, 0.3)
        
        stats = metrics.get_summary_stats()
        
        assert "total_requests" in stats
        assert "successful_requests" in stats
        assert "failed_requests" in stats
        assert "success_rate" in stats
        assert "metrics_collected" in stats
        assert "uptime_seconds" in stats


class TestTracingManager:
    """Test OpenTelemetry tracing"""
    
    def test_tracing_initialization(self, test_settings, mock_logger):
        """Test tracing manager initialization"""
        tracing = TracingManager(test_settings, mock_logger)
        
        assert tracing.settings == test_settings
        assert tracing.logger == mock_logger
        assert tracing.config.service_name == test_settings.service_name
        assert tracing.tracer is not None
        assert tracing.tracer_provider is not None
    
    def test_span_creation(self, test_settings, mock_logger):
        """Test span creation"""
        tracing = TracingManager(test_settings, mock_logger)
        
        # Create a span
        span = tracing.create_span(
            name="test_operation",
            attributes={"test.attribute": "test_value"}
        )
        
        assert span is not None
        assert span.name == "test_operation"
    
    @pytest.mark.asyncio
    async def test_trace_request_context(self, test_settings, mock_logger):
        """Test request tracing context manager"""
        tracing = TracingManager(test_settings, mock_logger)
        
        async with tracing.trace_request(
            operation_name="test_request",
            attributes={"http.method": "GET", "http.url": "/test"}
        ) as span:
            assert span is not None
            span.set_attribute("custom.attribute", "custom_value")
    
    @pytest.mark.asyncio
    async def test_downstream_call_tracing(self, test_settings, mock_logger):
        """Test downstream service call tracing"""
        tracing = TracingManager(test_settings, mock_logger)
        
        async with tracing.trace_downstream_call(
            service_name="test_service",
            operation="test_operation",
            url="http://test-service/api",
            method="POST"
        ) as (span, headers):
            assert span is not None
            assert isinstance(headers, dict)
            # Headers should contain trace context for propagation
    
    def test_span_context_extraction(self, test_settings, mock_logger):
        """Test span context extraction"""
        tracing = TracingManager(test_settings, mock_logger)
        
        # This might return None if no active span
        span_context = tracing.get_current_span_context()
        # Just test that it doesn't raise an exception
        assert span_context is None or hasattr(span_context, 'trace_id')
    
    @pytest.mark.asyncio
    async def test_flush_spans(self, test_settings, mock_logger):
        """Test span flushing"""
        tracing = TracingManager(test_settings, mock_logger)
        
        # Should not raise an exception
        await tracing.flush_spans(timeout_seconds=1.0)
    
    @pytest.mark.asyncio
    async def test_shutdown(self, test_settings, mock_logger):
        """Test tracing shutdown"""
        tracing = TracingManager(test_settings, mock_logger)
        
        # Should not raise an exception
        await tracing.shutdown()


class TestAlertManager:
    """Test alerting system"""
    
    @pytest.mark.asyncio
    async def test_alert_manager_initialization(self, test_settings, mock_logger):
        """Test alert manager initialization"""
        alert_manager = AlertManager(test_settings, mock_logger)
        
        assert alert_manager.settings == test_settings
        assert alert_manager.logger == mock_logger
        assert len(alert_manager.alert_rules) > 0
        assert len(alert_manager.notification_channels) >= 0
    
    @pytest.mark.asyncio
    async def test_alert_rule_evaluation(self, test_settings, mock_logger):
        """Test alert rule evaluation"""
        alert_manager = AlertManager(test_settings, mock_logger)
        
        # Create a test rule
        rule = AlertRule(
            name="test_rule",
            condition="error_rate > 0.05",
            severity=AlertSeverity.HIGH,
            message_template="Test alert: {error_rate}",
            channels=["email"],
            threshold=0.05
        )
        
        # Test evaluation with different metrics
        metrics = {"error_rate": 0.10}
        should_fire = await alert_manager._evaluate_rule(rule, metrics)
        assert should_fire == True
        
        metrics = {"error_rate": 0.02}
        should_fire = await alert_manager._evaluate_rule(rule, metrics)
        assert should_fire == False
    
    def test_alert_creation(self, test_settings, mock_logger):
        """Test alert creation"""
        alert_manager = AlertManager(test_settings, mock_logger)
        
        rule = AlertRule(
            name="test_alert",
            condition="test_condition",
            severity=AlertSeverity.CRITICAL,
            message_template="Test message",
            channels=["email"],
            threshold=1.0
        )
        
        alert = Alert(
            rule_name=rule.name,
            severity=rule.severity,
            status=alert_manager.AlertStatus.FIRING,
            message="Test alert message",
            labels={"service": "test"}
        )
        
        assert alert.rule_name == "test_alert"
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.fingerprint is not None
    
    def test_alert_acknowledgment(self, test_settings, mock_logger):
        """Test alert acknowledgment"""
        alert_manager = AlertManager(test_settings, mock_logger)
        
        # Create and add an alert
        alert = Alert(
            rule_name="test_alert",
            severity=AlertSeverity.HIGH,
            status=alert_manager.AlertStatus.FIRING,
            message="Test message",
            labels={"service": "test"}
        )
        
        alert_manager.active_alerts[alert.fingerprint] = alert
        
        # Acknowledge the alert
        alert_manager.acknowledge_alert(alert.fingerprint, "test_user")
        
        acknowledged_alert = alert_manager.active_alerts[alert.fingerprint]
        assert acknowledged_alert.status == alert_manager.AlertStatus.ACKNOWLEDGED
        assert acknowledged_alert.acknowledged_by == "test_user"
    
    def test_alert_suppression(self, test_settings, mock_logger):
        """Test alert suppression"""
        alert_manager = AlertManager(test_settings, mock_logger)
        
        # Create and add an alert
        alert = Alert(
            rule_name="test_alert",
            severity=AlertSeverity.MEDIUM,
            status=alert_manager.AlertStatus.FIRING,
            message="Test message",
            labels={"service": "test"}
        )
        
        alert_manager.active_alerts[alert.fingerprint] = alert
        
        # Suppress the alert
        alert_manager.suppress_alert(alert.fingerprint, 60)  # 60 minutes
        
        suppressed_alert = alert_manager.active_alerts[alert.fingerprint]
        assert suppressed_alert.status == alert_manager.AlertStatus.SUPPRESSED
        assert suppressed_alert.suppressed_until is not None
    
    def test_alert_statistics(self, test_settings, mock_logger):
        """Test alert statistics"""
        alert_manager = AlertManager(test_settings, mock_logger)
        
        # Add some test alerts
        for i in range(3):
            alert = Alert(
                rule_name=f"test_alert_{i}",
                severity=AlertSeverity.HIGH,
                status=alert_manager.AlertStatus.FIRING,
                message=f"Test message {i}",
                labels={"service": "test"}
            )
            alert_manager.active_alerts[alert.fingerprint] = alert
        
        stats = alert_manager.get_alert_stats()
        
        assert "active_alerts" in stats
        assert "active_by_severity" in stats
        assert "total_rules" in stats
        assert "enabled_rules" in stats
        assert stats["active_alerts"] == 3


class TestMonitoringMiddleware:
    """Test monitoring middleware"""
    
    @pytest.mark.asyncio
    async def test_monitoring_middleware_creation(self, test_settings, mock_logger):
        """Test monitoring middleware creation"""
        # Mock the monitoring components
        mock_metrics = Mock(spec=PrometheusMetrics)
        mock_tracing = Mock(spec=TracingManager)
        mock_alerting = Mock(spec=AlertManager)
        
        # Create middleware
        middleware = MonitoringMiddleware(
            app=Mock(),
            metrics=mock_metrics,
            tracing=mock_tracing,
            alerting=mock_alerting,
            logger=mock_logger
        )
        
        assert middleware.metrics == mock_metrics
        assert middleware.tracing == mock_tracing
        assert middleware.alerting == mock_alerting
        assert middleware.logger == mock_logger
    
    @pytest.mark.asyncio
    async def test_middleware_stats(self, test_settings, mock_logger):
        """Test middleware statistics"""
        mock_metrics = Mock(spec=PrometheusMetrics)
        mock_tracing = Mock(spec=TracingManager)
        mock_alerting = Mock(spec=AlertManager)
        
        middleware = MonitoringMiddleware(
            app=Mock(),
            metrics=mock_metrics,
            tracing=mock_tracing,
            alerting=mock_alerting,
            logger=mock_logger
        )
        
        stats = await middleware.get_middleware_stats()
        
        assert "active_requests" in stats
        assert "monitoring_components" in stats
        assert stats["monitoring_components"]["metrics"] == "prometheus"
        assert stats["monitoring_components"]["tracing"] == "opentelemetry"


class TestMonitoringEndpoints:
    """Test monitoring API endpoints"""
    
    def test_metrics_endpoint(self, client: TestClient):
        """Test Prometheus metrics endpoint"""
        response = client.get("/api/v1/metrics")
        
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        
        content = response.text
        assert "http_requests_total" in content or "# HELP" in content
    
    def test_metrics_summary_endpoint(self, client: TestClient):
        """Test metrics summary endpoint"""
        response = client.get("/api/v1/metrics/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "timestamp" in data
        assert "correlation_id" in data
        assert "service" in data
        assert "metrics_summary" in data
    
    def test_trace_info_endpoint(self, client: TestClient):
        """Test trace information endpoint"""
        response = client.get("/api/v1/trace")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "timestamp" in data
        assert "correlation_id" in data
        assert "trace_context" in data
        assert "tracing_config" in data
    
    def test_alerts_endpoint(self, client: TestClient):
        """Test alerts endpoint"""
        response = client.get("/api/v1/alerts")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "timestamp" in data
        assert "alerts" in data
        assert "total_count" in data
    
    def test_alert_stats_endpoint(self, client: TestClient):
        """Test alert statistics endpoint"""
        response = client.get("/api/v1/alerts/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "timestamp" in data
        assert "alert_statistics" in data
    
    def test_observability_overview_endpoint(self, client: TestClient):
        """Test observability overview endpoint"""
        response = client.get("/api/v1/observability")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "timestamp" in data
        assert "observability" in data
        assert "health" in data
        
        observability = data["observability"]
        assert "metrics" in observability
        assert "tracing" in observability
        assert "alerting" in observability
        assert "logging" in observability
    
    def test_test_alert_endpoint(self, client: TestClient):
        """Test test alert trigger endpoint"""
        response = client.post("/api/v1/test/alert?severity=warning&message=Test alert")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert data["status"] == "success"
        assert "Test alert triggered" in data["message"]


class TestMonitoringIntegration:
    """Integration tests for monitoring system"""
    
    @pytest.mark.asyncio
    async def test_full_monitoring_integration(self, test_settings, mock_logger):
        """Test full monitoring system integration"""
        # Initialize all components
        metrics = PrometheusMetrics(test_settings, mock_logger)
        tracing = TracingManager(test_settings, mock_logger)
        alert_manager = AlertManager(test_settings, mock_logger)
        
        await alert_manager.start()
        
        try:
            # Test metrics recording
            metrics.record_http_request("GET", "/test", 200, 0.1)
            
            # Test tracing
            async with tracing.trace_request("test_operation") as span:
                span.set_attribute("test.key", "test.value")
            
            # Test alert evaluation (mock)
            stats = alert_manager.get_alert_stats()
            assert "active_alerts" in stats
            
            # Test metrics export
            prometheus_output = metrics.get_metrics()
            assert len(prometheus_output) > 0
            
        finally:
            await alert_manager.stop()
            await tracing.shutdown()
    
    def test_monitoring_middleware_integration(self, test_app_with_monitoring):
        """Test monitoring middleware integration with FastAPI app"""
        client = TestClient(test_app_with_monitoring)
        
        # Make a request that should be monitored
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        
        # Check that response has monitoring headers
        assert "X-Response-Time" in response.headers
        
        # Check metrics endpoint works
        metrics_response = client.get("/api/v1/metrics")
        assert metrics_response.status_code == 200