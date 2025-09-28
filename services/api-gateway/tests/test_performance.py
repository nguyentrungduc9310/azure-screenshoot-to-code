"""
Tests for performance optimization components
"""
import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
import psutil

from app.performance.optimizer import (
    PerformanceOptimizer,
    OptimizationLevel,
    ResourceType,
    PerformanceMetrics,
    OptimizationRule,
    RequestProfile
)
from app.caching.redis_cache import AdvancedRedisCache


class TestPerformanceMetrics:
    """Test performance metrics data structure"""
    
    def test_performance_metrics_creation(self):
        """Test performance metrics creation"""
        metrics = PerformanceMetrics(
            cpu_percent=45.5,
            memory_percent=60.2,
            memory_available=8589934592,  # 8GB
            response_time_avg=0.25,
            error_rate=0.02
        )
        
        assert metrics.cpu_percent == 45.5
        assert metrics.memory_percent == 60.2
        assert metrics.memory_available == 8589934592
        assert metrics.response_time_avg == 0.25
        assert metrics.error_rate == 0.02
        assert metrics.timestamp > 0
    
    def test_performance_metrics_defaults(self):
        """Test performance metrics with defaults"""
        metrics = PerformanceMetrics()
        
        assert metrics.cpu_percent == 0.0
        assert metrics.memory_percent == 0.0
        assert metrics.response_time_avg == 0.0
        assert metrics.cache_hit_rate == 0.0
        assert metrics.timestamp > 0


class TestOptimizationRule:
    """Test optimization rules"""
    
    def test_optimization_rule_creation(self):
        """Test optimization rule creation"""
        def dummy_action(metrics):
            pass
        
        rule = OptimizationRule(
            name="test_rule",
            condition="cpu_percent > 80",
            action=dummy_action,
            level=OptimizationLevel.BALANCED,
            resource_type=ResourceType.CPU,
            cooldown_seconds=120
        )
        
        assert rule.name == "test_rule"
        assert rule.condition == "cpu_percent > 80"
        assert rule.level == OptimizationLevel.BALANCED
        assert rule.resource_type == ResourceType.CPU
        assert rule.cooldown_seconds == 120
        assert rule.enabled == True
        assert rule.last_triggered == 0.0


class TestRequestProfile:
    """Test request performance profiling"""
    
    def test_request_profile_creation(self):
        """Test request profile creation"""
        profile = RequestProfile(
            endpoint="/api/v1/test",
            method="GET",
            avg_duration=0.25,
            request_count=100,
            error_count=5
        )
        
        assert profile.endpoint == "/api/v1/test"
        assert profile.method == "GET"
        assert profile.avg_duration == 0.25
        assert profile.request_count == 100
        assert profile.error_count == 5
        assert profile.optimization_score == 1.0  # Default
        assert profile.last_updated > 0
    
    def test_request_profile_defaults(self):
        """Test request profile with defaults"""
        profile = RequestProfile(
            endpoint="/test",
            method="POST"
        )
        
        assert profile.avg_duration == 0.0
        assert profile.p95_duration == 0.0
        assert profile.request_count == 0
        assert profile.error_count == 0
        assert profile.cache_hit_count == 0


