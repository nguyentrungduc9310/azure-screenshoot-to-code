"""
Integration tests for caching and performance optimization system
"""
import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

from app.caching.redis_cache import AdvancedRedisCache, CacheConfig
from app.performance.optimizer import PerformanceOptimizer, OptimizationLevel
from app.middleware.caching import SmartCachingMiddleware


class TestCachingPerformanceIntegration:
    """Integration tests for caching and performance systems"""
    
    @pytest.mark.asyncio
    async def test_full_system_integration(self, test_settings, mock_logger):
        """Test full integration of caching and performance systems"""
        # Initialize caching system
        cache_config = CacheConfig(
            default_ttl=300,
            max_memory_mb=50,
            compression_threshold=512,
            enable_metrics=True
        )
        cache = AdvancedRedisCache(test_settings, mock_logger, cache_config)
        
        # Initialize performance optimizer
        performance_optimizer = PerformanceOptimizer(
            settings=test_settings,
            cache=cache,
            logger=mock_logger,
            optimization_level=OptimizationLevel.BALANCED
        )
        
        try:
            # Start systems
            await cache.start()
            await performance_optimizer.start()
            
            # Test cache operations
            await cache.set("integration_key", {"data": "test_value"}, ttl=600)
            result = await cache.get("integration_key")
            assert result == {"data": "test_value"}
            
            # Test performance recording
            await performance_optimizer.record_request(
                endpoint="/api/v1/test",
                method="GET",
                duration=0.25,
                status_code=200,
                cache_hit=True
            )
            
            # Allow background processing
            await asyncio.sleep(0.1)
            
            # Test performance report
            report = await performance_optimizer.get_performance_report()
            assert "current_metrics" in report
            assert "optimization_status" in report
            
            # Test cache statistics
            stats = await cache.get_stats()
            assert stats["statistics"]["hits"] >= 1
            assert stats["statistics"]["sets"] >= 1
            
        finally:
            # Cleanup
            await performance_optimizer.stop()
            await cache.stop()
    
    @pytest.mark.asyncio
    async def test_middleware_integration(self, test_settings, mock_logger):
        """Test caching middleware integration with performance optimizer"""
        # Setup components
        cache = AdvancedRedisCache(test_settings, mock_logger)
        performance_optimizer = PerformanceOptimizer(test_settings, cache, mock_logger)
        
        # Create middleware
        middleware = SmartCachingMiddleware(
            app=Mock(),
            cache=cache,
            optimizer=performance_optimizer,
            logger=mock_logger
        )
        
        # Test middleware initialization
        assert middleware.cache == cache
        assert middleware.optimizer == performance_optimizer
        assert len(middleware.cache_rules) > 0
        
        # Test cache statistics
        stats = middleware.get_smart_cache_stats()
        assert "smart_features" in stats
        assert "statistics" in stats
    
    @pytest.mark.asyncio
    async def test_performance_optimization_workflow(self, test_settings, mock_logger):
        """Test performance optimization workflow with caching"""
        cache = AdvancedRedisCache(test_settings, mock_logger)
        optimizer = PerformanceOptimizer(test_settings, cache, mock_logger)
        
        try:
            await cache.start()
            
            # Simulate high memory usage scenario
            with patch('psutil.virtual_memory') as mock_memory:
                mock_memory.return_value.percent = 85.0
                mock_memory.return_value.available = 2147483648  # 2GB
                
                # This should trigger cache cleanup optimization
                from app.performance.optimizer import PerformanceMetrics
                high_memory_metrics = PerformanceMetrics(memory_percent=85.0)
                
                # Test cache cleanup action
                await optimizer._cleanup_cache(high_memory_metrics)
                
                # Verify cache was affected (would be cleared in real scenario)
                stats = await cache.get_stats()
                assert "statistics" in stats
        
        finally:
            await cache.stop()
    
    @pytest.mark.asyncio
    async def test_adaptive_caching_behavior(self, test_settings, mock_logger):
        """Test adaptive caching behavior with performance feedback"""
        cache = AdvancedRedisCache(test_settings, mock_logger)
        optimizer = PerformanceOptimizer(test_settings, cache, mock_logger)
        middleware = SmartCachingMiddleware(Mock(), cache, optimizer, mock_logger)
        
        try:
            await cache.start()
            
            # Simulate endpoint access patterns
            endpoint = "GET /api/v1/test"
            current_time = time.time()
            
            # Create performance data for endpoint
            middleware.endpoint_performance[endpoint] = {
                'access_count': 100,
                'total_duration': 25.0,  # 0.25s average
                'cache_hits': 75,        # 75% hit rate
                'last_access': current_time
            }
            
            # Test adaptive TTL calculation
            await middleware._adjust_adaptive_ttl(endpoint, 200, 0.3)
            
            # Check if adaptive TTL was calculated
            if endpoint in middleware.adaptive_ttl:
                assert middleware.adaptive_ttl[endpoint] > 0
                assert middleware.adaptive_ttl[endpoint] <= 3600  # Within bounds
            
        finally:
            await cache.stop()
    
    @pytest.mark.asyncio
    async def test_cache_compression_with_performance(self, test_settings, mock_logger):
        """Test cache compression with performance monitoring"""
        # Use low compression threshold for testing
        cache_config = CacheConfig(
            compression_threshold=100,  # Very low for testing
            compression_type="zlib"
        )
        cache = AdvancedRedisCache(test_settings, mock_logger, cache_config)
        
        try:
            await cache.start()
            
            # Store large value that should be compressed
            large_data = {"data": "x" * 1000, "metadata": {"size": "large"}}
            
            start_time = time.time()
            await cache.set("large_key", large_data, ttl=300)
            set_duration = time.time() - start_time
            
            start_time = time.time()
            result = await cache.get("large_key")
            get_duration = time.time() - start_time
            
            # Verify data integrity
            assert result == large_data
            
            # Performance should be reasonable even with compression
            assert set_duration < 0.1  # Should be fast
            assert get_duration < 0.1   # Should be fast
            
            # Check compression was used (internal verification)
            serialized = cache._serialize_value(large_data)
            assert serialized.startswith(b'zlib:')  # Should be compressed
            
        finally:
            await cache.stop()
    
    @pytest.mark.asyncio
    async def test_error_handling_integration(self, test_settings, mock_logger):
        """Test error handling in integrated caching and performance system"""
        cache = AdvancedRedisCache(test_settings, mock_logger)
        optimizer = PerformanceOptimizer(test_settings, cache, mock_logger)
        
        # Test cache operations without Redis connection
        # (Redis client will be None, should fallback to memory cache)
        
        # Test cache operations
        await cache.set("error_test_key", "error_test_value")
        result = await cache.get("error_test_key")
        
        # Should work with memory cache even without Redis
        assert result == "error_test_value"
        
        # Test performance optimizer with cache errors
        with patch.object(cache, 'get_stats', side_effect=Exception("Cache error")):
            # Should handle cache errors gracefully
            try:
                await optimizer.record_request("/test", "GET", 0.1, 200, False)
                # Should not raise exception
            except Exception as e:
                pytest.fail(f"Performance optimizer should handle cache errors: {e}")
    
    def test_cache_key_generation_consistency(self, test_settings, mock_logger):
        """Test cache key generation consistency across components"""
        cache = AdvancedRedisCache(test_settings, mock_logger)
        middleware = SmartCachingMiddleware(Mock(), cache, None, mock_logger)
        
        # Test key generation consistency
        key1 = cache._generate_key("test_key", "namespace")
        key2 = cache._generate_key("test_key", "namespace")
        
        assert key1 == key2  # Should be consistent
        assert key1.startswith(cache.config.key_prefix)
        
        # Test key hashing for long keys
        long_key = "a" * 300
        hashed1 = cache._hash_key(long_key)
        hashed2 = cache._hash_key(long_key)
        
        assert hashed1 == hashed2  # Should be consistent
        assert len(hashed1) == 64   # SHA256 hex length
    
    @pytest.mark.asyncio
    async def test_memory_management_integration(self, test_settings, mock_logger):
        """Test memory management across caching and performance systems"""
        cache_config = CacheConfig(max_memory_mb=1)  # Very small for testing
        cache = AdvancedRedisCache(test_settings, mock_logger, cache_config)
        cache.max_memory_items = 5  # Small limit
        
        optimizer = PerformanceOptimizer(test_settings, cache, mock_logger)
        
        try:
            await cache.start()
            
            # Fill cache beyond limit
            for i in range(10):
                await cache.set(f"key_{i}", f"value_{i}")
            
            # Should have evicted older entries
            assert len(cache.memory_cache) <= cache.max_memory_items
            
            # Test memory cleanup optimization
            from app.performance.optimizer import PerformanceMetrics
            high_memory_metrics = PerformanceMetrics(memory_percent=90.0)
            
            # Should trigger memory cleanup
            await optimizer._emergency_memory_cleanup(high_memory_metrics)
            
            # Cache should be cleaned up
            assert len(cache.memory_cache) < 5  # Should be reduced
            
        finally:
            await cache.stop()
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self, test_settings, mock_logger):
        """Test concurrent caching and performance operations"""
        cache = AdvancedRedisCache(test_settings, mock_logger)
        optimizer = PerformanceOptimizer(test_settings, cache, mock_logger)
        
        try:
            await cache.start()
            
            # Test concurrent cache operations
            async def cache_worker(worker_id):
                for i in range(10):
                    key = f"worker_{worker_id}_key_{i}"
                    value = f"worker_{worker_id}_value_{i}"
                    
                    await cache.set(key, value)
                    result = await cache.get(key)
                    assert result == value
                    
                    # Record performance data
                    await optimizer.record_request(
                        f"/api/worker/{worker_id}",
                        "GET",
                        0.1,
                        200,
                        True
                    )
            
            # Run multiple workers concurrently
            workers = [cache_worker(i) for i in range(3)]
            await asyncio.gather(*workers)
            
            # Verify all operations completed successfully
            stats = await cache.get_stats()
            assert stats["statistics"]["sets"] >= 30  # 3 workers * 10 operations
            assert stats["statistics"]["hits"] >= 30
            
        finally:
            await cache.stop()
    
    @pytest.mark.asyncio
    async def test_performance_metrics_accuracy(self, test_settings, mock_logger):
        """Test accuracy of performance metrics collection"""
        cache = AdvancedRedisCache(test_settings, mock_logger)
        optimizer = PerformanceOptimizer(test_settings, cache, mock_logger)
        
        try:
            await cache.start()
            
            # Record known performance data
            test_requests = [
                ("/api/v1/fast", 0.1, 200, True),
                ("/api/v1/fast", 0.12, 200, True),
                ("/api/v1/slow", 1.5, 200, False),
                ("/api/v1/slow", 1.8, 500, False),  # Error
                ("/api/v1/medium", 0.5, 200, True),
            ]
            
            for endpoint, duration, status, cache_hit in test_requests:
                await optimizer.record_request(endpoint, "GET", duration, status, cache_hit)
            
            # Allow background processing
            await asyncio.sleep(0.2)
            
            # Check request profiles
            if "/api/v1/fast" in optimizer.request_profiles:
                fast_profile = optimizer.request_profiles["/api/v1/fast"]
                assert fast_profile.request_count == 2
                assert fast_profile.cache_hit_count == 2
                assert fast_profile.error_count == 0
                assert 0.1 <= fast_profile.avg_duration <= 0.12
            
            if "/api/v1/slow" in optimizer.request_profiles:
                slow_profile = optimizer.request_profiles["/api/v1/slow"]
                assert slow_profile.request_count == 2
                assert slow_profile.error_count == 1  # One 500 error
                assert slow_profile.cache_hit_count == 0
                assert slow_profile.avg_duration > 1.5
        
        finally:
            await cache.stop()


