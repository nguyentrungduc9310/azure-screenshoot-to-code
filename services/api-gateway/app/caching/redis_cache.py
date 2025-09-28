"""
Advanced Redis Caching System
Multi-tier caching with TTL management, compression, and intelligent invalidation
"""
import asyncio
import json
import time
import zlib
import pickle
from typing import Any, Optional, Dict, List, Union, Callable, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum
import hashlib
from datetime import datetime, timedelta

import redis.asyncio as redis
from redis.asyncio import Redis, ConnectionPool
from redis.exceptions import RedisError, ConnectionError, TimeoutError

from app.core.config import Settings
from shared.monitoring.structured_logger import StructuredLogger

T = TypeVar('T')

class CacheStrategy(str, Enum):
    """Cache strategy types"""
    WRITE_THROUGH = "write_through"      # Write to cache and database
    WRITE_BEHIND = "write_behind"        # Write to cache, async to database
    WRITE_AROUND = "write_around"        # Write to database, invalidate cache
    READ_THROUGH = "read_through"        # Read from cache, fallback to database
    CACHE_ASIDE = "cache_aside"          # Manual cache management

class CompressionType(str, Enum):
    """Compression algorithms"""
    NONE = "none"
    ZLIB = "zlib"
    GZIP = "gzip"
    PICKLE = "pickle"

class CacheLevel(str, Enum):
    """Cache levels for multi-tier caching"""
    L1_MEMORY = "l1_memory"      # In-memory cache (fastest, smallest)
    L2_REDIS = "l2_redis"        # Redis cache (fast, medium)
    L3_PERSISTENT = "l3_persistent"  # Persistent cache (slower, largest)

@dataclass
class CacheConfig:
    """Cache configuration"""
    default_ttl: int = 3600  # 1 hour
    max_memory_mb: int = 100
    compression_threshold: int = 1024  # Compress if > 1KB
    compression_type: CompressionType = CompressionType.ZLIB
    enable_metrics: bool = True
    key_prefix: str = "apigw"
    cluster_mode: bool = False
    
@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: Any
    created_at: float
    ttl: int
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    compressed: bool = False
    size_bytes: int = 0
    tags: List[str] = field(default_factory=list)

@dataclass
class CacheStats:
    """Cache statistics"""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    memory_usage: int = 0
    total_operations: int = 0
    
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / max(total, 1)
    
    @property
    def miss_rate(self) -> float:
        return 1.0 - self.hit_rate

