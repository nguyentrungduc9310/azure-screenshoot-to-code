"""
OpenTelemetry Distributed Tracing
Advanced distributed tracing with spans, context propagation, and export
"""
import time
import os
from typing import Optional, Dict, Any, List, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
import asyncio

from opentelemetry import trace, baggage, context as otel_context
from opentelemetry.sdk.trace import TracerProvider, Span
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.asyncio import AsyncioInstrumentor
from opentelemetry.propagate import inject, extract
from opentelemetry.trace.status import Status, StatusCode
from opentelemetry.semconv.trace import SpanAttributes

from app.core.config import Settings
from shared.monitoring.structured_logger import StructuredLogger

@dataclass
class TraceConfig:
    """Tracing configuration"""
    service_name: str
    service_version: str = "1.0.0"
    environment: str = "development"
    jaeger_endpoint: Optional[str] = None
    otlp_endpoint: Optional[str] = None
    sample_rate: float = 1.0
    max_queue_size: int = 2048
    max_export_batch_size: int = 512
    export_timeout_millis: int = 30000
    enable_console_exporter: bool = False

@dataclass
class SpanContext:
    """Span context information"""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    baggage: Dict[str, str] = field(default_factory=dict)
    attributes: Dict[str, Any] = field(default_factory=dict)

