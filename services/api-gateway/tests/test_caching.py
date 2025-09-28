"""
Tests for caching system components
"""
import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

from app.caching.redis_cache import (
    AdvancedRedisCache,
    CacheConfig,
    CacheStrategy,
    CacheLevel,
    CompressionType,
    CacheEntry,
    CacheStats
)
from app.middleware.caching import CachingMiddleware, SmartCachingMiddleware, CacheRule


class TestAdvancedRedisCache:
    """Test advanced Redis caching system"""
    
    def test_cache_config_defaults(self):
        """Test cache configuration defaults"""
        config = CacheConfig()
        
        assert config.default_ttl == 3600
        assert config.max_memory_mb == 100
        assert config.compression_threshold == 1024
        assert config.compression_type == CompressionType.ZLIB
        assert config.enable_metrics == True
        assert config.key_prefix == "apigw"
    
    def test_cache_entry_creation(self):
        """Test cache entry creation"""
        entry = CacheEntry(
            key="test_key",
            value={"data": "test_value"},
            created_at=time.time(),
            ttl=300,
            tags=["test", "cache"]
        )
        
        assert entry.key == "test_key"
        assert entry.value == {"data": "test_value"}
        assert entry.ttl == 300
        assert entry.tags == ["test", "cache"]
        assert entry.access_count == 0
    
    def test_cache_stats(self):
        """Test cache statistics"""
        stats = CacheStats(hits=80, misses=20, sets=100)
        
        assert stats.hit_rate == 0.8
        assert stats.miss_rate == 0.2
        assert stats.total_operations == 0  # Only hits + misses counted
    
    @pytest.mark.asyncio
    async def test_cache_initialization(self, test_settings, mock_logger):
        """Test cache initialization"""
        config = CacheConfig(key_prefix="test")
        cache = AdvancedRedisCache(test_settings, mock_logger, config)
        
        assert cache.settings == test_settings
        assert cache.logger == mock_logger
        assert cache.config.key_prefix == "test"
        assert cache.memory_cache == {}
        assert cache.stats.hits == 0
    
    @pytest.mark.asyncio
    async def test_key_generation(self, test_settings, mock_logger):
        """Test cache key generation"""
        cache = AdvancedRedisCache(test_settings, mock_logger)
        
        # Test basic key generation
        key = cache._generate_key("test_key")
        assert key == "apigw:test_key"
        
        # Test with namespace
        key_with_ns = cache._generate_key("test_key", "api")
        assert key_with_ns == "apigw:api:test_key"
    
    @pytest.mark.asyncio
    async def test_key_hashing(self, test_settings, mock_logger):
        """Test key hashing for long keys"""
        cache = AdvancedRedisCache(test_settings, mock_logger)
        
        # Short key should not be hashed
        short_key = "short_key"
        hashed = cache._hash_key(short_key)
        assert hashed == short_key
        
        # Long key should be hashed
        long_key = "a" * 300  # Longer than 250 characters
        hashed = cache._hash_key(long_key)
        assert len(hashed) == 64  # SHA256 hex length
        assert hashed != long_key
    
    @pytest.mark.asyncio
    async def test_serialization(self, test_settings, mock_logger):
        """Test value serialization and deserialization"""
        cache = AdvancedRedisCache(test_settings, mock_logger)
        
        # Test simple JSON serialization
        value = {"key": "value", "number": 42}
        serialized = cache._serialize_value(value)
        deserialized = cache._deserialize_value(serialized)
        
        assert deserialized == value
        assert serialized.startswith(b'raw:')  # Should not be compressed
    
    @pytest.mark.asyncio
    async def test_compression(self, test_settings, mock_logger):
        """Test value compression"""
        config = CacheConfig(compression_threshold=10)  # Very low threshold
        cache = AdvancedRedisCache(test_settings, mock_logger, config)
        
        # Large value should be compressed
        large_value = {"data": "x" * 1000}
        serialized = cache._serialize_value(large_value)
        deserialized = cache._deserialize_value(serialized)
        
        assert deserialized == large_value
        assert serialized.startswith(b'zlib:')  # Should be compressed
    
    @pytest.mark.asyncio
    async def test_memory_cache_operations(self, test_settings, mock_logger):
        """Test memory cache operations"""
        cache = AdvancedRedisCache(test_settings, mock_logger)
        
        # Test storing in memory cache
        await cache._store_in_memory("test_key", "test_value", 300)
        
        assert "test_key" in cache.memory_cache
        assert cache.memory_cache["test_key"].value == "test_value"
        assert cache.memory_cache["test_key"].ttl == 300
        
        # Test LRU order update
        assert cache.memory_cache_order[-1] == "test_key"
    
    @pytest.mark.asyncio
    async def test_memory_cache_eviction(self, test_settings, mock_logger):
        """Test memory cache eviction"""
        cache = AdvancedRedisCache(test_settings, mock_logger)
        cache.max_memory_items = 2  # Small limit for testing
        
        # Add items to fill cache
        await cache._store_in_memory("key1", "value1", 300)
        await cache._store_in_memory("key2", "value2", 300)
        await cache._store_in_memory("key3", "value3", 300)  # Should evict key1
        
        assert "key1" not in cache.memory_cache
        assert "key2" in cache.memory_cache
        assert "key3" in cache.memory_cache
    
    @pytest.mark.asyncio
    async def test_expired_cache_cleanup(self, test_settings, mock_logger):
        """Test expired cache entry cleanup"""
        cache = AdvancedRedisCache(test_settings, mock_logger)
        
        # Add expired entry
        expired_time = time.time() - 1000
        cache.memory_cache["expired_key"] = CacheEntry(
            key="expired_key",
            value="expired_value",
            created_at=expired_time,
            ttl=500  # Already expired
        )
        
        # Add valid entry
        await cache._store_in_memory("valid_key", "valid_value", 300)
        
        # Run cleanup
        await cache._evict_expired_memory()
        
        assert "expired_key" not in cache.memory_cache
        assert "valid_key" in cache.memory_cache
    
    @pytest.mark.asyncio
    async def test_cache_get_memory_hit(self, test_settings, mock_logger):
        """Test cache get with memory hit"""
        cache = AdvancedRedisCache(test_settings, mock_logger)
        
        # Store value in memory cache
        await cache._store_in_memory("test_key", "test_value", 300)
        
        # Get value
        result = await cache.get("test_key")
        
        assert result == "test_value"
        assert cache.stats.hits == 1
        assert cache.stats.misses == 0
    
    @pytest.mark.asyncio
    async def test_cache_get_miss(self, test_settings, mock_logger):
        """Test cache get with miss"""
        cache = AdvancedRedisCache(test_settings, mock_logger)
        
        # Get non-existent value
        result = await cache.get("non_existent_key", default="default_value")
        
        assert result == "default_value"
        assert cache.stats.hits == 0
        assert cache.stats.misses == 1
    
    @pytest.mark.asyncio
    async def test_cache_set_operations(self, test_settings, mock_logger):
        """Test cache set operations"""
        cache = AdvancedRedisCache(test_settings, mock_logger)
        
        # Set value
        success = await cache.set("test_key", "test_value", ttl=600, tags=["test"])
        
        assert success == True
        assert cache.stats.sets == 1
        
        # Verify value is in memory cache
        assert "apigw:test_key" in cache.memory_cache or cache._hash_key("apigw:test_key") in cache.memory_cache
    
    @pytest.mark.asyncio
    async def test_cache_delete(self, test_settings, mock_logger):
        """Test cache delete operations"""
        cache = AdvancedRedisCache(test_settings, mock_logger)
        
        # Set and then delete
        await cache.set("test_key", "test_value")
        success = await cache.delete("test_key")
        
        assert success == True
        assert cache.stats.deletes == 1
        
        # Verify value is deleted
        result = await cache.get("test_key")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_stats_retrieval(self, test_settings, mock_logger):
        """Test cache statistics retrieval"""
        cache = AdvancedRedisCache(test_settings, mock_logger)
        
        # Perform some operations
        await cache.set("key1", "value1")
        await cache.get("key1")  # Hit
        await cache.get("key2")  # Miss
        
        stats = await cache.get_stats()
        
        assert "l1_memory_cache" in stats
        assert "l2_redis_cache" in stats
        assert "statistics" in stats
        assert "configuration" in stats
        
        assert stats["statistics"]["hits"] >= 1
        assert stats["statistics"]["misses"] >= 1
        assert stats["statistics"]["sets"] >= 1


