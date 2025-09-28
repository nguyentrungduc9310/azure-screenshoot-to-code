"""
Monitoring Middleware
Integrates Prometheus metrics, OpenTelemetry tracing, and alerting
"""
import time
import asyncio
from typing import Optional, Dict, Any
import json

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.monitoring.prometheus_metrics import PrometheusMetrics
from app.monitoring.opentelemetry_tracing import TracingManager
from app.monitoring.alerting import AlertManager
from shared.monitoring.structured_logger import StructuredLogger
from shared.monitoring.correlation import get_correlation_id

class MonitoringMiddleware(BaseHTTPMiddleware):
    """Comprehensive monitoring middleware"""
    
    def __init__(
        self,
        app: ASGIApp,
        metrics: PrometheusMetrics,
        tracing: TracingManager,
        alerting: AlertManager,
        logger: StructuredLogger
    ):
        super().__init__(app)
        self.metrics = metrics
        self.tracing = tracing
        self.alerting = alerting
        self.logger = logger
        
        # Request tracking
        self.active_requests = 0
        self.request_sizes: Dict[str, int] = {}
        
        self.logger.info("Monitoring middleware initialized")
    
    async def dispatch(self, request: Request, call_next):
        """Process request with comprehensive monitoring"""
        start_time = time.time()
        correlation_id = get_correlation_id()
        
        # Extract request information
        method = request.method
        path = self._get_route_path(request)
        request_size = self._get_request_size(request)
        
        # Update active requests counter
        self.active_requests += 1
        
        # Start tracing span
        span_attributes = {
            "http.method": method,
            "http.url": str(request.url),
            "http.route": path,
            "http.user_agent": request.headers.get("user-agent", ""),
            "correlation.id": correlation_id
        }
        
        async with self.tracing.trace_request(
            operation_name=f"{method} {path}",
            attributes=span_attributes
        ) as span:
            
            try:
                # Process request
                response = await call_next(request)
                
                # Calculate response time
                duration = time.time() - start_time
                status_code = response.status_code
                response_size = self._get_response_size(response)
                
                # Record metrics
                self.metrics.record_http_request(
                    method=method,
                    endpoint=path,
                    status_code=status_code,
                    duration=duration,
                    request_size=request_size,
                    response_size=response_size
                )
                
                # Update tracing span
                span.set_attribute("http.status_code", status_code)
                span.set_attribute("http.response_size", response_size or 0)
                
                # Add response headers for observability
                response.headers["X-Response-Time"] = f"{duration*1000:.2f}ms"
                response.headers["X-Trace-Id"] = span.get_span_context().trace_id if span.get_span_context() else ""
                
                # Log request completion
                self.logger.info("Request completed",
                               method=method,
                               path=path,
                               status_code=status_code,
                               duration_ms=duration * 1000,
                               request_size=request_size,
                               response_size=response_size,
                               correlation_id=correlation_id)
                
                # Check for alert conditions
                await self._check_alert_conditions(method, path, status_code, duration)
                
                return response
                
            except Exception as e:
                # Calculate error duration
                duration = time.time() - start_time
                
                # Record error metrics
                self.metrics.record_http_request(
                    method=method,
                    endpoint=path,
                    status_code=500,
                    duration=duration,
                    request_size=request_size
                )
                
                # Update span with error
                span.set_attribute("http.status_code", 500)
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                
                # Log error
                self.logger.error("Request failed",
                                method=method,
                                path=path,
                                duration_ms=duration * 1000,
                                error=str(e),
                                correlation_id=correlation_id)
                
                # Check for error alert conditions
                await self._check_alert_conditions(method, path, 500, duration, error=str(e))
                
                raise
                
            finally:
                # Update active requests counter
                self.active_requests -= 1
    
    def _get_route_path(self, request: Request) -> str:
        """Extract route path for consistent metrics"""
        # Try to get the matched route
        if hasattr(request, 'scope') and 'route' in request.scope:
            route = request.scope['route']
            if hasattr(route, 'path'):
                return route.path
        
        # Fallback to URL path with parameter normalization
        path = request.url.path
        
        # Normalize common patterns to reduce cardinality
        if path.startswith('/api/v1/'):
            # Keep API paths as-is for better monitoring
            return path
        elif path in ['/', '/health', '/metrics', '/docs', '/redoc']:
            return path
        else:
            # Group other paths to avoid high cardinality
            return '/other'
    
    def _get_request_size(self, request: Request) -> Optional[int]:
        """Get request content length"""
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                return int(content_length)
            except ValueError:
                pass
        return None
    
    def _get_response_size(self, response: Response) -> Optional[int]:
        """Get response content length"""
        content_length = response.headers.get("content-length")
        if content_length:
            try:
                return int(content_length)
            except ValueError:
                pass
        return None
    
    async def _check_alert_conditions(
        self,
        method: str,
        path: str,
        status_code: int,
        duration: float,
        error: Optional[str] = None
    ):
        """Check if request triggers any alert conditions"""
        
        # High response time alert
        if duration > 5.0:
            await self._trigger_response_time_alert(method, path, duration)
        
        # Error rate monitoring
        if status_code >= 500:
            await self._track_error_rate(method, path, status_code, error)
        
        # Rate limiting violations
        if status_code == 429:
            await self._track_rate_limit_violations(method, path)
    
    async def _trigger_response_time_alert(self, method: str, path: str, duration: float):
        """Trigger high response time alert"""
        try:
            # This would integrate with the alert manager
            # For now, we'll log the condition
            self.logger.warning("High response time detected",
                              method=method,
                              path=path,
                              duration_seconds=duration,
                              alert_condition=True)
            
            # Update metrics for alerting
            self.metrics.record_security_event("high_response_time", "medium")
            
        except Exception as e:
            self.logger.error("Error checking response time alert", error=str(e))
    
    async def _track_error_rate(self, method: str, path: str, status_code: int, error: Optional[str]):
        """Track error rate for alerting"""
        try:
            # Log error for alerting system
            self.logger.error("HTTP error detected",
                            method=method,
                            path=path,
                            status_code=status_code,
                            error=error,
                            alert_condition=True)
            
            # Update security metrics
            error_type = "server_error" if status_code >= 500 else "client_error"
            self.metrics.record_security_event(error_type, "high" if status_code >= 500 else "medium")
            
        except Exception as e:
            self.logger.error("Error tracking error rate", error=str(e))
    
    async def _track_rate_limit_violations(self, method: str, path: str):
        """Track rate limiting violations"""
        try:
            self.logger.warning("Rate limit violation detected",
                              method=method,
                              path=path,
                              alert_condition=True)
            
            # Update rate limit metrics
            self.metrics.record_rate_limit_check(allowed=False)
            self.metrics.record_security_event("rate_limit_violation", "medium")
            
        except Exception as e:
            self.logger.error("Error tracking rate limit violations", error=str(e))
    
    async def get_middleware_stats(self) -> Dict[str, Any]:
        """Get middleware statistics"""
        return {
            "active_requests": self.active_requests,
            "monitoring_components": {
                "metrics": "prometheus",
                "tracing": "opentelemetry", 
                "alerting": "custom",
                "logging": "structured"
            }
        }