class AdvancedRedisCache:
    """Advanced Redis caching system with multi-tier support and optimization"""
    
    def __init__(self, settings: Settings, logger: StructuredLogger, config: Optional[CacheConfig] = None):
        self.settings = settings
        self.logger = logger
        self.config = config or CacheConfig()
        
        # Redis connection
        self.redis_client: Optional[Redis] = None
        self.connection_pool: Optional[ConnectionPool] = None
        
        # L1 memory cache (LRU)
        self.memory_cache: Dict[str, CacheEntry] = {}
        self.memory_cache_order: List[str] = []
        self.max_memory_items = 1000
        
        # Statistics
        self.stats = CacheStats()
        
        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._metrics_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Cache invalidation patterns
        self.invalidation_patterns: Dict[str, List[str]] = {}
        
        self.logger.info("Advanced Redis cache initialized",
                        config=self.config.__dict__)
    
    async def start(self):
        """Start cache system"""
        await self._connect_redis()
        
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        if self.config.enable_metrics:
            self._metrics_task = asyncio.create_task(self._metrics_loop())
        
        self.logger.info("Redis cache started",
                        redis_connected=self.redis_client is not None,
                        memory_cache_enabled=True)
    
    async def stop(self):
        """Stop cache system"""
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        if self._metrics_task:
            self._metrics_task.cancel()
            try:
                await self._metrics_task
            except asyncio.CancelledError:
                pass
        
        if self.redis_client:
            await self.redis_client.close()
        
        self.logger.info("Redis cache stopped")
    
    async def _connect_redis(self):
        """Connect to Redis"""
        try:
            # Create connection pool
            self.connection_pool = ConnectionPool.from_url(
                self.settings.redis_url,
                max_connections=20,
                retry_on_timeout=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                health_check_interval=30
            )
            
            # Create Redis client
            self.redis_client = Redis(
                connection_pool=self.connection_pool,
                decode_responses=False  # Handle binary data
            )
            
            # Test connection
            await self.redis_client.ping()
            
            self.logger.info("Redis connection established",
                           url=self.settings.redis_url)
            
        except Exception as e:
            self.logger.error("Failed to connect to Redis",
                            error=str(e),
                            url=self.settings.redis_url)
            # Continue without Redis (L1 cache only)
            self.redis_client = None
    
    def _generate_key(self, key: str, namespace: Optional[str] = None) -> str:
        """Generate cache key with prefix and namespace"""
        parts = [self.config.key_prefix]
        if namespace:
            parts.append(namespace)
        parts.append(key)
        return ":".join(parts)
    
    def _hash_key(self, key: str) -> str:
        """Hash long keys to prevent Redis key size limits"""
        if len(key) > 250:  # Redis key size limit
            return hashlib.sha256(key.encode()).hexdigest()
        return key
    
    def _serialize_value(self, value: Any) -> bytes:
        """Serialize value with optional compression"""
        # First serialize to JSON
        try:
            json_data = json.dumps(value, default=str).encode('utf-8')
        except (TypeError, ValueError):
            # Fallback to pickle for complex objects
            json_data = pickle.dumps(value)
        
        # Compress if larger than threshold
        if len(json_data) > self.config.compression_threshold:
            if self.config.compression_type == CompressionType.ZLIB:
                return b'zlib:' + zlib.compress(json_data)
            elif self.config.compression_type == CompressionType.GZIP:
                import gzip
                return b'gzip:' + gzip.compress(json_data)
        
        return b'raw:' + json_data
    
    def _deserialize_value(self, data: bytes) -> Any:
        """Deserialize value with decompression"""
        if data.startswith(b'zlib:'):
            decompressed = zlib.decompress(data[5:])
        elif data.startswith(b'gzip:'):
            import gzip
            decompressed = gzip.decompress(data[5:])
        elif data.startswith(b'raw:'):
            decompressed = data[4:]
        else:
            decompressed = data
        
        # Try JSON first, fallback to pickle
        try:
            return json.loads(decompressed.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return pickle.loads(decompressed)
    
    async def get(
        self,
        key: str,
        namespace: Optional[str] = None,
        default: Any = None
    ) -> Any:
        """Get value from cache with L1 -> L2 fallback"""
        cache_key = self._generate_key(key, namespace)
        hashed_key = self._hash_key(cache_key)
        
        start_time = time.time()
        
        try:
            # Try L1 memory cache first
            if hashed_key in self.memory_cache:
                entry = self.memory_cache[hashed_key]
                
                # Check if expired
                if time.time() - entry.created_at > entry.ttl:
                    await self._evict_from_memory(hashed_key)
                else:
                    # Update access info
                    entry.access_count += 1
                    entry.last_accessed = time.time()
                    self._update_memory_order(hashed_key)
                    
                    self.stats.hits += 1
                    self.stats.total_operations += 1
                    
                    self.logger.debug("Cache hit (L1 memory)",
                                    key=key,
                                    namespace=namespace,
                                    access_count=entry.access_count,
                                    age_seconds=time.time() - entry.created_at)
                    
                    return entry.value
            
            # Try L2 Redis cache
            if self.redis_client:
                try:
                    data = await self.redis_client.get(hashed_key)
                    if data:
                        value = self._deserialize_value(data)
                        
                        # Store in L1 cache for future access
                        await self._store_in_memory(hashed_key, value, self.config.default_ttl)
                        
                        self.stats.hits += 1
                        self.stats.total_operations += 1
                        
                        duration_ms = (time.time() - start_time) * 1000
                        self.logger.debug("Cache hit (L2 Redis)",
                                        key=key,
                                        namespace=namespace,
                                        duration_ms=duration_ms)
                        
                        return value
                        
                except RedisError as e:
                    self.logger.warning("Redis get error",
                                      key=key,
                                      error=str(e))
            
            # Cache miss
            self.stats.misses += 1
            self.stats.total_operations += 1
            
            duration_ms = (time.time() - start_time) * 1000
            self.logger.debug("Cache miss",
                            key=key,
                            namespace=namespace,
                            duration_ms=duration_ms)
            
            return default
            
        except Exception as e:
            self.logger.error("Cache get error",
                            key=key,
                            namespace=namespace,
                            error=str(e))
            return default
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        namespace: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> bool:
        """Set value in cache with L1 and L2 storage"""
        cache_key = self._generate_key(key, namespace)
        hashed_key = self._hash_key(cache_key)
        ttl = ttl or self.config.default_ttl
        tags = tags or []
        
        start_time = time.time()
        success = True
        
        try:
            # Store in L1 memory cache
            await self._store_in_memory(hashed_key, value, ttl, tags)
            
            # Store in L2 Redis cache
            if self.redis_client:
                try:
                    serialized = self._serialize_value(value)
                    await self.redis_client.setex(hashed_key, ttl, serialized)
                    
                    # Store tags for invalidation
                    if tags:
                        for tag in tags:
                            tag_key = f"{self.config.key_prefix}:tags:{tag}"
                            await self.redis_client.sadd(tag_key, hashed_key)
                            await self.redis_client.expire(tag_key, ttl)
                    
                except RedisError as e:
                    self.logger.warning("Redis set error",
                                      key=key,
                                      error=str(e))
                    success = False
            
            self.stats.sets += 1
            self.stats.total_operations += 1
            
            duration_ms = (time.time() - start_time) * 1000
            self.logger.debug("Cache set",
                            key=key,
                            namespace=namespace,
                            ttl=ttl,
                            tags=tags,
                            duration_ms=duration_ms,
                            l2_success=self.redis_client is not None and success)
            
            return success
            
        except Exception as e:
            self.logger.error("Cache set error",
                            key=key,
                            namespace=namespace,
                            error=str(e))
            return False
    
    async def delete(
        self,
        key: str,
        namespace: Optional[str] = None
    ) -> bool:
        """Delete value from cache"""
        cache_key = self._generate_key(key, namespace)
        hashed_key = self._hash_key(cache_key)
        
        success = True
        
        try:
            # Delete from L1 memory cache
            await self._evict_from_memory(hashed_key)
            
            # Delete from L2 Redis cache
            if self.redis_client:
                try:
                    result = await self.redis_client.delete(hashed_key)
                    success = result > 0
                except RedisError as e:
                    self.logger.warning("Redis delete error",
                                      key=key,
                                      error=str(e))
                    success = False
            
            self.stats.deletes += 1
            self.stats.total_operations += 1
            
            self.logger.debug("Cache delete",
                            key=key,
                            namespace=namespace,
                            success=success)
            
            return success
            
        except Exception as e:
            self.logger.error("Cache delete error",
                            key=key,
                            namespace=namespace,
                            error=str(e))
            return False
    
    async def invalidate_by_tags(self, tags: List[str]) -> int:
        """Invalidate cache entries by tags"""
        if not self.redis_client:
            return 0
        
        invalidated = 0
        
        try:
            for tag in tags:
                tag_key = f"{self.config.key_prefix}:tags:{tag}"
                
                # Get all keys with this tag
                keys = await self.redis_client.smembers(tag_key)
                if keys:
                    # Delete the keys
                    await self.redis_client.delete(*keys)
                    invalidated += len(keys)
                    
                    # Delete from memory cache too
                    for key in keys:
                        if isinstance(key, bytes):
                            key = key.decode('utf-8')
                        await self._evict_from_memory(key)
                
                # Delete the tag set
                await self.redis_client.delete(tag_key)
            
            self.logger.info("Cache invalidated by tags",
                           tags=tags,
                           invalidated_count=invalidated)
            
            return invalidated
            
        except Exception as e:
            self.logger.error("Cache tag invalidation error",
                            tags=tags,
                            error=str(e))
            return 0
    
    async def invalidate_by_pattern(self, pattern: str) -> int:
        """Invalidate cache entries by key pattern"""
        if not self.redis_client:
            return 0
        
        try:
            # Scan for keys matching pattern
            keys = []
            async for key in self.redis_client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                await self.redis_client.delete(*keys)
                
                # Delete from memory cache too
                for key in keys:
                    if isinstance(key, bytes):
                        key = key.decode('utf-8')
                    await self._evict_from_memory(key)
            
            self.logger.info("Cache invalidated by pattern",
                           pattern=pattern,
                           invalidated_count=len(keys))
            
            return len(keys)
            
        except Exception as e:
            self.logger.error("Cache pattern invalidation error",
                            pattern=pattern,
                            error=str(e))
            return 0
    
    async def _store_in_memory(
        self,
        key: str,
        value: Any,
        ttl: int,
        tags: Optional[List[str]] = None
    ):
        """Store value in L1 memory cache with LRU eviction"""
        # Evict expired and excess entries
        await self._evict_expired_memory()
        await self._evict_lru_memory()
        
        # Create cache entry
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=time.time(),
            ttl=ttl,
            tags=tags or [],
            size_bytes=len(str(value))  # Approximate size
        )
        
        self.memory_cache[key] = entry
        self._update_memory_order(key)
        
        # Update memory usage
        self.stats.memory_usage += entry.size_bytes
    
    def _update_memory_order(self, key: str):
        """Update LRU order for memory cache"""
        if key in self.memory_cache_order:
            self.memory_cache_order.remove(key)
        self.memory_cache_order.append(key)
    
    async def _evict_from_memory(self, key: str):
        """Evict entry from memory cache"""
        if key in self.memory_cache:
            entry = self.memory_cache[key]
            del self.memory_cache[key]
            
            if key in self.memory_cache_order:
                self.memory_cache_order.remove(key)
            
            self.stats.memory_usage -= entry.size_bytes
            self.stats.evictions += 1
    
    async def _evict_expired_memory(self):
        """Evict expired entries from memory cache"""
        current_time = time.time()
        expired_keys = []
        
        for key, entry in self.memory_cache.items():
            if current_time - entry.created_at > entry.ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            await self._evict_from_memory(key)
    
    async def _evict_lru_memory(self):
        """Evict LRU entries if cache is full"""
        while len(self.memory_cache) >= self.max_memory_items:
            if self.memory_cache_order:
                oldest_key = self.memory_cache_order[0]
                await self._evict_from_memory(oldest_key)
            else:
                break
    
    async def _cleanup_loop(self):
        """Background cleanup task"""
        while self._running:
            try:
                await self._evict_expired_memory()
                await asyncio.sleep(60)  # Run every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Cache cleanup error", error=str(e))
                await asyncio.sleep(5)
    
    async def _metrics_loop(self):
        """Background metrics collection task"""
        while self._running:
            try:
                # Log cache statistics
                self.logger.info("Cache metrics",
                               hit_rate=self.stats.hit_rate,
                               miss_rate=self.stats.miss_rate,
                               total_operations=self.stats.total_operations,
                               memory_entries=len(self.memory_cache),
                               memory_usage_bytes=self.stats.memory_usage,
                               redis_connected=self.redis_client is not None)
                
                await asyncio.sleep(300)  # Every 5 minutes
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Cache metrics error", error=str(e))
                await asyncio.sleep(60)
    
    # Cache decorators and helpers
    def cached(
        self,
        ttl: Optional[int] = None,
        namespace: Optional[str] = None,
        key_func: Optional[Callable] = None,
        tags: Optional[List[str]] = None
    ):
        """Decorator for caching function results"""
        def decorator(func: Callable):
            async def async_wrapper(*args, **kwargs):
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    # Default key generation
                    key_parts = [func.__name__]
                    key_parts.extend(str(arg) for arg in args)
                    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                    cache_key = ":".join(key_parts)
                
                # Try to get from cache
                result = await self.get(cache_key, namespace)
                if result is not None:
                    return result
                
                # Execute function and cache result
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                await self.set(cache_key, result, ttl, namespace, tags)
                return result
            
            def sync_wrapper(*args, **kwargs):
                # For sync functions, we need to handle async cache operations
                return asyncio.create_task(async_wrapper(*args, **kwargs))
            
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper
        
        return decorator
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        redis_info = {}
        if self.redis_client:
            try:
                redis_info = await self.redis_client.info('memory')
            except Exception as e:
                self.logger.warning("Failed to get Redis info", error=str(e))
        
        return {
            "l1_memory_cache": {
                "entries": len(self.memory_cache),
                "memory_usage_bytes": self.stats.memory_usage,
                "max_items": self.max_memory_items
            },
            "l2_redis_cache": {
                "connected": self.redis_client is not None,
                "info": redis_info
            },
            "statistics": {
                "hits": self.stats.hits,
                "misses": self.stats.misses,
                "hit_rate": self.stats.hit_rate,
                "miss_rate": self.stats.miss_rate,
                "sets": self.stats.sets,
                "deletes": self.stats.deletes,
                "evictions": self.stats.evictions,
                "total_operations": self.stats.total_operations
            },
            "configuration": {
                "default_ttl": self.config.default_ttl,
                "compression_threshold": self.config.compression_threshold,
                "compression_type": self.config.compression_type.value,
                "key_prefix": self.config.key_prefix
            }
        }
    
    async def flush_all(self) -> bool:
        """Flush all cache data"""
        try:
            # Clear memory cache
            self.memory_cache.clear()
            self.memory_cache_order.clear()
            self.stats.memory_usage = 0
            
            # Clear Redis cache
            if self.redis_client:
                # Only flush keys with our prefix
                pattern = f"{self.config.key_prefix}:*"
                keys = []
                async for key in self.redis_client.scan_iter(match=pattern):
                    keys.append(key)
                
                if keys:
                    await self.redis_client.delete(*keys)
            
            self.logger.info("Cache flushed", 
                           memory_cleared=True,
                           redis_cleared=self.redis_client is not None)
            
            return True
            
        except Exception as e:
            self.logger.error("Cache flush error", error=str(e))
            return False