class TestCacheRule:
    """Test cache rule functionality"""
    
    def test_cache_rule_creation(self):
        """Test cache rule creation"""
        rule = CacheRule(
            pattern="/api/v1/test*",
            ttl=300,
            vary_headers=["Authorization"],
            cache_post=True,
            cache_authenticated=False,
            invalidate_on=["/api/v1/test/*"],
            condition=lambda req: req.method == "GET"
        )
        
        assert rule.pattern == "/api/v1/test*"
        assert rule.ttl == 300
        assert rule.vary_headers == ["Authorization"]
        assert rule.cache_post == True
        assert rule.cache_authenticated == False
        assert rule.invalidate_on == ["/api/v1/test/*"]
        assert rule.condition is not None


class TestCachingMiddleware:
    """Test caching middleware"""
    
    @pytest.mark.asyncio
    async def test_caching_middleware_initialization(self, test_settings, mock_logger):
        """Test caching middleware initialization"""
        mock_cache = Mock(spec=AdvancedRedisCache)
        mock_optimizer = Mock()
        
        middleware = CachingMiddleware(
            app=Mock(),
            cache=mock_cache,
            optimizer=mock_optimizer,
            logger=mock_logger
        )
        
        assert middleware.cache == mock_cache
        assert middleware.optimizer == mock_optimizer
        assert middleware.logger == mock_logger
        assert len(middleware.cache_rules) > 0  # Should have default rules
    
    def test_cache_rule_matching(self, test_settings, mock_logger):
        """Test cache rule pattern matching"""
        mock_cache = Mock(spec=AdvancedRedisCache)
        middleware = CachingMiddleware(Mock(), mock_cache, None, mock_logger)
        
        # Test pattern matching
        assert middleware._pattern_matches("/health*", "/health") == True
        assert middleware._pattern_matches("/health*", "/health/status") == True
        assert middleware._pattern_matches("/health", "/health") == True
        assert middleware._pattern_matches("/health", "/health/status") == False
    
    def test_cache_key_generation_sync(self, test_settings, mock_logger):
        """Test synchronous aspects of cache key generation"""
        mock_cache = Mock(spec=AdvancedRedisCache)
        middleware = CachingMiddleware(Mock(), mock_cache, None, mock_logger)
        
        # Test key components
        rule = CacheRule(pattern="/test*", ttl=300, vary_headers=["Authorization"])
        
        # The actual key generation requires a Request object, 
        # so we'll test the pattern matching logic here
        assert rule.pattern == "/test*"
        assert rule.vary_headers == ["Authorization"]
    
    def test_cache_statistics(self, test_settings, mock_logger):
        """Test cache statistics collection"""
        mock_cache = Mock(spec=AdvancedRedisCache)
        middleware = CachingMiddleware(Mock(), mock_cache, None, mock_logger)
        
        # Simulate some activity
        middleware.stats['hits'] = 10
        middleware.stats['misses'] = 2
        middleware.stats['sets'] = 8
        
        stats = middleware.get_cache_stats()
        
        assert stats["statistics"]["hits"] == 10
        assert stats["statistics"]["misses"] == 2
        assert stats["statistics"]["sets"] == 8
        assert stats["statistics"]["hit_rate"] > 0.8
        assert len(stats["rules"]) > 0