class MetricsCollectionMiddleware(BaseHTTPMiddleware):
    """Lightweight metrics collection middleware for specific use cases"""
    
    def __init__(self, app: ASGIApp, metrics: PrometheusMetrics):
        super().__init__(app)
        self.metrics = metrics
        self.request_counter = 0
    
    async def dispatch(self, request: Request, call_next):
        """Collect basic metrics without full tracing overhead"""
        start_time = time.time()
        self.request_counter += 1
        
        method = request.method
        path = request.url.path
        
        try:
            response = await call_next(request)
            duration = time.time() - start_time
            
            # Record only essential metrics
            self.metrics.record_http_request(
                method=method,
                endpoint=path,
                status_code=response.status_code,
                duration=duration
            )
            
            return response
            
        except Exception:
            duration = time.time() - start_time
            self.metrics.record_http_request(
                method=method,
                endpoint=path,
                status_code=500,
                duration=duration
            )
            raise

class BusinessMetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for tracking business-specific metrics"""
    
    def __init__(self, app: ASGIApp, metrics: PrometheusMetrics, logger: StructuredLogger):
        super().__init__(app)
        self.metrics = metrics
        self.logger = logger
    
    async def dispatch(self, request: Request, call_next):
        """Track business metrics"""
        start_time = time.time()
        path = request.url.path
        
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Track business-specific metrics
        await self._track_business_metrics(request, response, duration)
        
        return response
    
    async def _track_business_metrics(self, request: Request, response: Response, duration: float):
        """Track business-specific metrics based on endpoints"""
        path = request.url.path
        method = request.method
        status_code = response.status_code
        
        try:
            # Code generation metrics
            if "/api/v1/generate/code" in path and method == "POST":
                framework = self._extract_framework_from_request(request)
                success = 200 <= status_code < 300
                self.metrics.record_code_generation(framework, duration, success)
                
                self.logger.info("Code generation tracked",
                               framework=framework,
                               duration_seconds=duration,
                               success=success)
            
            # Image generation metrics
            elif "/api/v1/generate/image" in path and method == "POST":
                success = 200 <= status_code < 300
                self.metrics.record_image_generation(duration, success)
                
                self.logger.info("Image generation tracked",
                               duration_seconds=duration,
                               success=success)
            
            # WebSocket connection metrics
            elif "/api/v1/ws" in path:
                # WebSocket metrics are handled separately
                pass
                
        except Exception as e:
            self.logger.error("Error tracking business metrics",
                            path=path,
                            error=str(e))
    
    def _extract_framework_from_request(self, request: Request) -> str:
        """Extract framework from request for code generation metrics"""
        try:
            # This would parse the request body to extract framework
            # For now, return a default
            return "react"
        except:
            return "unknown"

class HealthCheckMiddleware(BaseHTTPMiddleware):
    """Middleware for health check endpoint optimization"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.health_paths = {"/health", "/health/live", "/health/ready", "/health/detailed"}
    
    async def dispatch(self, request: Request, call_next):
        """Optimize health check requests"""
        if request.url.path in self.health_paths:
            # Skip heavy monitoring for health checks
            return await call_next(request)
        
        return await call_next(request)