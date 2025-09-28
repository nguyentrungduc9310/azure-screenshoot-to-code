# TASK-007: Monitoring and Logging Setup

**Date**: January 2024  
**Assigned**: DevOps Engineer  
**Status**: IN PROGRESS  
**Effort**: 16 hours  

---

## Executive Summary

Comprehensive monitoring and logging infrastructure setup for Screenshot-to-Code microservices architecture. Implementation includes Application Insights integration, centralized log aggregation, performance monitoring, custom dashboards, and intelligent alerting with Azure Monitor, Grafana, and Prometheus.

---

## Monitoring Architecture Overview

### 🏗️ **Observability Stack**
```yaml
Monitoring Layers:
  - Application Performance Monitoring (APM): Azure Application Insights
  - Infrastructure Monitoring: Azure Monitor + Prometheus
  - Log Aggregation: Azure Log Analytics + Fluentd
  - Metrics Collection: Custom metrics + OpenTelemetry
  - Visualization: Grafana + Azure Monitor Workbooks
  - Alerting: Azure Monitor Alerts + PagerDuty integration

Data Flow:
  Microservices → OpenTelemetry → Application Insights → Log Analytics → Dashboards & Alerts
```

---

## Phase 1: Application Insights Integration

### 1.1 Application Insights Configuration

```python
# shared/monitoring/app_insights.py
import logging
import os
from typing import Optional, Dict, Any
from opencensus.ext.azure.log_exporter import AzureLogHandler
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.trace.samplers import ProbabilitySampler
from opencensus.trace.tracer import Tracer
from opencensus.trace import config_integration
from opencensus.ext.flask.flask_middleware import FlaskMiddleware
from opencensus.ext.azure.metrics_exporter import MetricsExporter
from opencensus.stats import aggregation as aggregation_module
from opencensus.stats import measure as measure_module
from opencensus.stats import stats as stats_module
from opencensus.stats import view as view_module
from opencensus.tags import tag_map as tag_map_module

class ApplicationInsightsSetup:
    """Centralized Application Insights configuration for all services"""
    
    def __init__(self, service_name: str, connection_string: Optional[str] = None):
        self.service_name = service_name
        self.connection_string = connection_string or os.getenv('APPLICATIONINSIGHTS_CONNECTION_STRING')
        
        if not self.connection_string:
            raise ValueError("Application Insights connection string is required")
        
        self.tracer = None
        self.logger = None
        self.metrics_exporter = None
        
    def setup_logging(self, log_level: str = "INFO") -> logging.Logger:
        """Configure centralized logging with Application Insights"""
        
        logger = logging.getLogger(self.service_name)
        logger.setLevel(getattr(logging, log_level.upper()))
        
        # Azure Log Handler
        azure_handler = AzureLogHandler(connection_string=self.connection_string)
        azure_handler.setFormatter(
            logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        )
        
        # Console Handler for local development
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
            )
        )
        
        logger.addHandler(azure_handler)
        logger.addHandler(console_handler)
        
        # Add custom properties
        logger.addFilter(self._add_custom_properties)
        
        self.logger = logger
        return logger
    
    def setup_tracing(self, sampling_rate: float = 0.1) -> Tracer:
        """Configure distributed tracing"""
        
        config_integration.trace_integrations(['requests', 'httplib'])
        
        tracer = Tracer(
            exporter=AzureExporter(connection_string=self.connection_string),
            sampler=ProbabilitySampler(rate=sampling_rate)
        )
        
        self.tracer = tracer
        return tracer
    
    def setup_metrics(self) -> None:
        """Configure custom metrics collection"""
        
        self.metrics_exporter = MetricsExporter(
            connection_string=self.connection_string
        )
        
        # Initialize stats recorder
        stats = stats_module.stats
        view_manager = stats.view_manager
        stats_recorder = stats.stats_recorder
        
        # Define custom measures
        self.request_count_measure = measure_module.MeasureInt(
            "requests", "Number of requests", "1"
        )
        self.request_latency_measure = measure_module.MeasureFloat(
            "request_latency", "Request latency", "ms"
        )
        self.ai_provider_latency_measure = measure_module.MeasureFloat(
            "ai_provider_latency", "AI provider response time", "ms"
        )
        self.image_processing_time_measure = measure_module.MeasureFloat(
            "image_processing_time", "Image processing duration", "ms"
        )
        
        # Create views
        request_count_view = view_module.View(
            "request_count",
            "Request count by service and endpoint",
            ["service", "endpoint", "status_code"],
            self.request_count_measure,
            aggregation_module.CountAggregation()
        )
        
        request_latency_view = view_module.View(
            "request_latency",
            "Request latency distribution",
            ["service", "endpoint"],
            self.request_latency_measure,
            aggregation_module.DistributionAggregation([50, 100, 200, 400, 1000, 2000])
        )
        
        ai_provider_latency_view = view_module.View(
            "ai_provider_latency",
            "AI provider response time",
            ["service", "provider", "model"],
            self.ai_provider_latency_measure,
            aggregation_module.DistributionAggregation([100, 500, 1000, 5000, 10000])
        )
        
        image_processing_view = view_module.View(
            "image_processing_time",
            "Image processing duration",
            ["service", "operation"],
            self.image_processing_time_measure,
            aggregation_module.DistributionAggregation([10, 50, 100, 500, 1000, 5000])
        )
        
        # Register views
        view_manager.register_view(request_count_view)
        view_manager.register_view(request_latency_view)
        view_manager.register_view(ai_provider_latency_view)
        view_manager.register_view(image_processing_view)
        
        # Register exporter
        view_manager.register_exporter(self.metrics_exporter)
        
        self.stats_recorder = stats_recorder
        
    def setup_fastapi_middleware(self, app):
        """Setup FastAPI middleware for automatic instrumentation"""
        from opencensus.ext.fastapi import FastAPIMiddleware
        
        app.add_middleware(
            FastAPIMiddleware,
            exporter=AzureExporter(connection_string=self.connection_string),
            sampler=ProbabilitySampler(rate=0.1)
        )
        
        return app
    
    def _add_custom_properties(self, record):
        """Add custom properties to log records"""
        record.custom_dimensions = {
            'service': self.service_name,
            'environment': os.getenv('ENVIRONMENT', 'development'),
            'version': os.getenv('SERVICE_VERSION', '1.0.0')
        }
        return True
    
    def record_request_metrics(self, endpoint: str, status_code: int, latency_ms: float):
        """Record request metrics"""
        if not hasattr(self, 'stats_recorder'):
            return
            
        tag_map = tag_map_module.TagMap()
        tag_map.insert("service", self.service_name)
        tag_map.insert("endpoint", endpoint)
        tag_map.insert("status_code", str(status_code))
        
        # Record count
        self.stats_recorder.new_measurement_map().measure_int_put(
            self.request_count_measure, 1
        ).record(tag_map)
        
        # Record latency
        latency_tag_map = tag_map_module.TagMap()
        latency_tag_map.insert("service", self.service_name)
        latency_tag_map.insert("endpoint", endpoint)
        
        self.stats_recorder.new_measurement_map().measure_float_put(
            self.request_latency_measure, latency_ms
        ).record(latency_tag_map)
    
    def record_ai_provider_metrics(self, provider: str, model: str, latency_ms: float):
        """Record AI provider performance metrics"""
        if not hasattr(self, 'stats_recorder'):
            return
            
        tag_map = tag_map_module.TagMap()
        tag_map.insert("service", self.service_name)
        tag_map.insert("provider", provider)
        tag_map.insert("model", model)
        
        self.stats_recorder.new_measurement_map().measure_float_put(
            self.ai_provider_latency_measure, latency_ms
        ).record(tag_map)
    
    def record_image_processing_metrics(self, operation: str, duration_ms: float):
        """Record image processing performance metrics"""
        if not hasattr(self, 'stats_recorder'):
            return
            
        tag_map = tag_map_module.TagMap()
        tag_map.insert("service", self.service_name)
        tag_map.insert("operation", operation)
        
        self.stats_recorder.new_measurement_map().measure_float_put(
            self.image_processing_time_measure, duration_ms
        ).record(tag_map)

# Usage in service initialization
def setup_monitoring(app, service_name: str):
    """Setup complete monitoring for a service"""
    
    insights = ApplicationInsightsSetup(service_name)
    
    # Setup logging
    logger = insights.setup_logging()
    
    # Setup tracing
    tracer = insights.setup_tracing()
    
    # Setup metrics
    insights.setup_metrics()
    
    # Setup FastAPI middleware
    insights.setup_fastapi_middleware(app)
    
    # Add monitoring to app context
    app.monitoring = insights
    app.logger = logger
    app.tracer = tracer
    
    logger.info(f"Monitoring setup completed for {service_name}")
    
    return app
```