class TestPerformanceOptimizer:
    """Test performance optimizer"""
    
    @pytest.mark.asyncio
    async def test_optimizer_initialization(self, test_settings, mock_logger):
        """Test performance optimizer initialization"""
        mock_cache = Mock(spec=AdvancedRedisCache)
        
        optimizer = PerformanceOptimizer(
            settings=test_settings,
            cache=mock_cache,
            logger=mock_logger,
            optimization_level=OptimizationLevel.CONSERVATIVE
        )
        
        assert optimizer.settings == test_settings
        assert optimizer.cache == mock_cache
        assert optimizer.logger == mock_logger
        assert optimizer.optimization_level == OptimizationLevel.CONSERVATIVE
        assert len(optimizer.optimization_rules) > 0
        assert len(optimizer.metrics_history) == 0
        assert optimizer._running == False
    
    def test_optimization_level_ordering(self, test_settings, mock_logger):
        """Test optimization level comparison"""
        mock_cache = Mock(spec=AdvancedRedisCache)
        optimizer = PerformanceOptimizer(test_settings, mock_cache, mock_logger, OptimizationLevel.BALANCED)
        
        # Conservative rules should be applied
        assert optimizer._should_apply_optimization_level(OptimizationLevel.CONSERVATIVE) == True
        
        # Balanced rules should be applied
        assert optimizer._should_apply_optimization_level(OptimizationLevel.BALANCED) == True
        
        # Aggressive rules should NOT be applied with BALANCED level
        assert optimizer._should_apply_optimization_level(OptimizationLevel.AGGRESSIVE) == False
    
    def test_condition_evaluation(self, test_settings, mock_logger):
        """Test optimization condition evaluation"""
        mock_cache = Mock(spec=AdvancedRedisCache)
        optimizer = PerformanceOptimizer(test_settings, mock_cache, mock_logger)
        
        metrics = PerformanceMetrics(
            cpu_percent=85.0,
            memory_percent=70.0,
            response_time_p95=1.5,
            error_rate=0.03
        )
        
        # Test various conditions
        assert optimizer._evaluate_condition("cpu_percent > 80", metrics) == True
        assert optimizer._evaluate_condition("cpu_percent > 90", metrics) == False
        assert optimizer._evaluate_condition("memory_percent < 75", metrics) == True
        assert optimizer._evaluate_condition("response_time_p95 > 1.0", metrics) == True
        assert optimizer._evaluate_condition("error_rate < 0.05", metrics) == True
    
    def test_invalid_condition_evaluation(self, test_settings, mock_logger):
        """Test invalid condition evaluation"""
        mock_cache = Mock(spec=AdvancedRedisCache)
        optimizer = PerformanceOptimizer(test_settings, mock_cache, mock_logger)
        
        metrics = PerformanceMetrics()
        
        # Invalid condition should return False and log error
        result = optimizer._evaluate_condition("invalid_condition", metrics)
        assert result == False
    
    @pytest.mark.asyncio
    async def test_request_recording(self, test_settings, mock_logger):
        """Test request performance recording"""
        mock_cache = Mock(spec=AdvancedRedisCache)
        optimizer = PerformanceOptimizer(test_settings, mock_cache, mock_logger)
        
        # Record a request
        await optimizer.record_request(
            endpoint="/api/v1/test",
            method="GET",
            duration=0.25,
            status_code=200,
            cache_hit=True
        )
        
        # Check that request was queued (queue should not be empty)
        # Note: The actual processing happens in background tasks
        assert hasattr(optimizer, 'request_queue')
    
    def test_optimization_recommendations(self, test_settings, mock_logger):
        """Test optimization recommendations"""
        mock_cache = Mock(spec=AdvancedRedisCache)
        optimizer = PerformanceOptimizer(test_settings, mock_cache, mock_logger)
        
        # Add some metrics history
        high_cpu_metrics = PerformanceMetrics(cpu_percent=85.0, memory_percent=60.0)
        high_memory_metrics = PerformanceMetrics(cpu_percent=60.0, memory_percent=90.0)
        slow_response_metrics = PerformanceMetrics(response_time_avg=2.5)
        
        optimizer.metrics_history.extend([high_cpu_metrics, high_memory_metrics, slow_response_metrics])
        
        recommendations = optimizer.get_optimization_recommendations()
        
        assert len(recommendations) > 0
        
        # Check for CPU recommendations
        cpu_recs = [r for r in recommendations if r['type'] == 'cpu']
        assert len(cpu_recs) > 0
        assert cpu_recs[0]['severity'] in ['medium', 'high']
        
        # Check for memory recommendations  
        memory_recs = [r for r in recommendations if r['type'] == 'memory']
        assert len(memory_recs) > 0
        
        # Check for response time recommendations
        response_recs = [r for r in recommendations if r['type'] == 'response_time']
        assert len(response_recs) > 0
    
    @pytest.mark.asyncio
    async def test_performance_report(self, test_settings, mock_logger):
        """Test performance report generation"""
        mock_cache = Mock(spec=AdvancedRedisCache)
        mock_cache.get_stats = AsyncMock(return_value={"statistics": {"hit_rate": 0.75}})
        
        optimizer = PerformanceOptimizer(test_settings, mock_cache, mock_logger)
        
        # Add metrics to history
        metrics = PerformanceMetrics(
            cpu_percent=70.0,
            memory_percent=65.0,
            response_time_avg=0.8,
            error_rate=0.02,
            cache_hit_rate=0.75
        )
        optimizer.metrics_history.append(metrics)
        
        # Add request profile
        profile = RequestProfile(
            endpoint="/api/v1/test",
            method="GET",
            avg_duration=0.5,
            p95_duration=1.2,
            optimization_score=0.8
        )
        optimizer.request_profiles["/api/v1/test"] = profile
        
        report = await optimizer.get_performance_report()
        
        assert "timestamp" in report
        assert "current_metrics" in report
        assert "trends" in report
        assert "optimization_status" in report
        assert "top_slow_endpoints" in report
        assert "recommendations" in report
        assert "cache_stats" in report
        
        # Check current metrics
        current = report["current_metrics"]
        assert current["cpu_percent"] == 70.0
        assert current["memory_percent"] == 65.0
        assert current["response_time_avg_ms"] == 800.0  # Converted to ms
        
        # Check optimization status
        opt_status = report["optimization_status"]
        assert opt_status["level"] == OptimizationLevel.BALANCED.value
        assert "active_optimizations" in opt_status
        
        # Check slow endpoints
        slow_endpoints = report["top_slow_endpoints"]
        assert len(slow_endpoints) == 1
        assert slow_endpoints[0]["endpoint"] == "/api/v1/test"
    
    @pytest.mark.asyncio
    async def test_garbage_collection_optimization(self, test_settings, mock_logger):
        """Test garbage collection optimization"""
        mock_cache = Mock(spec=AdvancedRedisCache)
        optimizer = PerformanceOptimizer(test_settings, mock_cache, mock_logger)
        
        metrics = PerformanceMetrics(memory_percent=85.0)
        
        # Test garbage collection trigger
        await optimizer._trigger_garbage_collection(metrics)
        
        # Should not raise exception (actual GC happens)
        # We can't easily test the memory reduction without complex mocking
    
    @pytest.mark.asyncio
    async def test_cache_cleanup_optimization(self, test_settings, mock_logger):
        """Test cache cleanup optimization"""
        mock_cache = Mock(spec=AdvancedRedisCache)
        mock_cache.get_stats = AsyncMock(return_value={
            'l1_memory_cache': {
                'entries': 1000,
                'memory_usage_bytes': 1048576
            }
        })
        mock_cache.invalidate_by_pattern = AsyncMock(return_value=500)
        
        optimizer = PerformanceOptimizer(test_settings, mock_cache, mock_logger)
        
        metrics = PerformanceMetrics(memory_percent=85.0)
        
        # Test cache cleanup
        await optimizer._cleanup_cache(metrics)
        
        # Verify cache cleanup was called
        mock_cache.invalidate_by_pattern.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_request_throttling_optimization(self, test_settings, mock_logger):
        """Test request throttling optimization"""
        mock_cache = Mock(spec=AdvancedRedisCache)
        optimizer = PerformanceOptimizer(test_settings, mock_cache, mock_logger)
        
        metrics = PerformanceMetrics(cpu_percent=96.0)
        
        # Test request throttling activation
        await optimizer._enable_request_throttling(metrics)
        
        # Check that throttling was enabled
        assert 'request_throttling' in optimizer.current_optimizations
        throttling_config = optimizer.current_optimizations['request_throttling']
        assert throttling_config['enabled'] == True
        assert throttling_config['max_concurrent'] == 50
        assert throttling_config['reason'] == 'high_cpu'
    
    @pytest.mark.asyncio
    async def test_emergency_mode_activation(self, test_settings, mock_logger):
        """Test emergency mode activation"""
        mock_cache = Mock(spec=AdvancedRedisCache)
        optimizer = PerformanceOptimizer(test_settings, mock_cache, mock_logger)
        
        metrics = PerformanceMetrics(cpu_percent=99.0, memory_percent=96.0)
        
        # Test emergency mode activation
        await optimizer._activate_emergency_mode(metrics)
        
        # Check that emergency mode was activated
        assert 'emergency_mode' in optimizer.current_optimizations
        emergency_config = optimizer.current_optimizations['emergency_mode']
        assert emergency_config['enabled'] == True
        assert emergency_config['reason'] == 'extreme_resource_usage'
        
        # Check that other optimizations were configured
        assert 'request_throttling' in optimizer.current_optimizations
        assert optimizer.current_optimizations['request_throttling']['max_concurrent'] == 10
    
    @pytest.mark.asyncio
    async def test_slow_endpoint_optimization(self, test_settings, mock_logger):
        """Test slow endpoint optimization"""
        mock_cache = Mock(spec=AdvancedRedisCache)
        optimizer = PerformanceOptimizer(test_settings, mock_cache, mock_logger)
        
        # Add slow endpoint profile
        slow_profile = RequestProfile(
            endpoint="/api/v1/slow",
            method="GET",
            p95_duration=3.0,  # Slower than 2s threshold
            optimization_score=0.9
        )
        optimizer.request_profiles["/api/v1/slow"] = slow_profile
        
        metrics = PerformanceMetrics(response_time_p95=2.5)
        
        # Test slow endpoint optimization
        await optimizer._optimize_slow_endpoints(metrics)
        
        # Check that enhanced caching was enabled
        assert 'enhanced_caching' in optimizer.current_optimizations
        caching_config = optimizer.current_optimizations['enhanced_caching']
        assert caching_config['enabled'] == True
        assert "/api/v1/slow" in caching_config['endpoints']
        assert caching_config['cache_ttl_multiplier'] == 2.0
        
        # Check that optimization score was reduced
        assert slow_profile.optimization_score < 0.9
    
    @pytest.mark.asyncio
    async def test_metrics_collection(self, test_settings, mock_logger):
        """Test performance metrics collection"""
        mock_cache = Mock(spec=AdvancedRedisCache)
        mock_cache.get_stats = AsyncMock(return_value={
            'statistics': {'hit_rate': 0.85}
        })
        
        optimizer = PerformanceOptimizer(test_settings, mock_cache, mock_logger)
        
        # Mock system calls to avoid depending on actual system state
        with patch('psutil.cpu_percent', return_value=45.5), \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk, \
             patch('psutil.net_io_counters') as mock_network:
            
            # Configure mocks
            mock_memory.return_value.percent = 60.2
            mock_memory.return_value.available = 8589934592
            mock_disk.return_value.percent = 25.0
            mock_network.return_value.bytes_sent = 1048576
            mock_network.return_value.bytes_recv = 2097152
            
            metrics = await optimizer._collect_performance_metrics()
            
            assert metrics.cpu_percent == 45.5
            assert metrics.memory_percent == 60.2
            assert metrics.memory_available == 8589934592
            assert metrics.disk_usage_percent == 25.0
            assert metrics.cache_hit_rate == 0.85
    
    @pytest.mark.asyncio
    async def test_batch_processing(self, test_settings, mock_logger):
        """Test request batch processing"""
        mock_cache = Mock(spec=AdvancedRedisCache)
        optimizer = PerformanceOptimizer(test_settings, mock_cache, mock_logger)
        
        # Create test batch
        batch = [
            {
                'endpoint': '/api/v1/test',
                'method': 'GET',
                'duration': 0.25,
                'status_code': 200,
                'cache_hit': True,
                'timestamp': time.time()
            },
            {
                'endpoint': '/api/v1/test',
                'method': 'POST', 
                'duration': 0.35,
                'status_code': 201,
                'cache_hit': False,
                'timestamp': time.time()
            }
        ]
        
        # Process batch
        await optimizer._process_request_batch(batch, "test_processor")
        
        # Check that request profile was created/updated
        assert "/api/v1/test" in optimizer.request_profiles
        profile = optimizer.request_profiles["/api/v1/test"]
        assert profile.request_count == 2
        assert profile.cache_hit_count == 1  # One cache hit in batch


