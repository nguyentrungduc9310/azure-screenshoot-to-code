"""
Performance Optimization Middleware
FastAPI middleware for automatic performance optimization
"""
import asyncio
import time
from typing import Dict, Any, Optional, Callable
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

try:
    from shared.monitoring.structured_logger import StructuredLogger
    from shared.monitoring.correlation import get_correlation_id, set_correlation_id
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger
    
    def get_correlation_id():
        import uuid
        return str(uuid.uuid4())[:8]
    
    def set_correlation_id(correlation_id: str):
        pass

from .performance_integration import PerformanceIntegrationManager, get_performance_manager


class PerformanceOptimizationMiddleware(BaseHTTPMiddleware):
    """Middleware for automatic performance optimization of requests"""
    
    def __init__(self, 
                 app,
                 performance_manager: Optional[PerformanceIntegrationManager] = None,
                 logger: Optional[StructuredLogger] = None,
                 enable_request_caching: bool = True,
                 enable_response_compression: bool = True,
                 enable_performance_headers: bool = True,
                 cache_ttl_seconds: int = 300):
        
        super().__init__(app)
        self.performance_manager = performance_manager or get_performance_manager()
        self.logger = logger or StructuredLogger()
        self.enable_request_caching = enable_request_caching
        self.enable_response_compression = enable_response_compression
        self.enable_performance_headers = enable_performance_headers
        self.cache_ttl_seconds = cache_ttl_seconds
        
        # Performance tracking
        self.request_count = 0
        self.total_response_time = 0.0
        self.cache_hits = 0
        
        # Cacheable endpoints (GET requests to these paths)
        self.cacheable_endpoints = {
            "/health",
            "/metrics",
            "/api/status",
            "/api/frameworks",
            "/api/user/preferences"
        }
        
        # Non-cacheable endpoints (always process fresh)
        self.non_cacheable_endpoints = {
            "/copilot-studio/webhook",
            "/api/generate-code",
            "/api/process-screenshot"
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with performance optimization"""
        
        start_time = time.perf_counter()
        correlation_id = get_correlation_id()
        set_correlation_id(correlation_id)
        
        # Update request tracking
        self.request_count += 1
        
        try:
            # Check if request is cacheable
            is_cacheable = self._is_request_cacheable(request)
            
            # Try to serve from cache if enabled and cacheable
            if self.enable_request_caching and is_cacheable:
                cached_response = await self._get_cached_response(request, correlation_id)
                if cached_response:
                    self.cache_hits += 1
                    return cached_response
            
            # Process request with optimization context
            async with self.performance_manager.optimized_request_context(
                request_data=await self._extract_request_data(request),
                operation_name=f"{request.method}:{request.url.path}"
            ) as ctx:
                
                # If served from cache at optimization level
                if ctx.get("from_cache"):
                    response = self._create_json_response(ctx["result"])
                else:
                    # Process request normally
                    response = await call_next(request)
                
                # Cache response if appropriate
                if self.enable_request_caching and is_cacheable and response.status_code == 200:
                    await self._cache_response(request, response, correlation_id)
                
                # Add performance headers
                if self.enable_performance_headers:
                    self._add_performance_headers(response, start_time, correlation_id, ctx.get("from_cache", False))
                
                # Compress response if enabled
                if self.enable_response_compression:
                    response = await self._compress_response(response)
                
                return response
        
        except Exception as e:
            processing_time = (time.perf_counter() - start_time) * 1000
            
            self.logger.error(
                "Performance middleware error",
                path=request.url.path,
                method=request.method,
                error=str(e),
                processing_time_ms=processing_time,
                correlation_id=correlation_id
            )
            
            # Return error response with performance headers
            error_response = JSONResponse(
                status_code=500,
                content={"error": "Internal server error", "correlation_id": correlation_id}
            )
            
            if self.enable_performance_headers:
                self._add_performance_headers(error_response, start_time, correlation_id, False)
            
            return error_response
        
        finally:
            # Update performance metrics
            processing_time = (time.perf_counter() - start_time) * 1000
            self.total_response_time += processing_time
            
            # Log performance metrics periodically
            if self.request_count % 100 == 0:
                avg_response_time = self.total_response_time / self.request_count
                cache_hit_rate = (self.cache_hits / self.request_count) * 100
                
                self.logger.info(
                    "Performance middleware metrics",
                    total_requests=self.request_count,
                    avg_response_time_ms=f"{avg_response_time:.2f}",
                    cache_hit_rate=f"{cache_hit_rate:.2f}%"
                )
    
    def _is_request_cacheable(self, request: Request) -> bool:
        """Determine if request is cacheable"""
        
        # Only GET requests are cacheable
        if request.method != "GET":
            return False
        
        # Check non-cacheable endpoints
        if request.url.path in self.non_cacheable_endpoints:
            return False
        
        # Check explicitly cacheable endpoints
        if request.url.path in self.cacheable_endpoints:
            return True
        
        # Check for query parameters that make requests non-cacheable
        if "timestamp" in request.query_params or "random" in request.query_params:
            return False
        
        # Check for user-specific parameters
        if "user_id" in request.query_params or "session_id" in request.query_params:
            return False
        
        # Default: cache GET requests to API endpoints
        return request.url.path.startswith("/api/")
    
    async def _get_cached_response(self, request: Request, correlation_id: str) -> Optional[Response]:
        """Get cached response for request"""
        
        if not self.performance_manager.cache_manager:
            return None
        
        try:
            cache_key = self._generate_request_cache_key(request)
            cached_data = await self.performance_manager.cache_manager.get(cache_key)
            
            if cached_data:
                self.logger.info(
                    "Request served from cache",
                    path=request.url.path,
                    cache_key=cache_key,
                    correlation_id=correlation_id
                )
                
                # Reconstruct response from cached data
                return JSONResponse(
                    status_code=cached_data.get("status_code", 200),
                    content=cached_data.get("content"),
                    headers=cached_data.get("headers", {})
                )
            
        except Exception as e:
            self.logger.warning(
                "Cache retrieval error",
                path=request.url.path,
                error=str(e),
                correlation_id=correlation_id
            )
        
        return None
    
    async def _cache_response(self, request: Request, response: Response, correlation_id: str):
        """Cache response for future requests"""
        
        if not self.performance_manager.cache_manager:
            return
        
        try:
            # Only cache successful JSON responses
            if response.status_code != 200:
                return
            
            # Read response content
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk
            
            # Parse JSON content
            try:
                import json
                content = json.loads(response_body.decode())
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Don't cache non-JSON responses
                return
            
            # Create cache entry
            cache_data = {
                "status_code": response.status_code,
                "content": content,
                "headers": dict(response.headers),
                "cached_at": time.time()
            }
            
            cache_key = self._generate_request_cache_key(request)
            await self.performance_manager.cache_manager.set(
                key=cache_key,
                value=cache_data,
                ttl=self.cache_ttl_seconds,
                tags=["http_cache", request.url.path.split("/")[1] if "/" in request.url.path else "root"]
            )
            
            # Recreate response with same content
            response.body_iterator = self._create_body_iterator(response_body)
            
            self.logger.info(
                "Response cached",
                path=request.url.path,
                cache_key=cache_key,
                ttl_seconds=self.cache_ttl_seconds,
                correlation_id=correlation_id
            )
            
        except Exception as e:
            self.logger.warning(
                "Response caching error",
                path=request.url.path,
                error=str(e),
                correlation_id=correlation_id
            )
    
    def _generate_request_cache_key(self, request: Request) -> str:
        """Generate cache key for request"""
        import hashlib
        
        # Include method, path, and sorted query parameters
        key_components = [
            request.method,
            request.url.path,
            "&".join(f"{k}={v}" for k, v in sorted(request.query_params.items()))
        ]
        
        key_string = "|".join(key_components)
        return f"http_cache:{hashlib.md5(key_string.encode()).hexdigest()}"
    
    async def _extract_request_data(self, request: Request) -> Dict[str, Any]:
        """Extract request data for optimization context"""
        
        request_data = {
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": dict(request.headers),
            "client_ip": request.client.host if request.client else None
        }
        
        # Include body for POST/PUT requests
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    # Try to parse JSON body
                    try:
                        import json
                        request_data["body"] = json.loads(body.decode())
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        request_data["body_size"] = len(body)
            except Exception:
                pass
        
        return request_data
    
    def _create_json_response(self, data: Any) -> Response:
        """Create JSON response from data"""
        return JSONResponse(content=data)
    
    def _add_performance_headers(self, 
                               response: Response, 
                               start_time: float, 
                               correlation_id: str,
                               from_cache: bool = False):
        """Add performance-related headers to response"""
        
        processing_time = (time.perf_counter() - start_time) * 1000
        
        response.headers["X-Response-Time"] = f"{processing_time:.2f}ms"
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-From-Cache"] = "true" if from_cache else "false"
        response.headers["X-Request-Count"] = str(self.request_count)
        
        if self.request_count > 0:
            avg_response_time = self.total_response_time / self.request_count
            response.headers["X-Avg-Response-Time"] = f"{avg_response_time:.2f}ms"
        
        if self.request_count > 0:
            cache_hit_rate = (self.cache_hits / self.request_count) * 100
            response.headers["X-Cache-Hit-Rate"] = f"{cache_hit_rate:.2f}%"
    
    async def _compress_response(self, response: Response) -> Response:
        """Compress response if beneficial"""
        
        # Simple compression check - only compress large JSON responses
        if not hasattr(response, 'body_iterator'):
            return response
        
        try:
            # Read response content
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk
            
            # Only compress if response is large enough
            if len(response_body) < 1024:  # Less than 1KB
                response.body_iterator = self._create_body_iterator(response_body)
                return response
            
            # Check if content is already compressed
            if response.headers.get("content-encoding"):
                response.body_iterator = self._create_body_iterator(response_body)
                return response
            
            # Apply gzip compression
            import gzip
            compressed_body = gzip.compress(response_body)
            
            # Only use compression if it actually reduces size
            if len(compressed_body) < len(response_body):
                response.headers["Content-Encoding"] = "gzip"
                response.headers["Content-Length"] = str(len(compressed_body))
                response.body_iterator = self._create_body_iterator(compressed_body)
                
                self.logger.debug(
                    "Response compressed",
                    original_size=len(response_body),
                    compressed_size=len(compressed_body),
                    compression_ratio=f"{(1 - len(compressed_body) / len(response_body)) * 100:.1f}%"
                )
            else:
                response.body_iterator = self._create_body_iterator(response_body)
            
        except Exception as e:
            self.logger.warning(
                "Response compression error",
                error=str(e)
            )
        
        return response
    
    def _create_body_iterator(self, body: bytes):
        """Create async iterator for response body"""
        async def body_iterator():
            yield body
        return body_iterator()


class PerformanceMetricsEndpoint:
    """Endpoint for exposing performance metrics"""
    
    def __init__(self, 
                 performance_manager: Optional[PerformanceIntegrationManager] = None,
                 middleware: Optional[PerformanceOptimizationMiddleware] = None):
        
        self.performance_manager = performance_manager or get_performance_manager()
        self.middleware = middleware
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics"""
        
        metrics = {
            "timestamp": time.time(),
            "performance_integration": await self.performance_manager.get_performance_stats()
        }
        
        # Add middleware metrics if available
        if self.middleware:
            metrics["middleware"] = {
                "total_requests": self.middleware.request_count,
                "cache_hits": self.middleware.cache_hits,
                "avg_response_time_ms": (
                    self.middleware.total_response_time / max(self.middleware.request_count, 1)
                ),
                "cache_hit_rate": (
                    self.middleware.cache_hits / max(self.middleware.request_count, 1) * 100
                )
            }
        
        return metrics
    
    async def get_health(self) -> Dict[str, Any]:
        """Get performance health status"""
        
        stats = await self.performance_manager.get_performance_stats()
        integration_metrics = stats.get("integration_metrics", {})
        
        # Determine health status
        avg_response_time = integration_metrics.get("avg_response_time", 0)
        cache_hit_rate = integration_metrics.get("cache_hit_rate", 0)
        
        is_healthy = (
            avg_response_time < 2000 and  # Less than 2 seconds
            (cache_hit_rate > 10 or integration_metrics.get("total_requests", 0) < 100)  # Good cache performance or low volume
        )
        
        return {
            "status": "healthy" if is_healthy else "degraded",
            "avg_response_time_ms": avg_response_time,
            "cache_hit_rate": f"{cache_hit_rate:.2f}%",
            "total_requests": integration_metrics.get("total_requests", 0),
            "timestamp": time.time()
        }


# Helper functions for FastAPI integration
def create_performance_middleware(app,
                                performance_manager: Optional[PerformanceIntegrationManager] = None,
                                **kwargs) -> PerformanceOptimizationMiddleware:
    """Create and configure performance middleware"""
    
    middleware = PerformanceOptimizationMiddleware(
        app=app,
        performance_manager=performance_manager,
        **kwargs
    )
    
    return middleware


def add_performance_routes(app, 
                         performance_manager: Optional[PerformanceIntegrationManager] = None,
                         middleware: Optional[PerformanceOptimizationMiddleware] = None):
    """Add performance monitoring routes to FastAPI app"""
    
    metrics_endpoint = PerformanceMetricsEndpoint(
        performance_manager=performance_manager,
        middleware=middleware
    )
    
    @app.get("/api/performance/metrics")
    async def get_performance_metrics():
        return await metrics_endpoint.get_metrics()
    
    @app.get("/api/performance/health")
    async def get_performance_health():
        return await metrics_endpoint.get_health()
    
    @app.post("/api/performance/cache/invalidate")
    async def invalidate_cache(pattern: str = "*"):
        if performance_manager and performance_manager.cache_manager:
            count = await performance_manager.invalidate_cache_by_pattern(pattern)
            return {"invalidated_entries": count, "pattern": pattern}
        return {"error": "Cache manager not available"}