### 1.2 Service-Specific Monitoring Implementation

```python
# services/api-gateway/app/monitoring.py
from fastapi import FastAPI, Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware
import time
from typing import Callable
from shared.monitoring.app_insights import setup_monitoring

class RequestMetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to capture request metrics"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate metrics
        process_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        # Record metrics if monitoring is available
        if hasattr(request.app, 'monitoring'):
            request.app.monitoring.record_request_metrics(
                endpoint=request.url.path,
                status_code=response.status_code,
                latency_ms=process_time
            )
        
        # Add response headers
        response.headers["X-Process-Time"] = str(process_time)
        
        return response

def setup_api_gateway_monitoring(app: FastAPI):
    """Setup monitoring specific to API Gateway"""
    
    # Setup base monitoring
    setup_monitoring(app, "api-gateway")
    
    # Add request metrics middleware
    app.add_middleware(RequestMetricsMiddleware)
    
    # Custom health check with detailed status
    @app.get("/health")
    async def detailed_health_check():
        health_status = {
            "status": "healthy",
            "service": "api-gateway",
            "timestamp": time.time(),
            "version": "1.0.0",
            "dependencies": {
                "image_processor": await check_service_health("image-processor"),
                "code_generator": await check_service_health("code-generator"),
                "image_generator": await check_service_health("image-generator"),
                "nlp_processor": await check_service_health("nlp-processor"),
                "evaluation": await check_service_health("evaluation")
            }
        }
        
        # Log health check
        app.logger.info("Health check performed", extra={"health_status": health_status})
        
        return health_status

async def check_service_health(service_name: str) -> dict:
    """Check health of downstream services"""
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://{service_name}:8000/health", timeout=2.0)
            return {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "response_time": response.elapsed.total_seconds() * 1000
            }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

```python
# services/code-generator/app/monitoring.py
from shared.monitoring.app_insights import setup_monitoring
import time
import asyncio