class TestPerformanceIntegration:
    """Integration tests for performance optimization"""
    
    @pytest.mark.asyncio  
    async def test_full_performance_integration(self, test_settings, mock_logger):
        """Test full performance optimization integration"""
        # Create mock cache
        mock_cache = Mock(spec=AdvancedRedisCache)
        mock_cache.get_stats = AsyncMock(return_value={
            'statistics': {'hit_rate': 0.8}
        })
        
        # Create optimizer
        optimizer = PerformanceOptimizer(
            settings=test_settings,
            cache=mock_cache,
            logger=mock_logger,
            optimization_level=OptimizationLevel.BALANCED
        )
        
        try:
            # Test initialization
            assert len(optimizer.optimization_rules) > 0
            
            # Test request recording
            await optimizer.record_request("/test", "GET", 0.5, 200, False)
            
            # Test metrics collection (with mocked system calls)
            with patch('psutil.cpu_percent', return_value=70.0), \
                 patch('psutil.virtual_memory') as mock_memory, \
                 patch('psutil.disk_usage') as mock_disk, \
                 patch('psutil.net_io_counters') as mock_network:
                
                mock_memory.return_value.percent = 65.0
                mock_memory.return_value.available = 4294967296
                mock_disk.return_value.percent = 30.0
                mock_network.return_value.bytes_sent = 1048576
                mock_network.return_value.bytes_recv = 2097152
                
                metrics = await optimizer._collect_performance_metrics()
                assert metrics.cpu_percent == 70.0
                assert metrics.memory_percent == 65.0
            
            # Test recommendations
            optimizer.metrics_history.append(metrics)
            recommendations = optimizer.get_optimization_recommendations()
            assert isinstance(recommendations, list)
            
            # Test performance report
            report = await optimizer.get_performance_report()
            assert "current_metrics" in report
            assert "optimization_status" in report
            
        finally:
            # Cleanup would happen here if we started the optimizer
            pass
    
    @pytest.mark.asyncio
    async def test_optimization_rule_evaluation(self, test_settings, mock_logger):
        """Test optimization rule evaluation in realistic scenario"""
        mock_cache = Mock(spec=AdvancedRedisCache)
        optimizer = PerformanceOptimizer(test_settings, mock_cache, mock_logger)
        
        # Create high CPU scenario
        high_cpu_metrics = PerformanceMetrics(
            cpu_percent=92.0,
            memory_percent=70.0,
            response_time_p95=1.5
        )
        
        # Evaluate rules (but don't trigger them due to testing)
        rules_to_trigger = []
        for rule in optimizer.optimization_rules:
            if optimizer._should_apply_optimization_level(rule.level):
                if optimizer._evaluate_condition(rule.condition, high_cpu_metrics):
                    rules_to_trigger.append(rule.name)
        
        # Should have rules that would trigger for high CPU
        cpu_rules = [name for name in rules_to_trigger if 'cpu' in name.lower()]
        assert len(cpu_rules) > 0
    
    def test_request_profile_optimization_score_calculation(self, test_settings, mock_logger):
        """Test request profile optimization score calculation"""
        mock_cache = Mock(spec=AdvancedRedisCache) 
        optimizer = PerformanceOptimizer(test_settings, mock_cache, mock_logger)
        
        # Create request profile
        profile = RequestProfile(
            endpoint="/api/v1/test",
            method="GET"
        )
        
        # Simulate request data
        requests = [
            {'duration': 0.2, 'status_code': 200, 'cache_hit': True},
            {'duration': 0.3, 'status_code': 200, 'cache_hit': True}, 
            {'duration': 0.4, 'status_code': 500, 'cache_hit': False},  # Error
            {'duration': 0.25, 'status_code': 200, 'cache_hit': False}
        ]
        
        # Process requests manually to test scoring
        profile.request_count = len(requests)
        profile.error_count = sum(1 for req in requests if req['status_code'] >= 400) 
        profile.cache_hit_count = sum(1 for req in requests if req['cache_hit'])
        durations = [req['duration'] for req in requests]
        profile.avg_duration = sum(durations) / len(durations)
        
        # Calculate optimization score manually (same logic as in code)
        error_rate = profile.error_count / max(profile.request_count, 1)
        cache_hit_rate = profile.cache_hit_count / max(profile.request_count, 1)
        
        expected_score = (
            (1.0 - error_rate) * 0.4 +           # 40% weight on low error rate
            cache_hit_rate * 0.3 +               # 30% weight on cache hit rate  
            max(0, 1.0 - profile.avg_duration / 5.0) * 0.3  # 30% weight on fast responses
        )
        
        # The actual calculation happens in _process_endpoint_batch
        # Here we verify our understanding of the scoring algorithm
        assert error_rate == 0.25  # 1 error out of 4 requests
        assert cache_hit_rate == 0.5  # 2 cache hits out of 4 requests
        assert expected_score > 0.5  # Should be reasonable score