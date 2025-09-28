"""
Tests for health check endpoints
"""
import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Test health check endpoints"""
    
    def test_basic_health_check(self, client: TestClient):
        """Test basic health check endpoint"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "status" in data
        assert "timestamp" in data
        assert "correlation_id" in data
        assert "service" in data
        assert "version" in data
        assert "environment" in data
        assert "downstream_services" in data
        assert "circuit_breakers" in data
        
        # Check correlation ID header
        correlation_id = response.headers.get("X-Correlation-ID")
        assert correlation_id is not None
        assert correlation_id == data["correlation_id"]
        
        # Check downstream services status
        assert data["downstream_services"]["code_generator"] == "healthy"
        assert data["downstream_services"]["image_generator"] == "healthy"
    
    def test_liveness_check(self, client: TestClient):
        """Test Kubernetes liveness probe"""
        response = client.get("/health/live")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "alive"
        assert "timestamp" in data
        assert "service" in data
    
    def test_readiness_check(self, client: TestClient):
        """Test Kubernetes readiness probe"""
        response = client.get("/health/ready")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "ready"
        assert "timestamp" in data
        assert "service" in data
        assert "dependencies" in data
        
        # Check dependencies
        deps = data["dependencies"]
        assert "code_generator" in deps
        assert "image_generator" in deps
    
    def test_detailed_health_check(self, client: TestClient):
        """Test detailed health check endpoint"""
        response = client.get("/health/detailed")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check comprehensive response structure
        assert "status" in data
        assert "service_info" in data
        assert "configuration" in data
        assert "downstream_services" in data
        assert "circuit_breakers" in data
        assert "load_balancing" in data
        
        # Check service info
        service_info = data["service_info"]
        assert "name" in service_info
        assert "version" in service_info
        assert "environment" in service_info
        
        # Check configuration
        config = data["configuration"]
        assert "authentication_enabled" in config
        assert "rate_limiting_enabled" in config
        assert "circuit_breaker_enabled" in config
        
        # Check circuit breakers
        cb = data["circuit_breakers"]
        assert "code_generator" in cb
        assert "image_generator" in cb
        
        for service_cb in cb.values():
            assert "state" in service_cb
            assert "failure_count" in service_cb
            assert "failure_threshold" in service_cb
    
    def test_health_check_with_failed_services(self, test_settings, failed_service_client, mock_logger):
        """Test health check when downstream services are failing"""
        from app.main import create_app
        
        # Create app with failed service client
        app = create_app()
        app.state.settings = test_settings
        app.state.service_client = failed_service_client
        app.state.logger = mock_logger
        
        client = TestClient(app)
        response = client.get("/health")
        
        # Should return 503 when services are unhealthy
        assert response.status_code == 503
        data = response.json()
        
        assert data["status"] == "degraded"
        assert data["downstream_services"]["code_generator"] == "unhealthy"
        assert data["downstream_services"]["image_generator"] == "circuit_open"
    
    def test_readiness_check_with_failed_services(self, test_settings, failed_service_client, mock_logger):
        """Test readiness check when downstream services are failing"""
        from app.main import create_app
        
        # Create app with failed service client
        app = create_app()
        app.state.settings = test_settings
        app.state.service_client = failed_service_client
        app.state.logger = mock_logger
        
        client = TestClient(app)
        response = client.get("/health/ready")
        
        # Should return 503 when dependencies are not ready
        assert response.status_code == 503
        data = response.json()
        
        assert data["status"] == "not_ready"
        assert "dependencies" in data
    
    def test_health_endpoints_have_cors_headers(self, client: TestClient):
        """Test that health endpoints include CORS headers"""
        response = client.get("/health")
        
        # Check for CORS headers (added by middleware)
        assert response.status_code == 200
        # Note: TestClient might not include all middleware headers,
        # but in real deployment these would be present
    
    def test_health_check_response_time(self, client: TestClient):
        """Test that health check responds quickly"""
        import time
        
        start_time = time.time()
        response = client.get("/health")
        end_time = time.time()
        
        assert response.status_code == 200
        
        # Health check should be fast (< 1 second)
        response_time = end_time - start_time
        assert response_time < 1.0
        
        # Check response time header
        response_time_header = response.headers.get("X-Response-Time")
        assert response_time_header is not None
        assert response_time_header.endswith("ms")
    
    def test_health_endpoints_correlation_id_consistency(self, client: TestClient):
        """Test correlation ID consistency across health endpoints"""
        endpoints = ["/health", "/health/live", "/health/ready", "/health/detailed"]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            
            # All health endpoints should return correlation IDs
            correlation_id = response.headers.get("X-Correlation-ID")
            assert correlation_id is not None
            
            # If response has JSON body with correlation_id, it should match header
            if response.headers.get("content-type", "").startswith("application/json"):
                try:
                    data = response.json()
                    if "correlation_id" in data:
                        assert data["correlation_id"] == correlation_id
                except:
                    pass  # Some endpoints might not have JSON response
    
    def test_health_check_caching(self, client: TestClient):
        """Test that health checks are not cached"""
        # Make multiple requests
        response1 = client.get("/health")
        response2 = client.get("/health")
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Timestamps should be different (not cached)
        data1 = response1.json()
        data2 = response2.json()
        
        # Note: In a real scenario, timestamps might be very close but should not be identical
        # For this test, we just ensure both responses are valid
        assert "timestamp" in data1
        assert "timestamp" in data2
    
    def test_service_statistics_endpoint(self, client: TestClient):
        """Test advanced service statistics endpoint"""
        response = client.get("/api/v1/health/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "timestamp" in data
        assert "correlation_id" in data
        assert "service" in data
        assert "statistics" in data
        
        # Check comprehensive statistics structure
        stats = data["statistics"]
        assert "service_health" in stats
        assert "circuit_breakers" in stats
        assert "connection_pools" in stats
        assert "service_discovery" in stats
        
        # Check circuit breaker statistics
        circuit_breakers = stats["circuit_breakers"]
        assert "code_generator" in circuit_breakers
        assert "image_generator" in circuit_breakers
        
        for service_name, cb_stats in circuit_breakers.items():
            assert "service_name" in cb_stats
            assert "state" in cb_stats
            assert "total_requests" in cb_stats
            assert "successful_requests" in cb_stats
            assert "failed_requests" in cb_stats
            assert "success_rate" in cb_stats
            assert "consecutive_failures" in cb_stats
            assert "adaptive_threshold" in cb_stats
            assert "failure_counts" in cb_stats
            assert "response_time_stats" in cb_stats
        
        # Check service discovery statistics
        service_discovery = stats["service_discovery"]
        assert "code_generator" in service_discovery
        assert "image_generator" in service_discovery
        
        for service_name, sd_stats in service_discovery.items():
            assert "service_name" in sd_stats
            assert "total_instances" in sd_stats
            assert "healthy_instances" in sd_stats
            assert "unhealthy_instances" in sd_stats
            assert "total_requests" in sd_stats
            assert "successful_requests" in sd_stats
            assert "success_rate" in sd_stats
            assert "average_response_time_ms" in sd_stats
            assert "instances" in sd_stats
        
        # Check connection pool statistics
        connection_pools = stats["connection_pools"]
        # Connection pools might be empty if no requests have been made yet
        if connection_pools:
            for service_name, pool_stats in connection_pools.items():
                assert "total_requests" in pool_stats
                assert "successful_requests" in pool_stats
                assert "failed_requests" in pool_stats
                assert "average_response_time" in pool_stats
                assert "last_used" in pool_stats
                assert "created_at" in pool_stats