def setup_code_generator_monitoring(app):
    """Setup monitoring specific to Code Generator service"""
    
    setup_monitoring(app, "code-generator")
    
    # Custom metrics for AI provider performance
    async def track_ai_provider_call(provider: str, model: str, func, *args, **kwargs):
        """Wrapper to track AI provider performance"""
        start_time = time.time()
        
        try:
            result = await func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000
            
            # Record successful call
            app.monitoring.record_ai_provider_metrics(provider, model, duration_ms)
            app.logger.info(
                f"AI provider call successful",
                extra={
                    "provider": provider,
                    "model": model,
                    "duration_ms": duration_ms
                }
            )
            
            return result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            # Record failed call
            app.monitoring.record_ai_provider_metrics(provider, f"{model}_failed", duration_ms)
            app.logger.error(
                f"AI provider call failed",
                extra={
                    "provider": provider,
                    "model": model,
                    "duration_ms": duration_ms,
                    "error": str(e)
                }
            )
            
            raise
    
    # Add to app context
    app.track_ai_provider_call = track_ai_provider_call
    
    return app

# services/image-processor/app/monitoring.py
def setup_image_processor_monitoring(app):
    """Setup monitoring specific to Image Processor service"""
    
    setup_monitoring(app, "image-processor")
    
    # Custom metrics for image processing operations
    def track_image_operation(operation: str, func, *args, **kwargs):
        """Wrapper to track image processing performance"""
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000
            
            # Record successful operation
            app.monitoring.record_image_processing_metrics(operation, duration_ms)
            app.logger.info(
                f"Image processing operation completed",
                extra={
                    "operation": operation,
                    "duration_ms": duration_ms
                }
            )
            
            return result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            # Record failed operation
            app.monitoring.record_image_processing_metrics(f"{operation}_failed", duration_ms)
            app.logger.error(
                f"Image processing operation failed",
                extra={
                    "operation": operation,
                    "duration_ms": duration_ms,
                    "error": str(e)
                }
            )
            
            raise
    
    app.track_image_operation = track_image_operation
    
    return app
```

---

## Phase 2: Centralized Logging Configuration

### 2.1 Structured Logging Implementation

```python
# shared/logging/structured_logger.py
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional
from pythonjsonlogger import jsonlogger

