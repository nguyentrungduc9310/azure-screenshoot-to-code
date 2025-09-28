"""
Advanced Caching Middleware
Intelligent request/response caching with content-aware strategies
"""
import time
import hashlib
import json
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
import asyncio

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from starlette.responses import Response as StarletteResponse

from app.caching.redis_cache import AdvancedRedisCache
from app.performance.optimizer import PerformanceOptimizer
from shared.monitoring.structured_logger import StructuredLogger
from shared.monitoring.correlation import get_correlation_id

@dataclass
class CacheRule:
    """Cache rule configuration"""
    pattern: str
    ttl: int
    vary_headers: List[str]
    cache_post: bool = False
    cache_authenticated: bool = False
    invalidate_on: List[str] = None  # Invalidate on these patterns
    condition: Optional[Callable] = None

class CachingMiddleware(BaseHTTPMiddleware):
    """Advanced caching middleware with intelligent strategies"""
    
    def __init__(
        self,
        app: ASGIApp,
        cache: AdvancedRedisCache,
        optimizer: Optional[PerformanceOptimizer],
        logger: StructuredLogger
    ):
        super().__init__(app)
        self.cache = cache
        self.optimizer = optimizer
        self.logger = logger
        
        # Cache rules
        self.cache_rules = self._initialize_cache_rules()
        
        # Cache statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'bypassed': 0,
            'errors': 0
        }
        
        # Performance tracking
        self.response_times = {}
        
        self.logger.info("Caching middleware initialized",
                        rules_count=len(self.cache_rules))
    
    def _initialize_cache_rules(self) -> List[CacheRule]:
        """Initialize default cache rules"""
        return [
            # Health checks - short cache
            CacheRule(
                pattern="/health*",
                ttl=30,
                vary_headers=[],
                cache_post=False,
                cache_authenticated=True
            ),
            
            # API documentation - long cache
            CacheRule(
                pattern="/docs*",
                ttl=3600,  # 1 hour
                vary_headers=["Accept-Language"],
                cache_post=False,
                cache_authenticated=True
            ),
            
            # Static assets - very long cache
            CacheRule(
                pattern="/static/*",
                ttl=86400,  # 24 hours
                vary_headers=["Accept-Encoding"],
                cache_post=False,
                cache_authenticated=True
            ),
            
            # Metrics - short cache to balance performance and freshness
            CacheRule(
                pattern="/api/v1/metrics*",
                ttl=10,
                vary_headers=[],
                cache_post=False,
                cache_authenticated=False
            ),
            
            # Code generation results - medium cache
            CacheRule(
                pattern="/api/v1/generate/code",
                ttl=1800,  # 30 minutes
                vary_headers=["Authorization", "Content-Type"],
                cache_post=True,  # Cache POST requests
                cache_authenticated=True,
                invalidate_on=["/api/v1/generate/*"]
            ),
            
            # Image generation results - medium cache
            CacheRule(
                pattern="/api/v1/generate/image",
                ttl=1800,  # 30 minutes
                vary_headers=["Authorization", "Content-Type"],
                cache_post=True,
                cache_authenticated=True,
                invalidate_on=["/api/v1/generate/*"]
            ),
            
            # Service stats - short cache
            CacheRule(
                pattern="/api/v1/health/stats",
                ttl=60,  # 1 minute
                vary_headers=[],
                cache_post=False,
                cache_authenticated=False
            ),
            
            # Alert information - very short cache
            CacheRule(
                pattern="/api/v1/alerts*",
                ttl=30,
                vary_headers=["Authorization"],
                cache_post=False,
                cache_authenticated=True
            ),
            
            # Observability data - short cache
            CacheRule(
                pattern="/api/v1/observability",
                ttl=60,
                vary_headers=[],
                cache_post=False,
                cache_authenticated=False
            )
        ]
    
    async def dispatch(self, request: Request, call_next):
        """Process request with intelligent caching"""
        start_time = time.time()
        correlation_id = get_correlation_id()
        
        # Check if request should be cached
        cache_rule = self._match_cache_rule(request)
        if not cache_rule:
            # No cache rule, pass through
            self.stats['bypassed'] += 1
            response = await call_next(request)
            
            # Record performance data
            if self.optimizer:
                duration = time.time() - start_time
                await self.optimizer.record_request(
                    endpoint=request.url.path,
                    method=request.method,
                    duration=duration,
                    status_code=response.status_code,
                    cache_hit=False
                )
            
            return response
        
        # Check cache condition
        if cache_rule.condition and not cache_rule.condition(request):
            self.stats['bypassed'] += 1
            response = await call_next(request)
            
            if self.optimizer:
                duration = time.time() - start_time
                await self.optimizer.record_request(
                    endpoint=request.url.path,
                    method=request.method,
                    duration=duration,
                    status_code=response.status_code,
                    cache_hit=False
                )
            
            return response
        
        # Generate cache key
        cache_key = await self._generate_cache_key(request, cache_rule)
        
        # Try to get from cache
        try:
            cached_response = await self.cache.get(
                key=cache_key,
                namespace="http_responses"
            )
            
            if cached_response:
                # Cache hit
                self.stats['hits'] += 1
                duration = time.time() - start_time
                
                self.logger.debug("Cache hit",
                                path=request.url.path,
                                method=request.method,
                                cache_key=cache_key[:50],
                                duration_ms=duration * 1000,
                                correlation_id=correlation_id)
                
                # Record performance data
                if self.optimizer:
                    await self.optimizer.record_request(
                        endpoint=request.url.path,
                        method=request.method,
                        duration=duration,
                        status_code=cached_response['status_code'],
                        cache_hit=True
                    )
                
                # Return cached response
                return self._create_response_from_cache(cached_response)
            
        except Exception as e:
            self.logger.warning("Cache get error",
                              path=request.url.path,
                              cache_key=cache_key[:50],
                              error=str(e),
                              correlation_id=correlation_id)
            self.stats['errors'] += 1
        
        # Cache miss - execute request
        self.stats['misses'] += 1
        response = await call_next(request)
        request_duration = time.time() - start_time
        
        # Record performance data
        if self.optimizer:
            await self.optimizer.record_request(
                endpoint=request.url.path,
                method=request.method,
                duration=request_duration,
                status_code=response.status_code,
                cache_hit=False
            )
        
        # Cache response if appropriate
        if self._should_cache_response(request, response, cache_rule):
            try:
                await self._cache_response(request, response, cache_rule, cache_key)
                self.stats['sets'] += 1
                
                self.logger.debug("Response cached",
                                path=request.url.path,
                                method=request.method,
                                status_code=response.status_code,
                                cache_key=cache_key[:50],
                                ttl=cache_rule.ttl,
                                correlation_id=correlation_id)
                
            except Exception as e:
                self.logger.warning("Cache set error",
                                  path=request.url.path,
                                  cache_key=cache_key[:50],
                                  error=str(e),
                                  correlation_id=correlation_id)
                self.stats['errors'] += 1
        
        # Add cache headers
        response.headers["X-Cache-Status"] = "MISS"
        response.headers["X-Cache-Key"] = cache_key[:50]
        
        return response
    
    def _match_cache_rule(self, request: Request) -> Optional[CacheRule]:
        """Find matching cache rule for request"""
        path = request.url.path
        method = request.method
        
        for rule in self.cache_rules:
            # Simple pattern matching (in production, use regex or fnmatch)
            if self._pattern_matches(rule.pattern, path):
                # Check method constraints
                if method == "POST" and not rule.cache_post:
                    continue
                
                # Check authentication constraints
                if not rule.cache_authenticated and self._is_authenticated(request):
                    continue
                
                return rule
        
        return None
    
    def _pattern_matches(self, pattern: str, path: str) -> bool:
        """Check if path matches pattern"""
        if pattern.endswith("*"):
            return path.startswith(pattern[:-1])
        return pattern == path
    
    def _is_authenticated(self, request: Request) -> bool:
        """Check if request is authenticated"""
        return "Authorization" in request.headers
    
    async def _generate_cache_key(self, request: Request, cache_rule: CacheRule) -> str:
        """Generate cache key for request"""
        key_parts = [
            request.method,
            request.url.path,
            str(sorted(request.query_params.items()))
        ]
        
        # Add vary headers
        for header in cache_rule.vary_headers:
            header_value = request.headers.get(header, "")
            key_parts.append(f"{header}:{header_value}")
        
        # Add request body for POST/PUT/PATCH requests
        if request.method in ["POST", "PUT", "PATCH"] and cache_rule.cache_post:
            try:
                # Read body
                body = await request.body()
                if body:
                    # Hash body to avoid long keys
                    body_hash = hashlib.sha256(body).hexdigest()[:16]
                    key_parts.append(f"body:{body_hash}")
            except Exception as e:
                self.logger.warning("Failed to read request body for cache key",
                                  error=str(e))
        
        # Generate final key
        key_string = "|".join(key_parts)
        
        # Hash if too long
        if len(key_string) > 200:
            return hashlib.sha256(key_string.encode()).hexdigest()
        
        return key_string
    
    def _should_cache_response(
        self,
        request: Request,
        response: Response,
        cache_rule: CacheRule
    ) -> bool:
        """Determine if response should be cached"""
        
        # Only cache successful responses
        if not (200 <= response.status_code < 300):
            return False
        
        # Check for no-cache headers
        cache_control = response.headers.get("cache-control", "").lower()
        if "no-cache" in cache_control or "no-store" in cache_control:
            return False
        
        # Check response size (don't cache very large responses)
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > 10 * 1024 * 1024:  # 10MB
            return False
        
        # Check content type (cache JSON, HTML, but be careful with binary)
        content_type = response.headers.get("content-type", "").lower()
        cacheable_types = [
            "application/json",
            "text/html",
            "text/plain",
            "text/css",
            "application/javascript",
            "image/",
            "font/"
        ]
        
        if not any(content_type.startswith(ct) for ct in cacheable_types):
            return False
        
        return True
    
    async def _cache_response(
        self,
        request: Request,
        response: Response,
        cache_rule: CacheRule,
        cache_key: str
    ):
        """Cache response data"""
        
        # Read response body
        body = b""
        if hasattr(response, 'body'):
            body = response.body
        elif hasattr(response, 'body_iterator'):
            # For streaming responses, we might need to buffer
            chunks = []
            async for chunk in response.body_iterator:
                chunks.append(chunk)
                body = b"".join(chunks)
        
        # Prepare cache data
        cache_data = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": body.decode('utf-8', errors='ignore') if body else "",
            "content_type": response.headers.get("content-type", ""),
            "cached_at": time.time(),
            "cache_rule": cache_rule.pattern
        }
        
        # Generate cache tags for invalidation
        tags = ["http_responses"]
        if cache_rule.invalidate_on:
            tags.extend(cache_rule.invalidate_on)
        
        # Add endpoint-specific tag
        tags.append(f"endpoint:{request.url.path}")
        
        # Cache the response
        await self.cache.set(
            key=cache_key,
            value=cache_data,
            ttl=cache_rule.ttl,
            namespace="http_responses",
            tags=tags
        )
    
    def _create_response_from_cache(self, cached_data: Dict[str, Any]) -> Response:
        """Create response from cached data"""
        
        # Create response
        response = Response(
            content=cached_data.get("body", ""),
            status_code=cached_data.get("status_code", 200),
            headers=cached_data.get("headers", {}),
            media_type=cached_data.get("content_type")
        )
        
        # Add cache headers
        response.headers["X-Cache-Status"] = "HIT"
        response.headers["X-Cache-Age"] = str(int(time.time() - cached_data.get("cached_at", 0)))
        
        return response
    
    async def invalidate_cache_by_pattern(self, pattern: str) -> int:
        """Invalidate cached responses by pattern"""
        try:
            cache_pattern = f"http_responses:*{pattern}*"
            invalidated = await self.cache.invalidate_by_pattern(cache_pattern)
            
            self.logger.info("Cache invalidated by pattern",
                           pattern=pattern,
                           invalidated_count=invalidated)
            
            return invalidated
            
        except Exception as e:
            self.logger.error("Cache invalidation error",
                            pattern=pattern,
                            error=str(e))
            return 0
    
    async def invalidate_cache_by_tags(self, tags: List[str]) -> int:
        """Invalidate cached responses by tags"""
        try:
            invalidated = await self.cache.invalidate_by_tags(tags)
            
            self.logger.info("Cache invalidated by tags",
                           tags=tags,
                           invalidated_count=invalidated)
            
            return invalidated
            
        except Exception as e:
            self.logger.error("Cache tag invalidation error",
                            tags=tags,
                            error=str(e))
            return 0
    
    async def warm_cache(self, endpoints: List[Dict[str, Any]]):
        """Warm cache with popular endpoints"""
        self.logger.info("Starting cache warm-up",
                        endpoints_count=len(endpoints))
        
        warmed = 0
        
        for endpoint_config in endpoints:
            try:
                # Simulate request to warm cache
                path = endpoint_config.get("path")
                method = endpoint_config.get("method", "GET")
                
                # This would typically make internal requests
                # For now, we'll just log the intent
                self.logger.debug("Cache warm-up",
                                path=path,
                                method=method)
                warmed += 1
                
            except Exception as e:
                self.logger.warning("Cache warm-up failed",
                                  endpoint=endpoint_config,
                                  error=str(e))
        
        self.logger.info("Cache warm-up completed",
                        warmed_count=warmed,
                        total_count=len(endpoints))
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get caching middleware statistics"""
        total_requests = sum(self.stats.values())
        hit_rate = self.stats['hits'] / max(total_requests, 1)
        
        return {
            "statistics": {
                "hits": self.stats['hits'],
                "misses": self.stats['misses'],
                "sets": self.stats['sets'],
                "bypassed": self.stats['bypassed'],
                "errors": self.stats['errors'],
                "total_requests": total_requests,
                "hit_rate": hit_rate,
                "miss_rate": 1.0 - hit_rate
            },
            "rules": [
                {
                    "pattern": rule.pattern,
                    "ttl": rule.ttl,
                    "vary_headers": rule.vary_headers,
                    "cache_post": rule.cache_post,
                    "cache_authenticated": rule.cache_authenticated
                }
                for rule in self.cache_rules
            ]
        }

class SmartCachingMiddleware(CachingMiddleware):
    """Smart caching middleware with ML-based optimization"""
    
    def __init__(
        self,
        app: ASGIApp,
        cache: AdvancedRedisCache,
        optimizer: Optional[PerformanceOptimizer],
        logger: StructuredLogger
    ):
        super().__init__(app, cache, optimizer, logger)
        
        # Smart caching features
        self.endpoint_performance = {}
        self.cache_effectiveness = {}
        self.adaptive_ttl = {}
        
        self.logger.info("Smart caching middleware initialized")
    
    async def dispatch(self, request: Request, call_next):
        """Process request with smart caching decisions"""
        
        # Record endpoint access patterns
        endpoint = f"{request.method} {request.url.path}"
        current_time = time.time()
        
        if endpoint not in self.endpoint_performance:
            self.endpoint_performance[endpoint] = {
                'access_count': 0,
                'total_duration': 0.0,
                'cache_hits': 0,
                'last_access': current_time
            }
        
        self.endpoint_performance[endpoint]['access_count'] += 1
        self.endpoint_performance[endpoint]['last_access'] = current_time
        
        # Use parent dispatch with enhancements
        start_time = time.time()
        response = await super().dispatch(request, call_next)
        duration = time.time() - start_time
        
        # Update performance tracking
        self.endpoint_performance[endpoint]['total_duration'] += duration
        
        # Check if this was a cache hit
        if response.headers.get("X-Cache-Status") == "HIT":
            self.endpoint_performance[endpoint]['cache_hits'] += 1
        
        # Adaptive TTL adjustment
        await self._adjust_adaptive_ttl(endpoint, response.status_code, duration)
        
        return response
    
    async def _adjust_adaptive_ttl(self, endpoint: str, status_code: int, duration: float):
        """Adjust TTL based on endpoint performance"""
        
        perf = self.endpoint_performance.get(endpoint)
        if not perf or perf['access_count'] < 10:
            return  # Need more data
        
        # Calculate metrics
        avg_duration = perf['total_duration'] / perf['access_count']
        cache_hit_rate = perf['cache_hits'] / perf['access_count']
        access_frequency = perf['access_count'] / max((time.time() - perf['last_access']) / 3600, 1)  # per hour
        
        # Adaptive TTL logic
        base_ttl = 300  # 5 minutes default
        
        # Increase TTL for:
        # - Slow endpoints (more benefit from caching)
        # - High cache hit rates (content is stable)
        # - Frequently accessed endpoints
        
        duration_factor = min(avg_duration / 1.0, 3.0)  # Max 3x for very slow endpoints
        hit_rate_factor = 1.0 + cache_hit_rate  # 1.0 to 2.0
        frequency_factor = min(access_frequency / 10.0, 2.0)  # Max 2x for very frequent
        
        adaptive_ttl = int(base_ttl * duration_factor * hit_rate_factor * frequency_factor)
        adaptive_ttl = max(60, min(adaptive_ttl, 3600))  # Between 1 minute and 1 hour
        
        self.adaptive_ttl[endpoint] = adaptive_ttl
        
        self.logger.debug("Adaptive TTL calculated",
                        endpoint=endpoint,
                        avg_duration=avg_duration,
                        cache_hit_rate=cache_hit_rate,
                        access_frequency=access_frequency,
                        adaptive_ttl=adaptive_ttl)
    
    def _match_cache_rule(self, request: Request) -> Optional[CacheRule]:
        """Enhanced cache rule matching with adaptive TTL"""
        rule = super()._match_cache_rule(request)
        
        if rule:
            # Check for adaptive TTL
            endpoint = f"{request.method} {request.url.path}"
            if endpoint in self.adaptive_ttl:
                # Create modified rule with adaptive TTL
                adaptive_rule = CacheRule(
                    pattern=rule.pattern,
                    ttl=self.adaptive_ttl[endpoint],
                    vary_headers=rule.vary_headers,
                    cache_post=rule.cache_post,
                    cache_authenticated=rule.cache_authenticated,
                    invalidate_on=rule.invalidate_on,
                    condition=rule.condition
                )
                return adaptive_rule
        
        return rule
    
    def get_smart_cache_stats(self) -> Dict[str, Any]:
        """Get smart caching statistics"""
        base_stats = self.get_cache_stats()
        
        # Add smart caching specific stats
        base_stats.update({
            "smart_features": {
                "endpoints_tracked": len(self.endpoint_performance),
                "adaptive_ttl_endpoints": len(self.adaptive_ttl),
                "avg_adaptive_ttl": statistics.mean(self.adaptive_ttl.values()) if self.adaptive_ttl else 0
            },
            "top_cached_endpoints": [
                {
                    "endpoint": endpoint,
                    "access_count": perf['access_count'],
                    "avg_duration_ms": (perf['total_duration'] / perf['access_count']) * 1000,
                    "cache_hit_rate": perf['cache_hits'] / perf['access_count'],
                    "adaptive_ttl": self.adaptive_ttl.get(endpoint, 0)
                }
                for endpoint, perf in sorted(
                    self.endpoint_performance.items(),
                    key=lambda x: x[1]['access_count'],
                    reverse=True
                )[:10]
            ]
        })
        
        return base_stats