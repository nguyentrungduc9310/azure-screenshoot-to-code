"""
Advanced Caching Optimization
Multi-layer caching strategy with intelligent invalidation and performance optimization
"""
import asyncio
import time
import json
import hashlib
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import redis.asyncio as redis
from functools import wraps

try:
    from shared.monitoring.structured_logger import StructuredLogger
    from shared.monitoring.correlation import get_correlation_id
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger
    
    def get_correlation_id():
        import uuid
        return str(uuid.uuid4())[:8]


class CacheLevel(Enum):
    """Cache level definitions"""
    L1_MEMORY = "l1_memory"       # In-memory cache (fastest)
    L2_REDIS = "l2_redis"         # Redis cache (fast, distributed)
    L3_DATABASE = "l3_database"   # Database cache (persistent)


class CacheStrategy(Enum):
    """Cache strategy types"""
    WRITE_THROUGH = "write_through"     # Write to cache and storage simultaneously
    WRITE_BEHIND = "write_behind"       # Write to cache first, storage later
    READ_THROUGH = "read_through"       # Load data through cache
    CACHE_ASIDE = "cache_aside"         # Manual cache management


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: Any
    created_at: datetime
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    size_bytes: int = 0
    cache_level: CacheLevel = CacheLevel.L1_MEMORY
    tags: List[str] = field(default_factory=list)
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def calculate_size(self) -> int:
        """Calculate approximate size of cache entry"""
        try:
            if isinstance(self.value, (str, bytes)):
                self.size_bytes = len(self.value)
            else:
                # Approximate size for complex objects
                self.size_bytes = len(json.dumps(self.value, default=str).encode('utf-8'))
        except Exception:
            self.size_bytes = 1024  # Default estimate
        return self.size_bytes