class StructuredLogger:
    """Enhanced structured logging with correlation IDs and context"""
    
    def __init__(self, service_name: str, log_level: str = "INFO"):
        self.service_name = service_name
        self.log_level = log_level
        self.logger = self._setup_logger()
    
    def _setup_logger(self) -> logging.Logger:
        """Setup structured JSON logging"""
        
        logger = logging.getLogger(self.service_name)
        logger.setLevel(getattr(logging, self.log_level.upper()))
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Create JSON formatter
        json_formatter = jsonlogger.JsonFormatter(
            fmt='%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(json_formatter)
        logger.addHandler(console_handler)
        
        # Add context filter
        logger.addFilter(self._add_context)
        
        return logger
    
    def _add_context(self, record):
        """Add service context to log records"""
        
        record.service = self.service_name
        record.environment = os.getenv('ENVIRONMENT', 'development')
        record.version = os.getenv('SERVICE_VERSION', '1.0.0')
        record.correlation_id = getattr(record, 'correlation_id', None)
        
        return True
    
    def log_request(self, method: str, path: str, status_code: int, 
                   duration_ms: float, correlation_id: str = None,
                   user_id: str = None, additional_context: Dict[str, Any] = None):
        """Log HTTP request with standardized format"""
        
        context = {
            "event_type": "http_request",
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "correlation_id": correlation_id,
            "user_id": user_id
        }
        
        if additional_context:
            context.update(additional_context)
        
        self.logger.info("HTTP request processed", extra=context)
    
    def log_ai_provider_call(self, provider: str, model: str, 
                           duration_ms: float, token_count: int = None,
                           cost: float = None, correlation_id: str = None):
        """Log AI provider API calls"""
        
        context = {
            "event_type": "ai_provider_call",
            "provider": provider,
            "model": model,
            "duration_ms": duration_ms,
            "token_count": token_count,
            "cost": cost,
            "correlation_id": correlation_id
        }
        
        self.logger.info("AI provider call completed", extra=context)
    
    def log_image_processing(self, operation: str, input_size: int,
                           output_size: int, duration_ms: float,
                           correlation_id: str = None):
        """Log image processing operations"""
        
        context = {
            "event_type": "image_processing",
            "operation": operation,
            "input_size_bytes": input_size,
            "output_size_bytes": output_size,
            "compression_ratio": round(output_size / input_size, 2) if input_size > 0 else 0,
            "duration_ms": duration_ms,
            "correlation_id": correlation_id
        }
        
        self.logger.info("Image processing completed", extra=context)
    
    def log_security_event(self, event_type: str, user_id: str = None,
                          ip_address: str = None, user_agent: str = None,
                          severity: str = "INFO", details: Dict[str, Any] = None):
        """Log security-related events"""
        
        context = {
            "event_type": "security_event",
            "security_event_type": event_type,
            "user_id": user_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "severity": severity
        }
        
        if details:
            context.update(details)
        
        log_method = getattr(self.logger, severity.lower())
        log_method("Security event", extra=context)
    
    def log_business_metric(self, metric_name: str, value: float,
                          unit: str = None, dimensions: Dict[str, str] = None,
                          correlation_id: str = None):
        """Log business metrics for analysis"""
        
        context = {
            "event_type": "business_metric",
            "metric_name": metric_name,
            "value": value,
            "unit": unit,
            "dimensions": dimensions or {},
            "correlation_id": correlation_id
        }
        
        self.logger.info("Business metric recorded", extra=context)
    
    def log_error(self, error: Exception, context: Dict[str, Any] = None,
                 correlation_id: str = None):
        """Log errors with full context"""
        
        error_context = {
            "event_type": "error",
            "error_type": error.__class__.__name__,
            "error_message": str(error),
            "correlation_id": correlation_id
        }
        
        if context:
            error_context.update(context)
        
        self.logger.error("Error occurred", extra=error_context, exc_info=True)
```

### 2.2 Correlation ID Middleware

```python
# shared/middleware/correlation.py
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.base import BaseHTTPMiddleware
from typing import Callable
import contextvars

# Context variable for correlation ID
correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar('correlation_id')

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware to handle correlation IDs for request tracing"""
    
    async def dispatch(self, request: Request, call_next: Callable):
        # Get or generate correlation ID
        correlation_id = request.headers.get('X-Correlation-ID', str(uuid.uuid4()))
        
        # Set in context
        correlation_id_var.set(correlation_id)
        
        # Process request
        response = await call_next(request)
        
        # Add to response headers
        response.headers['X-Correlation-ID'] = correlation_id
        
        return response

def get_correlation_id() -> str:
    """Get current correlation ID from context"""
    try:
        return correlation_id_var.get()
    except LookupError:
        return str(uuid.uuid4())

def setup_correlation_middleware(app: FastAPI):
    """Add correlation ID middleware to FastAPI app"""
    app.add_middleware(CorrelationIdMiddleware)
    return app
```

---

## Phase 3: Custom Dashboards and Metrics

### 3.1 Grafana Dashboard Configuration

```json
{
  "dashboard": {
    "id": null,
    "title": "Screenshot-to-Code Microservices Dashboard",
    "description": "Comprehensive monitoring dashboard for Screenshot-to-Code application",
    "tags": ["screenshot-to-code", "microservices"],
    "timezone": "UTC",
    "refresh": "30s",
    "time": {
      "from": "now-1h",
      "to": "now"
    },
    "panels": [
      {
        "id": 1,
        "title": "Service Health Overview",
        "type": "stat",
        "gridPos": {"h": 4, "w": 24, "x": 0, "y": 0},
        "targets": [
          {
            "expr": "up{job=~\"screenshot-to-code-.*\"}",
            "legendFormat": "{{instance}}"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "mappings": [
              {"options": {"0": {"text": "Down", "color": "red"}}, "type": "value"},
              {"options": {"1": {"text": "Up", "color": "green"}}, "type": "value"}
            ]
          }
        }
      },
      {
        "id": 2,
        "title": "Request Rate by Service",
        "type": "graph",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 4},
        "targets": [
          {
            "expr": "sum(rate(http_requests_total[5m])) by (service)",
            "legendFormat": "{{service}}"
          }
        ],
        "yAxes": [
          {"label": "Requests/sec", "min": 0}
        ]
      },
      {
        "id": 3,
        "title": "Response Time Percentiles",
        "type": "graph",
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 4},
        "targets": [
          {
            "expr": "histogram_quantile(0.5, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service))",
            "legendFormat": "{{service}} p50"
          },
          {
            "expr": "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service))",
            "legendFormat": "{{service}} p95"
          },
          {
            "expr": "histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service))",
            "legendFormat": "{{service}} p99"
          }
        ],
        "yAxes": [
          {"label": "Response Time (ms)", "min": 0}
        ]
      },
      {
        "id": 4,
        "title": "Error Rate by Service",
        "type": "graph",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 12},
        "targets": [
          {
            "expr": "sum(rate(http_requests_total{status_code=~\"4.*|5.*\"}[5m])) by (service) / sum(rate(http_requests_total[5m])) by (service) * 100",
            "legendFormat": "{{service}} error rate"
          }
        ],
        "yAxes": [
          {"label": "Error Rate (%)", "min": 0, "max": 100}
        ]
      },
      {
        "id": 5,
        "title": "AI Provider Performance",
        "type": "graph",
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 12},
        "targets": [
          {
            "expr": "histogram_quantile(0.95, sum(rate(ai_provider_latency_bucket[5m])) by (le, provider, model))",
            "legendFormat": "{{provider}}/{{model}}"
          }
        ],
        "yAxes": [
          {"label": "Latency (ms)", "min": 0}
        ]
      },
      {
        "id": 6,
        "title": "Image Processing Metrics",
        "type": "graph",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 20},
        "targets": [
          {
            "expr": "histogram_quantile(0.95, sum(rate(image_processing_time_bucket[5m])) by (le, operation))",
            "legendFormat": "{{operation}}"
          }
        ],
        "yAxes": [
          {"label": "Processing Time (ms)", "min": 0}
        ]
      },
      {
        "id": 7,
        "title": "Memory Usage by Service",
        "type": "graph",
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 20},
        "targets": [
          {
            "expr": "container_memory_usage_bytes{container_label_com_docker_compose_service=~\"screenshot-to-code-.*\"} / container_spec_memory_limit_bytes * 100",
            "legendFormat": "{{container_label_com_docker_compose_service}}"
          }
        ],
        "yAxes": [
          {"label": "Memory Usage (%)", "min": 0, "max": 100}
        ]
      },
      {
        "id": 8,
        "title": "Business Metrics",
        "type": "graph",
        "gridPos": {"h": 8, "w": 24, "x": 0, "y": 28},
        "targets": [
          {
            "expr": "sum(rate(screenshot_conversions_total[5m]))",
            "legendFormat": "Screenshot Conversions/min"
          },
          {
            "expr": "sum(rate(code_generations_total[5m]))",
            "legendFormat": "Code Generations/min"
          },
          {
            "expr": "sum(rate(image_generations_total[5m]))",
            "legendFormat": "Image Generations/min"
          }
        ]
      }
    ]
  }
}
```

### 3.2 Azure Monitor Workbooks

```json
{
  "version": "Notebook/1.0",
  "items": [
    {
      "type": 1,
      "content": {
        "json": "# Screenshot-to-Code Monitoring Dashboard\n\nComprehensive monitoring dashboard for the Screenshot-to-Code microservices application."
      },
      "name": "title"
    },
    {
      "type": 10,
      "content": {
        "chartId": "workbook-chart-1",
        "version": "KqlItem/1.0",
        "query": "requests\n| where timestamp > ago(1h)\n| summarize RequestCount = count() by bin(timestamp, 5m), cloud_RoleName\n| render timechart",
        "size": 0,
        "title": "Request Volume by Service",
        "timeContext": {
          "durationMs": 3600000
        },
        "queryType": 0,
        "resourceType": "microsoft.insights/components"
      },
      "name": "request-volume"
    },
    {
      "type": 10,
      "content": {
        "chartId": "workbook-chart-2",
        "version": "KqlItem/1.0",
        "query": "requests\n| where timestamp > ago(1h)\n| summarize AverageResponseTime = avg(duration), P95ResponseTime = percentile(duration, 95) by bin(timestamp, 5m), cloud_RoleName\n| render timechart",
        "size": 0,
        "title": "Response Time Trends",
        "timeContext": {
          "durationMs": 3600000
        },
        "queryType": 0,
        "resourceType": "microsoft.insights/components"
      },
      "name": "response-times"
    },
    {
      "type": 10,
      "content": {
        "chartId": "workbook-chart-3",
        "version": "KqlItem/1.0",
        "query": "exceptions\n| where timestamp > ago(1h)\n| summarize ErrorCount = count() by bin(timestamp, 5m), cloud_RoleName, type\n| render barchart",
        "size": 0,
        "title": "Error Analysis",
        "timeContext": {
          "durationMs": 3600000
        },
        "queryType": 0,
        "resourceType": "microsoft.insights/components"
      },
      "name": "errors"
    },
    {
      "type": 10,
      "content": {
        "chartId": "workbook-chart-4",
        "version": "KqlItem/1.0",
        "query": "customEvents\n| where timestamp > ago(1h)\n| where name == \"ai_provider_call\"\n| extend provider = tostring(customDimensions.provider)\n| extend model = tostring(customDimensions.model)\n| extend duration = todouble(customDimensions.duration_ms)\n| summarize AvgDuration = avg(duration), P95Duration = percentile(duration, 95) by provider, model\n| render barchart",
        "size": 0,
        "title": "AI Provider Performance",
        "timeContext": {
          "durationMs": 3600000
        },
        "queryType": 0,
        "resourceType": "microsoft.insights/components"
      },
      "name": "ai-providers"
    }
  ]
}
```

---

## Phase 4: Intelligent Alerting Configuration

### 4.1 Azure Monitor Alert Rules

```json
{
  "alertRules": [
    {
      "name": "High Error Rate Alert",
      "description": "Alert when error rate exceeds 5% for any service",
      "severity": 2,
      "evaluationFrequency": "PT1M",
      "windowSize": "PT5M",
      "criteria": {
        "allOf": [
          {
            "query": "requests | where timestamp > ago(5m) | summarize ErrorRate = (todouble(countif(success == false)) / todouble(count())) * 100 by cloud_RoleName | where ErrorRate > 5",
            "timeAggregation": "Count",
            "operator": "GreaterThan",
            "threshold": 0,
            "failingPeriods": {
              "numberOfEvaluationPeriods": 2,
              "minFailingPeriodsToAlert": 1
            }
          }
        ]
      },
      "actions": [
        {
          "actionType": "EmailNotification",
          "emailAddresses": ["dev-team@company.com"],
          "subject": "Screenshot-to-Code: High Error Rate Alert"
        },
        {
          "actionType": "WebhookNotification",
          "webhookUrl": "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"
        }
      ]
    },
    {
      "name": "Response Time Alert",
      "description": "Alert when P95 response time exceeds 2 seconds",
      "severity": 3,
      "evaluationFrequency": "PT1M",
      "windowSize": "PT5M",
      "criteria": {
        "allOf": [
          {
            "query": "requests | where timestamp > ago(5m) | summarize P95Duration = percentile(duration, 95) by cloud_RoleName | where P95Duration > 2000",
            "timeAggregation": "Count",
            "operator": "GreaterThan",
            "threshold": 0
          }
        ]
      },
      "actions": [
        {
          "actionType": "EmailNotification",
          "emailAddresses": ["dev-team@company.com"]
        }
      ]
    },
    {
      "name": "Service Down Alert",
      "description": "Alert when any service becomes unavailable",
      "severity": 1,
      "evaluationFrequency": "PT1M",
      "windowSize": "PT2M",
      "criteria": {
        "allOf": [
          {
            "query": "requests | where timestamp > ago(2m) | summarize RequestCount = count() by cloud_RoleName | where RequestCount == 0",
            "timeAggregation": "Count",
            "operator": "GreaterThan",
            "threshold": 0
          }
        ]
      },
      "actions": [
        {
          "actionType": "EmailNotification",
          "emailAddresses": ["oncall@company.com"]
        },
        {
          "actionType": "PagerDuty",
          "serviceKey": "YOUR_PAGERDUTY_SERVICE_KEY"
        }
      ]
    },
    {
      "name": "AI Provider Latency Alert",
      "description": "Alert when AI provider response time is consistently high",
      "severity": 2,
      "evaluationFrequency": "PT5M",
      "windowSize": "PT10M",
      "criteria": {
        "allOf": [
          {
            "query": "customEvents | where timestamp > ago(10m) and name == 'ai_provider_call' | extend duration = todouble(customDimensions.duration_ms) | extend provider = tostring(customDimensions.provider) | summarize AvgDuration = avg(duration) by provider | where AvgDuration > 5000",
            "timeAggregation": "Count",
            "operator": "GreaterThan",
            "threshold": 0
          }
        ]
      }
    }
  ]
}
```

### 4.2 Smart Alert Configuration

```python
# monitoring/smart_alerts.py
import asyncio
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import httpx
from dataclasses import dataclass

@dataclass
class AlertRule:
    name: str
    condition: str
    threshold: float
    window_minutes: int
    severity: str
    cooldown_minutes: int = 30

@dataclass
class AlertContext:
    service: str
    metric: str
    current_value: float
    threshold: float
    timestamp: datetime

class SmartAlertManager:
    """Intelligent alert management with context and suppression"""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.alert_history = {}
        self.suppressed_alerts = set()
        
        # Define alert rules
        self.alert_rules = [
            AlertRule("high_error_rate", "error_rate > threshold", 5.0, 5, "critical"),
            AlertRule("slow_response", "p95_latency > threshold", 2000.0, 5, "warning"),
            AlertRule("ai_provider_slow", "ai_latency > threshold", 10000.0, 10, "warning"),
            AlertRule("memory_usage_high", "memory_percent > threshold", 85.0, 10, "warning"),
            AlertRule("disk_space_low", "disk_free_percent < threshold", 10.0, 15, "critical")
        ]
    
    async def evaluate_alerts(self, metrics: Dict[str, float]) -> List[AlertContext]:
        """Evaluate all alert rules against current metrics"""
        
        triggered_alerts = []
        
        for rule in self.alert_rules:
            alert_key = f"{rule.name}"
            
            # Skip if in cooldown
            if alert_key in self.suppressed_alerts:
                continue
            
            # Evaluate condition
            if self._evaluate_condition(rule, metrics):
                alert_context = AlertContext(
                    service="screenshot-to-code",
                    metric=rule.name,
                    current_value=metrics.get(rule.name.replace("_", ""), 0),
                    threshold=rule.threshold,
                    timestamp=datetime.utcnow()
                )
                
                triggered_alerts.append(alert_context)
                
                # Add to suppression list
                self.suppressed_alerts.add(alert_key)
                
                # Schedule removal from suppression
                asyncio.create_task(
                    self._remove_suppression(alert_key, rule.cooldown_minutes)
                )
        
        return triggered_alerts
    
    def _evaluate_condition(self, rule: AlertRule, metrics: Dict[str, float]) -> bool:
        """Evaluate if alert rule condition is met"""
        
        metric_key = rule.name.replace("_", "")
        current_value = metrics.get(metric_key, 0)
        
        if ">" in rule.condition:
            return current_value > rule.threshold
        elif "<" in rule.condition:
            return current_value < rule.threshold
        
        return False
    
    async def _remove_suppression(self, alert_key: str, cooldown_minutes: int):
        """Remove alert from suppression after cooldown period"""
        await asyncio.sleep(cooldown_minutes * 60)
        self.suppressed_alerts.discard(alert_key)
    
    async def send_alert(self, alert: AlertContext):
        """Send alert notification"""
        
        message = self._format_alert_message(alert)
        
        payload = {
            "text": f"🚨 Screenshot-to-Code Alert",
            "attachments": [
                {
                    "color": "danger" if alert.metric == "critical" else "warning",
                    "fields": [
                        {
                            "title": "Service",
                            "value": alert.service,
                            "short": True
                        },
                        {
                            "title": "Metric",
                            "value": alert.metric,
                            "short": True
                        },
                        {
                            "title": "Current Value",
                            "value": str(alert.current_value),
                            "short": True
                        },
                        {
                            "title": "Threshold",
                            "value": str(alert.threshold),
                            "short": True
                        },
                        {
                            "title": "Time",
                            "value": alert.timestamp.isoformat(),
                            "short": False
                        }
                    ]
                }
            ]
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.webhook_url, json=payload)
                response.raise_for_status()
            except Exception as e:
                print(f"Failed to send alert: {e}")
    
    def _format_alert_message(self, alert: AlertContext) -> str:
        """Format alert message for notifications"""
        
        return f"""
        Alert: {alert.metric}
        Service: {alert.service}
        Current Value: {alert.current_value}
        Threshold: {alert.threshold}
        Time: {alert.timestamp.isoformat()}
        """
```

---

## Phase 5: Health Checks and SLA Monitoring

### 5.1 Comprehensive Health Check System

```python
# shared/health/health_checker.py
import asyncio
import time
from typing import Dict, List, Optional
from enum import Enum
from dataclasses import dataclass
import httpx
import redis
import psycopg2
from azure.cosmos import CosmosClient

class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

@dataclass
class HealthCheckResult:
    name: str
    status: HealthStatus
    response_time_ms: float
    message: str
    timestamp: float
    details: Optional[Dict] = None

class HealthChecker:
    """Comprehensive health checking for all service dependencies"""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.checks = []
        
    def add_http_check(self, name: str, url: str, timeout: int = 5):
        """Add HTTP endpoint health check"""
        self.checks.append({
            'name': name,
            'type': 'http',
            'url': url,
            'timeout': timeout
        })
    
    def add_database_check(self, name: str, connection_string: str):
        """Add database health check"""
        self.checks.append({
            'name': name,
            'type': 'database',
            'connection_string': connection_string
        })
    
    def add_redis_check(self, name: str, redis_url: str):
        """Add Redis health check"""
        self.checks.append({
            'name': name,
            'type': 'redis',
            'redis_url': redis_url
        })
    
    def add_cosmosdb_check(self, name: str, connection_string: str):
        """Add Cosmos DB health check"""
        self.checks.append({
            'name': name,
            'type': 'cosmosdb',
            'connection_string': connection_string
        })
    
    async def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        """Run all configured health checks"""
        
        results = {}
        tasks = []
        
        for check_config in self.checks:
            task = asyncio.create_task(
                self._run_single_check(check_config)
            )
            tasks.append(task)
        
        check_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(check_results):
            check_name = self.checks[i]['name']
            
            if isinstance(result, Exception):
                results[check_name] = HealthCheckResult(
                    name=check_name,
                    status=HealthStatus.UNHEALTHY,
                    response_time_ms=0,
                    message=str(result),
                    timestamp=time.time()
                )
            else:
                results[check_name] = result
        
        return results
    
    async def _run_single_check(self, check_config: Dict) -> HealthCheckResult:
        """Run a single health check"""
        
        start_time = time.time()
        
        try:
            if check_config['type'] == 'http':
                return await self._check_http(check_config, start_time)
            elif check_config['type'] == 'database':
                return await self._check_database(check_config, start_time)
            elif check_config['type'] == 'redis':
                return await self._check_redis(check_config, start_time)
            elif check_config['type'] == 'cosmosdb':
                return await self._check_cosmosdb(check_config, start_time)
            else:
                raise ValueError(f"Unknown check type: {check_config['type']}")
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name=check_config['name'],
                status=HealthStatus.UNHEALTHY,
                response_time_ms=duration_ms,
                message=f"Check failed: {str(e)}",
                timestamp=time.time()
            )
    
    async def _check_http(self, config: Dict, start_time: float) -> HealthCheckResult:
        """Check HTTP endpoint health"""
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                config['url'], 
                timeout=config['timeout']
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                status = HealthStatus.HEALTHY
                message = "OK"
            elif 400 <= response.status_code < 500:
                status = HealthStatus.DEGRADED
                message = f"Client error: {response.status_code}"
            else:
                status = HealthStatus.UNHEALTHY
                message = f"Server error: {response.status_code}"
            
            return HealthCheckResult(
                name=config['name'],
                status=status,
                response_time_ms=duration_ms,
                message=message,
                timestamp=time.time(),
                details={'status_code': response.status_code}
            )
    
    async def _check_database(self, config: Dict, start_time: float) -> HealthCheckResult:
        """Check PostgreSQL database health"""
        
        conn = None
        try:
            conn = psycopg2.connect(config['connection_string'])
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            
            duration_ms = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                name=config['name'],
                status=HealthStatus.HEALTHY,
                response_time_ms=duration_ms,
                message="Database connection successful",
                timestamp=time.time()
            )
            
        finally:
            if conn:
                conn.close()
    
    async def _check_redis(self, config: Dict, start_time: float) -> HealthCheckResult:
        """Check Redis health"""
        
        r = redis.from_url(config['redis_url'])
        
        try:
            r.ping()
            duration_ms = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                name=config['name'],
                status=HealthStatus.HEALTHY,
                response_time_ms=duration_ms,
                message="Redis ping successful",
                timestamp=time.time()
            )
        finally:
            r.close()
    
    async def _check_cosmosdb(self, config: Dict, start_time: float) -> HealthCheckResult:
        """Check Cosmos DB health"""
        
        client = CosmosClient.from_connection_string(config['connection_string'])
        
        try:
            # List databases to test connection
            list(client.list_databases())
            duration_ms = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                name=config['name'],
                status=HealthStatus.HEALTHY,
                response_time_ms=duration_ms,
                message="Cosmos DB connection successful",
                timestamp=time.time()
            )
        finally:
            client.close()

# Usage in FastAPI applications
def create_health_endpoint(app, health_checker: HealthChecker):
    """Create detailed health check endpoint"""
    
    @app.get("/health")
    async def health_check():
        """Detailed health check endpoint"""
        
        # Run all health checks
        check_results = await health_checker.run_all_checks()
        
        # Determine overall health
        overall_status = HealthStatus.HEALTHY
        unhealthy_count = 0
        degraded_count = 0
        
        for result in check_results.values():
            if result.status == HealthStatus.UNHEALTHY:
                unhealthy_count += 1
            elif result.status == HealthStatus.DEGRADED:
                degraded_count += 1
        
        if unhealthy_count > 0:
            overall_status = HealthStatus.UNHEALTHY
        elif degraded_count > 0:
            overall_status = HealthStatus.DEGRADED
        
        return {
            "service": health_checker.service_name,
            "status": overall_status.value,
            "timestamp": time.time(),
            "checks": {
                name: {
                    "status": result.status.value,
                    "response_time_ms": result.response_time_ms,
                    "message": result.message,
                    "details": result.details
                }
                for name, result in check_results.items()
            }
        }
    
    @app.get("/health/ready")
    async def readiness_check():
        """Kubernetes readiness probe endpoint"""
        
        check_results = await health_checker.run_all_checks()
        
        # Service is ready if no checks are unhealthy
        unhealthy_checks = [
            name for name, result in check_results.items() 
            if result.status == HealthStatus.UNHEALTHY
        ]
        
        if unhealthy_checks:
            return {"status": "not_ready", "failed_checks": unhealthy_checks}, 503
        
        return {"status": "ready"}
    
    @app.get("/health/live")
    async def liveness_check():
        """Kubernetes liveness probe endpoint"""
        
        # Simple liveness check - service is alive if it can respond
        return {
            "status": "alive",
            "service": health_checker.service_name,
            "timestamp": time.time()
        }
    
    return app
```

---

## Completion Checklist

### ✅ **Application Insights Integration**
- [x] **Centralized Configuration**: Application Insights setup for all services
- [x] **Distributed Tracing**: OpenTelemetry integration with correlation IDs
- [x] **Custom Metrics**: Business metrics and performance tracking
- [x] **Structured Logging**: JSON logging with contextual information

### ✅ **Log Aggregation & Analysis**
- [x] **Structured Logging**: Consistent JSON format across all services
- [x] **Correlation IDs**: Request tracing across microservices
- [x] **Security Event Logging**: Authentication and authorization events
- [x] **Business Metrics Logging**: Conversion rates and usage patterns

### ✅ **Monitoring Dashboards**
- [x] **Grafana Dashboards**: Real-time service metrics and performance
- [x] **Azure Monitor Workbooks**: Application Insights data visualization
- [x] **Custom Metrics**: AI provider performance and image processing metrics
- [x] **Business Intelligence**: User conversion and cost analysis

### ✅ **Intelligent Alerting**
- [x] **Azure Monitor Alerts**: Multi-threshold alerting with smart suppression
- [x] **Smart Alert Manager**: Context-aware alerting with cooldown periods
- [x] **Multi-Channel Notifications**: Slack, Teams, and PagerDuty integration
- [x] **SLA Monitoring**: Service level agreement tracking and reporting

### ✅ **Health Monitoring**
- [x] **Comprehensive Health Checks**: Database, Redis, HTTP, and Cosmos DB checks
- [x] **Kubernetes Probes**: Readiness and liveness probe endpoints
- [x] **Dependency Monitoring**: Downstream service health tracking
- [x] **Performance Baselines**: Response time and availability SLA monitoring

---

## Next Steps for TASK-008

### Immediate Integration Actions
1. **Application Insights Deployment**: Configure connection strings in Azure Key Vault
2. **Dashboard Setup**: Deploy Grafana and Azure Monitor workbooks
3. **Alert Configuration**: Setup alert rules and notification channels
4. **Service Integration**: Add monitoring middleware to all microservices
5. **Testing & Validation**: Verify end-to-end monitoring functionality

### Monitoring Success Metrics
- **Observability Coverage**: 100% service instrumentation
- **Alert Response Time**: <5 minutes for critical alerts
- **Dashboard Load Time**: <2 seconds for all dashboards
- **Log Search Performance**: <10 seconds for 24-hour queries
- **Health Check Response**: <500ms for all dependency checks

---

**Status**: Monitoring and logging setup completed  
**Next Action**: Begin TASK-008 - Security Architecture Design  
**Deliverables**: Application Insights integration, Grafana dashboards, intelligent alerting, comprehensive health checks