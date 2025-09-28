"""
Prometheus Metrics Collector
Advanced metrics collection and export for monitoring and observability
"""
import time
from typing import Dict, List, Optional, Any, Counter as CounterType
from dataclasses import dataclass, field
from enum import Enum
import asyncio
from collections import defaultdict, Counter

from prometheus_client import (
    Counter, Histogram, Gauge, Info, Enum as PrometheusEnum,
    CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
)

from app.core.config import Settings
from shared.monitoring.structured_logger import StructuredLogger

class MetricType(str, Enum):
    COUNTER = "counter"
    HISTOGRAM = "histogram"
    GAUGE = "gauge"
    INFO = "info"
    ENUM = "enum"

@dataclass
class MetricLabels:
    """Standard metric labels"""
    service: str
    environment: str
    version: str = "1.0.0"
    instance: str = "default"
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "service": self.service,
            "environment": self.environment,
            "version": self.version,
            "instance": self.instance
        }

@dataclass
class RequestMetrics:
    """Request-specific metrics tracking"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    response_times: List[float] = field(default_factory=list)
    error_counts: CounterType = field(default_factory=Counter)
    
    def add_request(self, success: bool, response_time: float, error_type: Optional[str] = None):
        self.total_requests += 1
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
            if error_type:
                self.error_counts[error_type] += 1
        self.response_times.append(response_time)

class PrometheusMetrics:
    """Comprehensive Prometheus metrics collector"""
    
    def __init__(self, settings: Settings, logger: StructuredLogger):
        self.settings = settings
        self.logger = logger
        
        # Create custom registry
        self.registry = CollectorRegistry()
        
        # Standard labels
        self.base_labels = MetricLabels(
            service=settings.service_name,
            environment=settings.environment.value,
            instance=f"{settings.api_host}:{settings.api_port}"
        )
        
        # Initialize core metrics
        self._init_core_metrics()
        self._init_business_metrics()
        self._init_infrastructure_metrics()
        self._init_security_metrics()
        
        # Metrics storage
        self.request_metrics: Dict[str, RequestMetrics] = defaultdict(RequestMetrics)
        
        self.logger.info("Prometheus metrics initialized",
                        registry_collectors=len(self.registry._collector_to_names))
    
    def _init_core_metrics(self):
        """Initialize core application metrics"""
        base_labels = list(self.base_labels.to_dict().keys())
        
        # HTTP Request metrics
        self.http_requests_total = Counter(
            'http_requests_total',
            'Total HTTP requests',
            labelnames=base_labels + ['method', 'endpoint', 'status_code'],
            registry=self.registry
        )
        
        self.http_request_duration_seconds = Histogram(
            'http_request_duration_seconds',
            'HTTP request duration in seconds',
            labelnames=base_labels + ['method', 'endpoint', 'status_code'],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            registry=self.registry
        )
        
        self.http_request_size_bytes = Histogram(
            'http_request_size_bytes',
            'HTTP request size in bytes',
            labelnames=base_labels + ['method', 'endpoint'],
            buckets=[100, 500, 1000, 5000, 10000, 50000, 100000],
            registry=self.registry
        )
        
        self.http_response_size_bytes = Histogram(
            'http_response_size_bytes',
            'HTTP response size in bytes',
            labelnames=base_labels + ['method', 'endpoint', 'status_code'],
            buckets=[100, 500, 1000, 5000, 10000, 50000, 100000, 500000],
            registry=self.registry
        )
        
        # Application info
        self.app_info = Info(
            'app_info',
            'Application information',
            registry=self.registry
        )
        self.app_info.info({
            'version': self.base_labels.version,
            'service': self.base_labels.service,
            'environment': self.base_labels.environment
        })
        
        # Application uptime
        self.app_start_time = Gauge(
            'app_start_time_seconds',
            'Application start time in seconds since epoch',
            labelnames=base_labels,
            registry=self.registry
        )
        self.app_start_time.labels(**self.base_labels.to_dict()).set(time.time())
    
    def _init_business_metrics(self):
        """Initialize business-specific metrics"""
        base_labels = list(self.base_labels.to_dict().keys())
        
        # Code generation metrics
        self.code_generations_total = Counter(
            'code_generations_total',
            'Total code generations',
            labelnames=base_labels + ['framework', 'status'],
            registry=self.registry
        )
        
        self.code_generation_duration_seconds = Histogram(
            'code_generation_duration_seconds',
            'Code generation duration in seconds',
            labelnames=base_labels + ['framework', 'status'],
            buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
            registry=self.registry
        )
        
        # Image generation metrics
        self.image_generations_total = Counter(
            'image_generations_total',
            'Total image generations',
            labelnames=base_labels + ['status'],
            registry=self.registry
        )
        
        self.image_generation_duration_seconds = Histogram(
            'image_generation_duration_seconds',
            'Image generation duration in seconds',
            labelnames=base_labels + ['status'],
            buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 60.0],
            registry=self.registry
        )
        
        # WebSocket metrics
        self.websocket_connections_total = Counter(
            'websocket_connections_total',
            'Total WebSocket connections',
            labelnames=base_labels + ['status'],
            registry=self.registry
        )
        
        self.websocket_messages_total = Counter(
            'websocket_messages_total',
            'Total WebSocket messages',
            labelnames=base_labels + ['direction', 'message_type'],
            registry=self.registry
        )
        
        self.websocket_connections_active = Gauge(
            'websocket_connections_active',
            'Active WebSocket connections',
            labelnames=base_labels,
            registry=self.registry
        )
    
    def _init_infrastructure_metrics(self):
        """Initialize infrastructure metrics"""
        base_labels = list(self.base_labels.to_dict().keys())
        
        # Circuit breaker metrics
        self.circuit_breaker_requests_total = Counter(
            'circuit_breaker_requests_total',
            'Total circuit breaker requests',
            labelnames=base_labels + ['service_name', 'state', 'outcome'],
            registry=self.registry
        )
        
        self.circuit_breaker_state = PrometheusEnum(
            'circuit_breaker_state',
            'Circuit breaker state',
            labelnames=base_labels + ['service_name'],
            states=['closed', 'open', 'half_open'],
            registry=self.registry
        )
        
        self.circuit_breaker_failure_rate = Gauge(
            'circuit_breaker_failure_rate',
            'Circuit breaker failure rate',
            labelnames=base_labels + ['service_name'],
            registry=self.registry
        )
        
        # Service discovery metrics
        self.service_instances_total = Gauge(
            'service_instances_total',
            'Total service instances',
            labelnames=base_labels + ['service_name', 'health_status'],
            registry=self.registry
        )
        
        self.service_health_checks_total = Counter(
            'service_health_checks_total',
            'Total service health checks',
            labelnames=base_labels + ['service_name', 'result'],
            registry=self.registry
        )
        
        # Connection pool metrics
        self.connection_pool_connections_active = Gauge(
            'connection_pool_connections_active',
            'Active connections in pool',
            labelnames=base_labels + ['service_name'],
            registry=self.registry
        )
        
        self.connection_pool_connections_idle = Gauge(
            'connection_pool_connections_idle',
            'Idle connections in pool',
            labelnames=base_labels + ['service_name'],
            registry=self.registry
        )
        
        self.connection_pool_requests_total = Counter(
            'connection_pool_requests_total',
            'Total connection pool requests',
            labelnames=base_labels + ['service_name', 'result'],
            registry=self.registry
        )
    
    def _init_security_metrics(self):
        """Initialize security metrics"""
        base_labels = list(self.base_labels.to_dict().keys())
        
        # Authentication metrics
        self.auth_attempts_total = Counter(
            'auth_attempts_total',
            'Total authentication attempts',
            labelnames=base_labels + ['result', 'method'],
            registry=self.registry
        )
        
        self.auth_token_validations_total = Counter(
            'auth_token_validations_total',
            'Total token validations',
            labelnames=base_labels + ['result'],
            registry=self.registry
        )
        
        # Rate limiting metrics
        self.rate_limit_requests_total = Counter(
            'rate_limit_requests_total',
            'Total rate limit checks',
            labelnames=base_labels + ['result'],
            registry=self.registry
        )
        
        self.rate_limit_violations_total = Counter(
            'rate_limit_violations_total',
            'Total rate limit violations',
            labelnames=base_labels + ['client_id'],
            registry=self.registry
        )
        
        # Security events
        self.security_events_total = Counter(
            'security_events_total',
            'Total security events',
            labelnames=base_labels + ['event_type', 'severity'],
            registry=self.registry
        )
    
    # HTTP Metrics Methods
    def record_http_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration: float,
        request_size: Optional[int] = None,
        response_size: Optional[int] = None
    ):
        """Record HTTP request metrics"""
        labels = {
            **self.base_labels.to_dict(),
            'method': method,
            'endpoint': endpoint,
            'status_code': str(status_code)
        }
        
        # Record request count
        self.http_requests_total.labels(**labels).inc()
        
        # Record duration
        self.http_request_duration_seconds.labels(**labels).observe(duration)
        
        # Record request size
        if request_size is not None:
            request_labels = {k: v for k, v in labels.items() if k != 'status_code'}
            self.http_request_size_bytes.labels(**request_labels).observe(request_size)
        
        # Record response size
        if response_size is not None:
            self.http_response_size_bytes.labels(**labels).observe(response_size)
    
    # Business Metrics Methods
    def record_code_generation(
        self,
        framework: str,
        duration: float,
        success: bool
    ):
        """Record code generation metrics"""
        status = "success" if success else "failure"
        labels = {
            **self.base_labels.to_dict(),
            'framework': framework,
            'status': status
        }
        
        self.code_generations_total.labels(**labels).inc()
        self.code_generation_duration_seconds.labels(**labels).observe(duration)
    
    def record_image_generation(
        self,
        duration: float,
        success: bool
    ):
        """Record image generation metrics"""
        status = "success" if success else "failure"
        labels = {
            **self.base_labels.to_dict(),
            'status': status
        }
        
        self.image_generations_total.labels(**labels).inc()
        self.image_generation_duration_seconds.labels(**labels).observe(duration)
    
    def record_websocket_connection(self, connected: bool):
        """Record WebSocket connection event"""
        status = "connected" if connected else "disconnected"
        labels = {
            **self.base_labels.to_dict(),
            'status': status
        }
        
        self.websocket_connections_total.labels(**labels).inc()
        
        # Update active connections gauge
        if connected:
            self.websocket_connections_active.labels(**self.base_labels.to_dict()).inc()
        else:
            self.websocket_connections_active.labels(**self.base_labels.to_dict()).dec()
    
    def record_websocket_message(self, direction: str, message_type: str):
        """Record WebSocket message"""
        labels = {
            **self.base_labels.to_dict(),
            'direction': direction,
            'message_type': message_type
        }
        
        self.websocket_messages_total.labels(**labels).inc()
    
    # Infrastructure Metrics Methods
    def record_circuit_breaker_request(
        self,
        service_name: str,
        state: str,
        outcome: str
    ):
        """Record circuit breaker request"""
        labels = {
            **self.base_labels.to_dict(),
            'service_name': service_name,
            'state': state,
            'outcome': outcome
        }
        
        self.circuit_breaker_requests_total.labels(**labels).inc()
    
    def update_circuit_breaker_state(self, service_name: str, state: str):
        """Update circuit breaker state"""
        labels = {
            **self.base_labels.to_dict(),
            'service_name': service_name
        }
        
        self.circuit_breaker_state.labels(**labels).state(state)
    
    def update_circuit_breaker_failure_rate(self, service_name: str, failure_rate: float):
        """Update circuit breaker failure rate"""
        labels = {
            **self.base_labels.to_dict(),
            'service_name': service_name
        }
        
        self.circuit_breaker_failure_rate.labels(**labels).set(failure_rate)
    
    def update_service_instances(self, service_name: str, health_status: str, count: int):
        """Update service instance count"""
        labels = {
            **self.base_labels.to_dict(),
            'service_name': service_name,
            'health_status': health_status
        }
        
        self.service_instances_total.labels(**labels).set(count)
    
    def record_health_check(self, service_name: str, success: bool):
        """Record service health check"""
        result = "success" if success else "failure"
        labels = {
            **self.base_labels.to_dict(),
            'service_name': service_name,
            'result': result
        }
        
        self.service_health_checks_total.labels(**labels).inc()
    
    # Security Metrics Methods
    def record_auth_attempt(self, success: bool, method: str):
        """Record authentication attempt"""
        result = "success" if success else "failure"
        labels = {
            **self.base_labels.to_dict(),
            'result': result,
            'method': method
        }
        
        self.auth_attempts_total.labels(**labels).inc()
    
    def record_rate_limit_check(self, allowed: bool, client_id: Optional[str] = None):
        """Record rate limit check"""
        result = "allowed" if allowed else "denied"
        labels = {
            **self.base_labels.to_dict(),
            'result': result
        }
        
        self.rate_limit_requests_total.labels(**labels).inc()
        
        if not allowed and client_id:
            violation_labels = {
                **self.base_labels.to_dict(),
                'client_id': client_id
            }
            self.rate_limit_violations_total.labels(**violation_labels).inc()
    
    def record_security_event(self, event_type: str, severity: str):
        """Record security event"""
        labels = {
            **self.base_labels.to_dict(),
            'event_type': event_type,
            'severity': severity
        }
        
        self.security_events_total.labels(**labels).inc()
    
    # Export Methods
    def get_metrics(self) -> str:
        """Get metrics in Prometheus format"""
        return generate_latest(self.registry).decode('utf-8')
    
    def get_content_type(self) -> str:
        """Get content type for metrics endpoint"""
        return CONTENT_TYPE_LATEST
    
    async def collect_runtime_metrics(self):
        """Collect runtime metrics periodically"""
        try:
            import psutil
            import gc
            
            # Memory metrics
            memory_info = psutil.virtual_memory()
            self._update_system_metric('memory_usage_percent', memory_info.percent)
            self._update_system_metric('memory_available_bytes', memory_info.available)
            
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            self._update_system_metric('cpu_usage_percent', cpu_percent)
            
            # Garbage collection metrics
            gc_stats = gc.get_stats()
            for i, stats in enumerate(gc_stats):
                self._update_system_metric(f'gc_collections_generation_{i}', stats['collections'])
                self._update_system_metric(f'gc_collected_generation_{i}', stats['collected'])
            
        except ImportError:
            self.logger.warning("psutil not available, skipping system metrics")
        except Exception as e:
            self.logger.error("Failed to collect runtime metrics", error=str(e))
    
    def _update_system_metric(self, metric_name: str, value: float):
        """Update system metric (creates gauge if not exists)"""
        if not hasattr(self, f'_system_{metric_name}'):
            gauge = Gauge(
                f'system_{metric_name}',
                f'System metric: {metric_name}',
                labelnames=list(self.base_labels.to_dict().keys()),
                registry=self.registry
            )
            setattr(self, f'_system_{metric_name}', gauge)
        
        gauge = getattr(self, f'_system_{metric_name}')
        gauge.labels(**self.base_labels.to_dict()).set(value)
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics"""
        total_requests = sum(rm.total_requests for rm in self.request_metrics.values())
        total_success = sum(rm.successful_requests for rm in self.request_metrics.values())
        total_failures = sum(rm.failed_requests for rm in self.request_metrics.values())
        
        return {
            "total_requests": total_requests,
            "successful_requests": total_success,
            "failed_requests": total_failures,
            "success_rate": total_success / max(total_requests, 1),
            "metrics_collected": len(self.registry._collector_to_names),
            "uptime_seconds": time.time() - self.app_start_time.labels(**self.base_labels.to_dict())._value._value
        }