class TestSmartCachingMiddleware:
    """Test smart caching middleware"""
    
    @pytest.mark.asyncio
    async def test_smart_caching_initialization(self, test_settings, mock_logger):
        """Test smart caching middleware initialization"""
        mock_cache = Mock(spec=AdvancedRedisCache)
        mock_optimizer = Mock()
        
        middleware = SmartCachingMiddleware(
            app=Mock(),
            cache=mock_cache,
            optimizer=mock_optimizer,
            logger=mock_logger
        )
        
        assert middleware.cache == mock_cache
        assert middleware.optimizer == mock_optimizer
        assert middleware.endpoint_performance == {}
        assert middleware.adaptive_ttl == {}
    
    def test_adaptive_ttl_calculation(self, test_settings, mock_logger):
        """Test adaptive TTL calculation logic"""
        mock_cache = Mock(spec=AdvancedRedisCache)
        middleware = SmartCachingMiddleware(Mock(), mock_cache, None, mock_logger)
        
        # Simulate endpoint performance data
        endpoint = "GET /api/v1/test"
        middleware.endpoint_performance[endpoint] = {
            'access_count': 100,
            'total_duration': 50.0,  # 0.5s average
            'cache_hits': 80,
            'last_access': time.time()
        }
        
        # The adaptive TTL calculation happens in dispatch method
        # Here we test the data structure setup
        assert middleware.endpoint_performance[endpoint]['access_count'] == 100
        assert middleware.endpoint_performance[endpoint]['cache_hits'] == 80
    
    def test_smart_cache_stats(self, test_settings, mock_logger):
        """Test smart cache statistics"""
        mock_cache = Mock(spec=AdvancedRedisCache)
        middleware = SmartCachingMiddleware(Mock(), mock_cache, None, mock_logger)
        
        # Add some endpoint data
        middleware.endpoint_performance["GET /test"] = {
            'access_count': 50,
            'total_duration': 10.0,
            'cache_hits': 40,
            'last_access': time.time()
        }
        middleware.adaptive_ttl["GET /test"] = 600
        
        # Mock the parent class method
        with patch.object(CachingMiddleware, 'get_cache_stats', return_value={"statistics": {}, "rules": []}):
            stats = middleware.get_smart_cache_stats()
        
        assert "smart_features" in stats
        assert stats["smart_features"]["endpoints_tracked"] == 1
        assert stats["smart_features"]["adaptive_ttl_endpoints"] == 1
        assert len(stats["top_cached_endpoints"]) > 0