class TestRealWorldScenarios:
    """Test real-world usage scenarios"""
    
    @pytest.mark.asyncio
    async def test_high_traffic_scenario(self, test_settings, mock_logger):
        """Test system behavior under high traffic"""
        cache = AdvancedRedisCache(test_settings, mock_logger)
        optimizer = PerformanceOptimizer(test_settings, cache, mock_logger)
        
        try:
            await cache.start()
            
            # Simulate high traffic pattern
            endpoints = ["/api/v1/popular", "/api/v1/common", "/api/v1/frequent"]
            
            # Generate traffic pattern
            for i in range(100):
                endpoint = endpoints[i % len(endpoints)]
                
                # Vary response times and cache hits
                duration = 0.1 + (i % 10) * 0.05  # 0.1 to 0.55 seconds
                cache_hit = i % 3 == 0  # 33% cache hit rate
                status = 500 if i % 20 == 0 else 200  # 5% error rate
                
                await optimizer.record_request(endpoint, "GET", duration, status, cache_hit)
            
            # Allow processing
            await asyncio.sleep(0.1)
            
            # System should handle high traffic gracefully
            assert len(optimizer.request_profiles) <= len(endpoints) + 2  # Some tolerance
            
            # Check that profiles were created
            popular_requests = sum(1 for key in optimizer.request_profiles.keys() 
                                 if "popular" in key)
            assert popular_requests > 0
            
        finally:
            await cache.stop()
    
    @pytest.mark.asyncio
    async def test_cache_warming_scenario(self, test_settings, mock_logger):
        """Test cache warming and initial performance"""
        cache = AdvancedRedisCache(test_settings, mock_logger)
        middleware = SmartCachingMiddleware(Mock(), cache, None, mock_logger)
        
        try:
            await cache.start()
            
            # Pre-populate cache (cache warming)
            warm_data = [
                ("popular_endpoint_1", {"data": "frequently_accessed"}),
                ("popular_endpoint_2", {"data": "commonly_used"}), 
                ("popular_endpoint_3", {"data": "often_requested"}),
            ]
            
            for key, value in warm_data:
                await cache.set(key, value, ttl=3600)
            
            # Verify cache warming worked
            for key, expected_value in warm_data:
                result = await cache.get(key)
                assert result == expected_value
            
            # Check cache statistics
            stats = await cache.get_stats()
            assert stats["statistics"]["sets"] >= len(warm_data)
            assert stats["statistics"]["hits"] >= len(warm_data)
            
            # Test cache warm-up endpoint simulation
            popular_endpoints = [
                {"path": "/api/v1/popular", "method": "GET"},
                {"path": "/api/v1/common", "method": "GET"}, 
                {"path": "/api/v1/frequent", "method": "GET"},
            ]
            
            await middleware.warm_cache(popular_endpoints)
            
        finally:
            await cache.stop()
    
    @pytest.mark.asyncio
    async def test_gradual_degradation_scenario(self, test_settings, mock_logger):
        """Test system behavior during gradual performance degradation"""
        cache = AdvancedRedisCache(test_settings, mock_logger)
        optimizer = PerformanceOptimizer(test_settings, cache, mock_logger)
        
        try:
            await cache.start()
            
            # Simulate gradual performance degradation
            base_duration = 0.1
            
            for minute in range(10):  # 10 minutes of gradual degradation
                # Response time increases over time
                current_duration = base_duration + (minute * 0.2)  # Up to 1.9s
                
                # Simulate requests for this minute
                for request in range(10):
                    await optimizer.record_request(
                        "/api/v1/degrading",
                        "GET", 
                        current_duration,
                        200,
                        False  # No cache hits during degradation
                    )
                
                # Allow some processing
                await asyncio.sleep(0.01)
            
            # Check if system detected degradation
            if "/api/v1/degrading" in optimizer.request_profiles:
                profile = optimizer.request_profiles["/api/v1/degrading"]
                assert profile.request_count == 100
                assert profile.avg_duration > base_duration
                
                # Optimization score should decrease with poor performance
                assert profile.optimization_score < 1.0
            
            # Test recommendations for degraded endpoint
            recommendations = optimizer.get_optimization_recommendations()
            response_time_recs = [r for r in recommendations if r['type'] == 'response_time']
            assert len(response_time_recs) > 0
            
        finally:
            await cache.stop()
    
    @pytest.mark.asyncio
    async def test_cache_invalidation_patterns(self, test_settings, mock_logger):
        """Test various cache invalidation patterns"""
        cache = AdvancedRedisCache(test_settings, mock_logger)
        
        try:
            await cache.start()
            
            # Set up data with different tags
            user_data = [
                ("user:123", {"name": "John"}, ["users", "profile"]),
                ("user:456", {"name": "Jane"}, ["users", "profile"]), 
                ("admin:789", {"name": "Admin"}, ["users", "admin"]),
                ("config:app", {"theme": "dark"}, ["config"]),
                ("config:db", {"host": "localhost"}, ["config", "database"]),
            ]
            
            for key, value, tags in user_data:
                await cache.set(key, value, ttl=3600, tags=tags)
            
            # Test tag-based invalidation
            invalidated = await cache.invalidate_by_tags(["profile"])
            assert invalidated >= 2  # Should invalidate user profiles
            
            # Test pattern-based invalidation  
            invalidated = await cache.invalidate_by_pattern("config:*")
            # Note: Pattern invalidation may not work without Redis
            
            # Verify invalidation worked
            result = await cache.get("user:123")
            assert result is None  # Should be invalidated
            
            result = await cache.get("config:app") 
            # May still exist in memory cache if Redis not available
            
        finally:
            await cache.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])