class TracingManager:
    """OpenTelemetry distributed tracing manager"""
    
    def __init__(self, settings: Settings, logger: StructuredLogger):
        self.settings = settings
        self.logger = logger
        
        # Create trace configuration
        self.config = TraceConfig(
            service_name=settings.service_name,
            environment=settings.environment.value,
            jaeger_endpoint=getattr(settings, 'jaeger_endpoint', None),
            otlp_endpoint=getattr(settings, 'otlp_endpoint', None),
            sample_rate=getattr(settings, 'trace_sample_rate', 1.0),
            enable_console_exporter=settings.is_development
        )
        
        # Initialize tracing
        self.tracer_provider: Optional[TracerProvider] = None
        self.tracer: Optional[trace.Tracer] = None
        self._span_processors: List[BatchSpanProcessor] = []
        
        self._setup_tracing()
        self._setup_instrumentations()
        
        self.logger.info("OpenTelemetry tracing initialized",
                        service=self.config.service_name,
                        environment=self.config.environment,
                        sample_rate=self.config.sample_rate)
    
    def _setup_tracing(self):
        """Setup OpenTelemetry tracing infrastructure"""
        # Create resource
        resource = Resource.create({
            "service.name": self.config.service_name,
            "service.version": self.config.service_version,
            "service.instance.id": f"{self.settings.api_host}:{self.settings.api_port}",
            "deployment.environment": self.config.environment,
            "telemetry.sdk.name": "opentelemetry",
            "telemetry.sdk.language": "python",
            "telemetry.sdk.version": "1.20.0"
        })
        
        # Create tracer provider
        self.tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(self.tracer_provider)
        
        # Setup exporters
        self._setup_exporters()
        
        # Get tracer
        self.tracer = trace.get_tracer(
            instrumenting_module_name=self.config.service_name,
            instrumenting_library_version=self.config.service_version
        )
    
    def _setup_exporters(self):
        """Setup trace exporters"""
        exporters = []
        
        # Console exporter for development
        if self.config.enable_console_exporter:
            console_exporter = ConsoleSpanExporter()
            console_processor = BatchSpanProcessor(console_exporter)
            self.tracer_provider.add_span_processor(console_processor)
            self._span_processors.append(console_processor)
            exporters.append("console")
        
        # Jaeger exporter
        if self.config.jaeger_endpoint:
            try:
                jaeger_exporter = JaegerExporter(
                    agent_host_name=self.config.jaeger_endpoint.split(':')[0],
                    agent_port=int(self.config.jaeger_endpoint.split(':')[1]) if ':' in self.config.jaeger_endpoint else 14268,
                    collector_endpoint=f"http://{self.config.jaeger_endpoint}/api/traces",
                )
                jaeger_processor = BatchSpanProcessor(
                    jaeger_exporter,
                    max_queue_size=self.config.max_queue_size,
                    max_export_batch_size=self.config.max_export_batch_size,
                    export_timeout_millis=self.config.export_timeout_millis
                )
                self.tracer_provider.add_span_processor(jaeger_processor)
                self._span_processors.append(jaeger_processor)
                exporters.append("jaeger")
            except Exception as e:
                self.logger.warning("Failed to setup Jaeger exporter", error=str(e))
        
        # OTLP exporter
        if self.config.otlp_endpoint:
            try:
                otlp_exporter = OTLPSpanExporter(
                    endpoint=self.config.otlp_endpoint,
                    timeout=self.config.export_timeout_millis // 1000
                )
                otlp_processor = BatchSpanProcessor(
                    otlp_exporter,
                    max_queue_size=self.config.max_queue_size,
                    max_export_batch_size=self.config.max_export_batch_size,
                    export_timeout_millis=self.config.export_timeout_millis
                )
                self.tracer_provider.add_span_processor(otlp_processor)
                self._span_processors.append(otlp_processor)
                exporters.append("otlp")
            except Exception as e:
                self.logger.warning("Failed to setup OTLP exporter", error=str(e))
        
        self.logger.info("Trace exporters configured", exporters=exporters)
    
    def _setup_instrumentations(self):
        """Setup automatic instrumentation"""
        try:
            # FastAPI instrumentation
            FastAPIInstrumentor.instrument(
                tracer_provider=self.tracer_provider,
                excluded_urls="/health,/metrics,/docs,/redoc"
            )
            
            # HTTPX client instrumentation
            HTTPXClientInstrumentor().instrument(
                tracer_provider=self.tracer_provider
            )
            
            # Asyncio instrumentation
            AsyncioInstrumentor().instrument(
                tracer_provider=self.tracer_provider
            )
            
            self.logger.info("Auto-instrumentation enabled",
                           instrumentations=["fastapi", "httpx", "asyncio"])
            
        except Exception as e:
            self.logger.error("Failed to setup auto-instrumentation", error=str(e))
    
    def create_span(
        self,
        name: str,
        kind: trace.SpanKind = trace.SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None,
        parent: Optional[trace.Span] = None
    ) -> trace.Span:
        """Create a new span"""
        span = self.tracer.start_span(
            name=name,
            kind=kind,
            context=trace.set_span_in_context(parent) if parent else None
        )
        
        # Set standard attributes
        span.set_attribute(SpanAttributes.SERVICE_NAME, self.config.service_name)
        span.set_attribute(SpanAttributes.SERVICE_VERSION, self.config.service_version)
        span.set_attribute("environment", self.config.environment)
        
        # Set custom attributes
        if attributes:
            for key, value in attributes.items():
                if value is not None:
                    span.set_attribute(key, value)
        
        return span
    
    @asynccontextmanager
    async def trace_request(
        self,
        operation_name: str,
        span_kind: trace.SpanKind = trace.SpanKind.SERVER,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """Context manager for tracing requests"""
        span = self.create_span(
            name=operation_name,
            kind=span_kind,
            attributes=attributes
        )
        
        start_time = time.time()
        
        try:
            with trace.use_span(span):
                yield span
                
            # Mark as successful
            span.set_status(Status(StatusCode.OK))
            
        except Exception as e:
            # Record exception
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            raise
            
        finally:
            # Record duration
            duration = time.time() - start_time
            span.set_attribute("duration_ms", duration * 1000)
            span.end()
    
    @asynccontextmanager
    async def trace_downstream_call(
        self,
        service_name: str,
        operation: str,
        url: str,
        method: str = "GET",
        attributes: Optional[Dict[str, Any]] = None
    ):
        """Context manager for tracing downstream service calls"""
        span_attributes = {
            SpanAttributes.HTTP_METHOD: method,
            SpanAttributes.HTTP_URL: url,
            "service.name": service_name,
            "operation": operation,
            **(attributes or {})
        }
        
        span = self.create_span(
            name=f"{service_name}.{operation}",
            kind=trace.SpanKind.CLIENT,
            attributes=span_attributes
        )
        
        start_time = time.time()
        
        try:
            with trace.use_span(span):
                # Inject trace context for propagation
                headers = {}
                inject(headers)
                yield span, headers
                
            span.set_status(Status(StatusCode.OK))
            
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.set_attribute("error", True)
            raise
            
        finally:
            duration = time.time() - start_time
            span.set_attribute("duration_ms", duration * 1000)
            span.end()
    
    def add_span_event(
        self,
        span: trace.Span,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
        timestamp: Optional[int] = None
    ):
        """Add event to current span"""
        span.add_event(
            name=name,
            attributes=attributes or {},
            timestamp=timestamp
        )
    
    def set_span_attribute(self, span: trace.Span, key: str, value: Any):
        """Set attribute on span"""
        if value is not None:
            span.set_attribute(key, value)
    
    def set_baggage(self, key: str, value: str):
        """Set baggage item"""
        ctx = baggage.set_baggage(key, value)
        otel_context.attach(ctx)
    
    def get_baggage(self, key: str) -> Optional[str]:
        """Get baggage item"""
        return baggage.get_baggage(key)
    
    def get_current_span_context(self) -> Optional[SpanContext]:
        """Get current span context"""
        current_span = trace.get_current_span()
        if not current_span or not current_span.is_recording():
            return None
        
        span_context = current_span.get_span_context()
        return SpanContext(
            trace_id=f"{span_context.trace_id:032x}",
            span_id=f"{span_context.span_id:016x}",
            baggage={k: v for k, v in baggage.get_all().items()},
            attributes={}
        )
    
    def inject_context(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Inject trace context into headers"""
        inject(headers)
        return headers
    
    def extract_context(self, headers: Dict[str, str]):
        """Extract trace context from headers"""
        ctx = extract(headers)
        otel_context.attach(ctx)
    
    async def flush_spans(self, timeout_seconds: float = 30.0):
        """Flush all pending spans"""
        tasks = []
        for processor in self._span_processors:
            if hasattr(processor, 'force_flush'):
                tasks.append(processor.force_flush(timeout_millis=int(timeout_seconds * 1000)))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def shutdown(self):
        """Shutdown tracing system"""
        try:
            # Flush pending spans
            await self.flush_spans()
            
            # Shutdown processors
            for processor in self._span_processors:
                if hasattr(processor, 'shutdown'):
                    processor.shutdown()
            
            self.logger.info("OpenTelemetry tracing shutdown completed")
            
        except Exception as e:
            self.logger.error("Error during tracing shutdown", error=str(e))

# Decorators for easy tracing
def trace_function(operation_name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None):
    """Decorator to trace function calls"""
    def decorator(func: Callable):
        async def async_wrapper(*args, **kwargs):
            # Get tracing manager from context or create minimal tracer
            tracer = trace.get_tracer(__name__)
            span_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            with tracer.start_as_current_span(span_name) as span:
                # Set attributes
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)
                
                # Set function attributes
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)
                
                try:
                    if asyncio.iscoroutinefunction(func):
                        result = await func(*args, **kwargs)
                    else:
                        result = func(*args, **kwargs)
                    
                    span.set_status(Status(StatusCode.OK))
                    return result
                    
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
        
        def sync_wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            span_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            with tracer.start_as_current_span(span_name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)
                
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)
                
                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

def trace_class(class_name: Optional[str] = None):
    """Decorator to trace all methods of a class"""
    def decorator(cls):
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if callable(attr) and not attr_name.startswith('_'):
                traced_attr = trace_function(
                    operation_name=f"{class_name or cls.__name__}.{attr_name}"
                )(attr)
                setattr(cls, attr_name, traced_attr)
        return cls
    return decorator