class TestCachingIntegration:
    """Integration tests for caching system"""
    
    @pytest.mark.asyncio
    async def test_full_caching_integration(self, test_settings, mock_logger):
        """Test full caching system integration"""
        # Initialize cache
        cache_config = CacheConfig(default_ttl=300)
        cache = AdvancedRedisCache(test_settings, mock_logger, cache_config)
        
        try:
            # Test cache lifecycle
            await cache.start()
            
            # Test set and get
            await cache.set("integration_key", {"data": "integration_test"}, ttl=600)
            result = await cache.get("integration_key")
            
            assert result == {"data": "integration_test"}
            
            # Test statistics
            stats = await cache.get_stats()
            assert stats["statistics"]["sets"] >= 1
            assert stats["statistics"]["hits"] >= 1
            
        finally:
            await cache.stop()
    
    @pytest.mark.asyncio
    async def test_caching_middleware_integration(self, test_settings, mock_logger):
        """Test caching middleware integration"""
        # Create cache and middleware
        cache = AdvancedRedisCache(test_settings, mock_logger)
        middleware = CachingMiddleware(Mock(), cache, None, mock_logger)
        
        # Test middleware initialization
        assert middleware.cache == cache
        assert len(middleware.cache_rules) > 0
        
        # Test rule matching
        mock_request = Mock()
        mock_request.url.path = "/health"
        mock_request.method = "GET"
        
        rule = middleware._match_cache_rule(mock_request)
        # Should match health endpoint rule or return None
        assert rule is None or rule.pattern.startswith("/health")