@dataclass
class CacheMetrics:
    """Cache performance metrics"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    memory_usage_bytes: int = 0
    entries_count: int = 0
    avg_access_time_ms: float = 0.0
    hit_rate: float = 0.0
    
    def calculate_hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total_requests = self.hits + self.misses
        if total_requests == 0:
            return 0.0
        self.hit_rate = (self.hits / total_requests) * 100
        return self.hit_rate


class AdvancedCacheManager:
    """Advanced multi-level cache manager with intelligent optimization"""
    
    def __init__(self, 
                 redis_client: Optional[redis.Redis] = None,
                 logger: Optional[StructuredLogger] = None,
                 max_memory_size: int = 100 * 1024 * 1024,  # 100MB
                 default_ttl: int = 3600):  # 1 hour
        
        self.redis_client = redis_client
        self.logger = logger or StructuredLogger()
        self.max_memory_size = max_memory_size
        self.default_ttl = default_ttl
        
        # L1 Memory Cache
        self._memory_cache: Dict[str, CacheEntry] = {}
        self._access_times: Dict[str, List[float]] = {}
        self._cache_lock = asyncio.Lock()
        
        # Cache metrics
        self.metrics = {
            CacheLevel.L1_MEMORY: CacheMetrics(),
            CacheLevel.L2_REDIS: CacheMetrics(),
            CacheLevel.L3_DATABASE: CacheMetrics()
        }
        
        # Cache optimization settings
        self.optimization_enabled = True
        self.auto_eviction_enabled = True
        self.performance_monitoring = True
    
    async def get(self, 
                  key: str, 
                  default: Any = None,
                  cache_levels: List[CacheLevel] = None) -> Any:
        """Get value from cache with multi-level fallback"""
        
        if cache_levels is None:
            cache_levels = [CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS]
        
        start_time = time.perf_counter()
        correlation_id = get_correlation_id()
        
        try:
            # Try each cache level in order
            for cache_level in cache_levels:
                value = await self._get_from_level(key, cache_level)
                if value is not None:
                    # Update access metrics
                    access_time = (time.perf_counter() - start_time) * 1000
                    await self._update_access_metrics(key, cache_level, access_time)
                    
                    # Promote to higher cache levels if beneficial
                    if self.optimization_enabled:
                        await self._promote_entry(key, value, cache_level, cache_levels)
                    
                    self.logger.info(
                        "Cache hit",
                        cache_key=key,
                        cache_level=cache_level.value,
                        access_time_ms=access_time,
                        correlation_id=correlation_id
                    )
                    
                    return value
            
            # Cache miss
            miss_time = (time.perf_counter() - start_time) * 1000
            for cache_level in cache_levels:
                self.metrics[cache_level].misses += 1
            
            self.logger.info(
                "Cache miss",
                cache_key=key,
                attempted_levels=[level.value for level in cache_levels],
                miss_time_ms=miss_time,
                correlation_id=correlation_id
            )
            
            return default
            
        except Exception as e:
            self.logger.error(
                "Cache get error",
                cache_key=key,
                error=str(e),
                correlation_id=correlation_id
            )
            return default
    
    async def set(self, 
                  key: str, 
                  value: Any,
                  ttl: Optional[int] = None,
                  cache_levels: List[CacheLevel] = None,
                  tags: List[str] = None) -> bool:
        """Set value in cache with multi-level storage"""
        
        if cache_levels is None:
            cache_levels = [CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS]
        
        if ttl is None:
            ttl = self.default_ttl
        
        start_time = time.perf_counter()
        correlation_id = get_correlation_id()
        
        try:
            success = True
            expires_at = datetime.utcnow() + timedelta(seconds=ttl) if ttl > 0 else None
            
            # Set in each cache level
            for cache_level in cache_levels:
                level_success = await self._set_in_level(
                    key, value, cache_level, expires_at, tags or []
                )
                if not level_success:
                    success = False
                    self.logger.warning(
                        "Failed to set in cache level",
                        cache_key=key,
                        cache_level=cache_level.value,
                        correlation_id=correlation_id
                    )
            
            # Update metrics
            set_time = (time.perf_counter() - start_time) * 1000
            self.logger.info(
                "Cache set",
                cache_key=key,
                cache_levels=[level.value for level in cache_levels],
                ttl_seconds=ttl,
                set_time_ms=set_time,
                success=success,
                correlation_id=correlation_id
            )
            
            # Trigger optimization if needed
            if self.optimization_enabled and cache_level == CacheLevel.L1_MEMORY:
                await self._check_memory_optimization()
            
            return success
            
        except Exception as e:
            self.logger.error(
                "Cache set error",
                cache_key=key,
                error=str(e),
                correlation_id=correlation_id
            )
            return False
    
    async def _get_from_level(self, key: str, cache_level: CacheLevel) -> Optional[Any]:
        """Get value from specific cache level"""
        
        if cache_level == CacheLevel.L1_MEMORY:
            return await self._get_from_memory(key)
        elif cache_level == CacheLevel.L2_REDIS:
            return await self._get_from_redis(key)
        elif cache_level == CacheLevel.L3_DATABASE:
            # Database caching would be implemented here
            return None
        
        return None
    
    async def _set_in_level(self, 
                           key: str, 
                           value: Any, 
                           cache_level: CacheLevel,
                           expires_at: Optional[datetime],
                           tags: List[str]) -> bool:
        """Set value in specific cache level"""
        
        if cache_level == CacheLevel.L1_MEMORY:
            return await self._set_in_memory(key, value, expires_at, tags)
        elif cache_level == CacheLevel.L2_REDIS:
            return await self._set_in_redis(key, value, expires_at, tags)
        elif cache_level == CacheLevel.L3_DATABASE:
            # Database caching would be implemented here
            return True
        
        return False
    
    async def _get_from_memory(self, key: str) -> Optional[Any]:
        """Get value from L1 memory cache"""
        
        async with self._cache_lock:
            if key not in self._memory_cache:
                return None
            
            entry = self._memory_cache[key]
            
            # Check expiration
            if entry.is_expired():
                del self._memory_cache[key]
                self.metrics[CacheLevel.L1_MEMORY].evictions += 1
                return None
            
            # Update access information
            entry.access_count += 1
            entry.last_accessed = datetime.utcnow()
            
            # Track access time
            if key not in self._access_times:
                self._access_times[key] = []
            self._access_times[key].append(time.perf_counter())
            
            # Keep only recent access times (last 100)
            if len(self._access_times[key]) > 100:
                self._access_times[key] = self._access_times[key][-100:]
            
            self.metrics[CacheLevel.L1_MEMORY].hits += 1
            return entry.value
    
    async def _set_in_memory(self, 
                            key: str, 
                            value: Any, 
                            expires_at: Optional[datetime],
                            tags: List[str]) -> bool:
        """Set value in L1 memory cache"""
        
        async with self._cache_lock:
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=datetime.utcnow(),
                expires_at=expires_at,
                cache_level=CacheLevel.L1_MEMORY,
                tags=tags
            )
            entry.calculate_size()
            
            # Check memory limits before adding
            if await self._check_memory_limit(entry.size_bytes):
                self._memory_cache[key] = entry
                await self._update_memory_metrics()
                return True
            else:
                # Try to evict some entries
                if await self._evict_memory_entries(entry.size_bytes):
                    self._memory_cache[key] = entry
                    await self._update_memory_metrics()
                    return True
                else:
                    self.logger.warning(
                        "Memory cache full, cannot add entry",
                        cache_key=key,
                        entry_size=entry.size_bytes,
                        current_memory=await self._calculate_memory_usage()
                    )
                    return False
    
    async def _get_from_redis(self, key: str) -> Optional[Any]:
        """Get value from L2 Redis cache"""
        
        if not self.redis_client:
            return None
        
        try:
            start_time = time.perf_counter()
            
            # Get value and metadata
            pipe = self.redis_client.pipeline()
            pipe.get(f"cache:{key}")
            pipe.hgetall(f"meta:{key}")
            results = await pipe.execute()
            
            cached_data, metadata = results
            
            if cached_data is None:
                return None
            
            # Update access metrics
            access_time = (time.perf_counter() - start_time) * 1000
            await self._update_redis_access_metrics(key, access_time)
            
            # Deserialize data
            try:
                value = json.loads(cached_data)
                self.metrics[CacheLevel.L2_REDIS].hits += 1
                return value
            except json.JSONDecodeError:
                # Handle non-JSON data (strings, etc.)
                self.metrics[CacheLevel.L2_REDIS].hits += 1
                return cached_data.decode('utf-8') if isinstance(cached_data, bytes) else cached_data
                
        except Exception as e:
            self.logger.error(
                "Redis cache get error",
                cache_key=key,
                error=str(e)
            )
            return None
    
    async def _set_in_redis(self, 
                           key: str, 
                           value: Any, 
                           expires_at: Optional[datetime],
                           tags: List[str]) -> bool:
        """Set value in L2 Redis cache"""
        
        if not self.redis_client:
            return False
        
        try:
            # Serialize value
            if isinstance(value, (dict, list)):
                serialized_value = json.dumps(value)
            else:
                serialized_value = str(value)
            
            # Calculate TTL
            ttl = None
            if expires_at:
                ttl = int((expires_at - datetime.utcnow()).total_seconds())
                if ttl <= 0:
                    return False
            
            # Store value and metadata
            pipe = self.redis_client.pipeline()
            
            if ttl:
                pipe.setex(f"cache:{key}", ttl, serialized_value)
            else:
                pipe.set(f"cache:{key}", serialized_value)
            
            # Store metadata
            metadata = {
                "created_at": datetime.utcnow().isoformat(),
                "tags": json.dumps(tags),
                "size": len(serialized_value)
            }
            pipe.hset(f"meta:{key}", mapping=metadata)
            
            if ttl:
                pipe.expire(f"meta:{key}", ttl)
            
            await pipe.execute()
            return True
            
        except Exception as e:
            self.logger.error(
                "Redis cache set error",
                cache_key=key,
                error=str(e)
            )
            return False
    
    async def _promote_entry(self, 
                            key: str, 
                            value: Any, 
                            current_level: CacheLevel,
                            available_levels: List[CacheLevel]) -> None:
        """Promote frequently accessed entries to higher cache levels"""
        
        if not self.optimization_enabled:
            return
        
        # Only promote from L2 to L1 for now
        if current_level != CacheLevel.L2_REDIS:
            return
        
        if CacheLevel.L1_MEMORY not in available_levels:
            return
        
        # Check if entry should be promoted based on access patterns
        should_promote = await self._should_promote_entry(key)
        
        if should_promote:
            await self._set_in_level(
                key, value, CacheLevel.L1_MEMORY, None, []
            )
            self.logger.info(
                "Cache entry promoted",
                cache_key=key,
                from_level=current_level.value,
                to_level=CacheLevel.L1_MEMORY.value
            )
    
    async def _should_promote_entry(self, key: str) -> bool:
        """Determine if entry should be promoted to higher cache level"""
        
        # Simple promotion strategy based on access frequency
        # In real implementation, this could be more sophisticated
        
        if key in self._access_times:
            recent_accesses = self._access_times[key]
            if len(recent_accesses) >= 5:  # Accessed 5+ times
                # Check access frequency (accesses per minute)
                if len(recent_accesses) >= 2:
                    time_span = recent_accesses[-1] - recent_accesses[0]
                    if time_span > 0:
                        access_rate = len(recent_accesses) / time_span * 60  # per minute
                        return access_rate > 10  # More than 10 accesses per minute
        
        return False
    
    async def _check_memory_limit(self, additional_size: int) -> bool:
        """Check if adding entry would exceed memory limit"""
        
        current_memory = await self._calculate_memory_usage()
        return (current_memory + additional_size) <= self.max_memory_size
    
    async def _calculate_memory_usage(self) -> int:
        """Calculate current memory cache usage"""
        
        total_size = 0
        for entry in self._memory_cache.values():
            total_size += entry.size_bytes
        
        return total_size
    
    async def _evict_memory_entries(self, required_space: int) -> bool:
        """Evict entries from memory cache to free space"""
        
        if not self.auto_eviction_enabled:
            return False
        
        # Sort entries by priority (LRU + access frequency)
        entries_by_priority = sorted(
            self._memory_cache.items(),
            key=lambda x: (x[1].last_accessed.timestamp(), x[1].access_count)
        )
        
        freed_space = 0
        evicted_keys = []
        
        for key, entry in entries_by_priority:
            if freed_space >= required_space:
                break
            
            freed_space += entry.size_bytes
            evicted_keys.append(key)
        
        # Remove evicted entries
        for key in evicted_keys:
            del self._memory_cache[key]
            if key in self._access_times:
                del self._access_times[key]
            self.metrics[CacheLevel.L1_MEMORY].evictions += 1
        
        if freed_space >= required_space:
            self.logger.info(
                "Memory cache eviction completed",
                evicted_entries=len(evicted_keys),
                freed_space_bytes=freed_space
            )
            return True
        
        return False
    
    async def _check_memory_optimization(self) -> None:
        """Check if memory optimization is needed"""
        
        current_usage = await self._calculate_memory_usage()
        usage_percentage = (current_usage / self.max_memory_size) * 100
        
        if usage_percentage > 80:  # 80% memory usage threshold
            await self._optimize_memory_cache()
    
    async def _optimize_memory_cache(self) -> None:
        """Optimize memory cache by removing expired and low-value entries"""
        
        optimization_start = time.perf_counter()
        
        # Remove expired entries
        expired_keys = []
        for key, entry in self._memory_cache.items():
            if entry.is_expired():
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._memory_cache[key]
            if key in self._access_times:
                del self._access_times[key]
        
        # Remove low-value entries if still over threshold
        current_usage = await self._calculate_memory_usage()
        if current_usage > self.max_memory_size * 0.7:  # 70% threshold
            await self._evict_memory_entries(current_usage - int(self.max_memory_size * 0.6))
        
        optimization_time = (time.perf_counter() - optimization_start) * 1000
        
        self.logger.info(
            "Memory cache optimization completed",
            expired_entries_removed=len(expired_keys),
            optimization_time_ms=optimization_time,
            final_memory_usage=await self._calculate_memory_usage()
        )
    
    async def _update_access_metrics(self, 
                                   key: str, 
                                   cache_level: CacheLevel, 
                                   access_time: float) -> None:
        """Update access metrics for cache level"""
        
        metrics = self.metrics[cache_level]
        
        # Update average access time
        if metrics.avg_access_time_ms == 0:
            metrics.avg_access_time_ms = access_time
        else:
            # Exponential moving average
            metrics.avg_access_time_ms = (metrics.avg_access_time_ms * 0.9) + (access_time * 0.1)
        
        # Calculate hit rate
        metrics.calculate_hit_rate()
    
    async def _update_redis_access_metrics(self, key: str, access_time: float) -> None:
        """Update Redis-specific access metrics"""
        
        try:
            # Increment access count in Redis
            await self.redis_client.hincrby(f"meta:{key}", "access_count", 1)
            await self.redis_client.hset(f"meta:{key}", "last_accessed", datetime.utcnow().isoformat())
        except Exception as e:
            self.logger.warning(
                "Failed to update Redis access metrics",
                cache_key=key,
                error=str(e)
            )
    
    async def _update_memory_metrics(self) -> None:
        """Update memory cache metrics"""
        
        metrics = self.metrics[CacheLevel.L1_MEMORY]
        metrics.entries_count = len(self._memory_cache)
        metrics.memory_usage_bytes = await self._calculate_memory_usage()
    
    async def invalidate_by_pattern(self, pattern: str) -> int:
        """Invalidate cache entries matching pattern"""
        
        invalidated_count = 0
        correlation_id = get_correlation_id()
        
        # Invalidate from memory cache
        keys_to_remove = []
        for key in self._memory_cache:
            if self._pattern_matches(key, pattern):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._memory_cache[key]
            if key in self._access_times:
                del self._access_times[key]
            invalidated_count += 1
        
        # Invalidate from Redis cache
        if self.redis_client:
            try:
                redis_pattern = f"cache:{pattern}"
                keys = await self.redis_client.keys(redis_pattern)
                if keys:
                    # Delete cache entries and metadata
                    pipe = self.redis_client.pipeline()
                    for key in keys:
                        pipe.delete(key)
                        # Also delete metadata
                        meta_key = key.decode('utf-8').replace('cache:', 'meta:')
                        pipe.delete(meta_key)
                    
                    await pipe.execute()
                    invalidated_count += len(keys)
                    
            except Exception as e:
                self.logger.error(
                    "Redis cache invalidation error",
                    pattern=pattern,
                    error=str(e),
                    correlation_id=correlation_id
                )
        
        self.logger.info(
            "Cache invalidation completed",
            pattern=pattern,
            invalidated_entries=invalidated_count,
            correlation_id=correlation_id
        )
        
        return invalidated_count
    
    async def invalidate_by_tags(self, tags: List[str]) -> int:
        """Invalidate cache entries by tags"""
        
        invalidated_count = 0
        
        # Invalidate from memory cache
        keys_to_remove = []
        for key, entry in self._memory_cache.items():
            if any(tag in entry.tags for tag in tags):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._memory_cache[key]
            if key in self._access_times:
                del self._access_times[key]
            invalidated_count += 1
        
        # Redis tag-based invalidation would require additional indexing
        # For now, we skip Redis tag invalidation
        
        return invalidated_count
    
    def _pattern_matches(self, key: str, pattern: str) -> bool:
        """Simple pattern matching (supports * wildcard)"""
        
        if '*' not in pattern:
            return key == pattern
        
        # Convert pattern to regex-like matching
        pattern_parts = pattern.split('*')
        
        if len(pattern_parts) == 2:
            prefix, suffix = pattern_parts
            return key.startswith(prefix) and key.endswith(suffix)
        
        # More complex pattern matching could be implemented here
        return False
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        
        stats = {}
        
        for cache_level, metrics in self.metrics.items():
            stats[cache_level.value] = {
                "hits": metrics.hits,
                "misses": metrics.misses,
                "hit_rate": f"{metrics.calculate_hit_rate():.2f}%",
                "evictions": metrics.evictions,
                "entries_count": metrics.entries_count,
                "memory_usage_bytes": metrics.memory_usage_bytes,
                "avg_access_time_ms": f"{metrics.avg_access_time_ms:.2f}ms"
            }
        
        # Additional memory cache stats
        stats["l1_memory"]["max_memory_size"] = self.max_memory_size
        stats["l1_memory"]["memory_usage_percentage"] = f"{(await self._calculate_memory_usage() / self.max_memory_size) * 100:.2f}%"
        
        return stats
    
    async def warm_cache(self, warm_data: Dict[str, Any]) -> int:
        """Warm cache with initial data"""
        
        warmed_count = 0
        
        for key, value in warm_data.items():
            success = await self.set(key, value)
            if success:
                warmed_count += 1
        
        self.logger.info(
            "Cache warming completed",
            warmed_entries=warmed_count,
            total_entries=len(warm_data)
        )
        
        return warmed_count


def cache_result(ttl: int = 3600, 
                cache_levels: Optional[List[CacheLevel]] = None,
                tags: Optional[List[str]] = None):
    """Decorator for caching function results"""
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key = f"{func.__name__}:{hashlib.md5(str(args).encode() + str(kwargs).encode()).hexdigest()}"
            
            # Try to get from cache first (assumes cache manager is available)
            # In real implementation, cache manager would be injected or available globally
            
            # Execute function if not in cache
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            
            # Store result in cache (implementation would use actual cache manager)
            
            return result
        
        return wrapper
    return decorator


# Global cache manager instance
_cache_manager: Optional[AdvancedCacheManager] = None


def get_cache_manager() -> AdvancedCacheManager:
    """Get global cache manager instance"""
    global _cache_manager
    if _cache_manager is None:
        raise RuntimeError("Cache manager not initialized")
    return _cache_manager


def initialize_cache_manager(redis_client: Optional[redis.Redis] = None,
                           max_memory_size: int = 100 * 1024 * 1024) -> AdvancedCacheManager:
    """Initialize global cache manager"""
    global _cache_manager
    _cache_manager = AdvancedCacheManager(
        redis_client=redis_client,
        max_memory_size=max_memory_size
    )
    return _cache_manager