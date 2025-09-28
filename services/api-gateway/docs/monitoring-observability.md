# Monitoring and Observability

## Overview

This document describes the comprehensive monitoring and observability system implemented in the API Gateway service. The system provides full-stack monitoring with metrics collection, distributed tracing, alerting, and visualization capabilities.

## Architecture Components

### 1. Prometheus Metrics Collection

**Purpose**: Comprehensive metrics collection for monitoring application and infrastructure performance.

**Key Features**:
- **Core HTTP Metrics**: Request count, duration, size, and status codes
- **Business Metrics**: Code generation, image generation, and WebSocket statistics
- **Infrastructure Metrics**: Circuit breaker state, service discovery, connection pools
- **Security Metrics**: Authentication attempts, rate limiting, security events
- **System Metrics**: Memory, CPU, garbage collection statistics

**Metrics Categories**:

#### HTTP Request Metrics
- `http_requests_total`: Total HTTP requests by method, endpoint, and status code
- `http_request_duration_seconds`: Request duration histogram
- `http_request_size_bytes`: Request size histogram
- `http_response_size_bytes`: Response size histogram

#### Business Metrics
- `code_generations_total`: Total code generations by framework and status
- `code_generation_duration_seconds`: Code generation duration histogram
- `image_generations_total`: Total image generations by status
- `image_generation_duration_seconds`: Image generation duration histogram
- `websocket_connections_total`: WebSocket connection events
- `websocket_messages_total`: WebSocket message count by direction and type
- `websocket_connections_active`: Current active WebSocket connections

#### Infrastructure Metrics
- `circuit_breaker_requests_total`: Circuit breaker requests by service and outcome
- `circuit_breaker_state`: Current circuit breaker state (closed/open/half_open)
- `circuit_breaker_failure_rate`: Current failure rate per service
- `service_instances_total`: Service instances by health status
- `service_health_checks_total`: Health check results
- `connection_pool_connections_active`: Active connections per service
- `connection_pool_requests_total`: Connection pool requests by result

#### Security Metrics
- `auth_attempts_total`: Authentication attempts by result and method
- `auth_token_validations_total`: Token validation results
- `rate_limit_requests_total`: Rate limit checks by result
- `rate_limit_violations_total`: Rate limit violations by client
- `security_events_total`: Security events by type and severity

### 2. OpenTelemetry Distributed Tracing

**Purpose**: End-to-end request tracing across microservices with context propagation.

**Key Features**:
- **Automatic Instrumentation**: FastAPI, HTTPX, and asyncio instrumentation
- **Custom Spans**: Manual span creation for business logic
- **Context Propagation**: Trace context propagation across service boundaries
- **Multiple Exporters**: Jaeger, OTLP, and console exporters
- **Baggage Support**: Additional context data propagation

**Trace Configuration**:
```python
TraceConfig(
    service_name="api-gateway",
    environment="production",
    jaeger_endpoint="jaeger:14268",
    otlp_endpoint="otel-collector:4317",
    sample_rate=1.0
)
```

**Usage Examples**:
```python
# Automatic tracing (via middleware)
@app.get("/api/v1/generate/code")
async def generate_code(request: Request):
    # Automatically traced
    pass

# Manual span creation
async with tracing.trace_request("custom_operation") as span:
    span.set_attribute("custom.attribute", "value")
    # Your code here

# Downstream service tracing
async with tracing.trace_downstream_call(
    service_name="code_generator",
    operation="generate",
    url="http://code-generator/generate",
    method="POST"
) as (span, headers):
    # headers contain trace context for propagation
    response = await http_client.post(url, headers=headers)
```

### 3. Advanced Alerting System

**Purpose**: Multi-channel alerting with rules engine, escalation, and suppression.

**Key Features**:
- **Rule-Based Alerting**: Configurable alert rules with conditions
- **Multi-Channel Notifications**: Email, Slack, PagerDuty, webhook support
- **Alert Escalation**: Time-based escalation with different notification channels
- **Alert Suppression**: Temporary alert suppression to reduce noise
- **Alert Acknowledgment**: Manual alert acknowledgment tracking

**Default Alert Rules**:

#### System Alerts
- **High Error Rate**: Error rate > 5% for 5 minutes
- **High Response Time**: Average response time > 5 seconds for 5 minutes
- **Circuit Breaker Open**: Any circuit breaker opens for 1 minute
- **Service Unavailable**: Service health check fails for 2 minutes
- **High Memory Usage**: Memory usage > 85% for 10 minutes
- **Rate Limit Violations**: Rate limit violations > 100 per hour

#### Business Alerts
- **Code Generation Failures**: Code generation failure rate > 10% for 5 minutes
- **Image Generation Failures**: Image generation failure rate > 10% for 5 minutes
- **WebSocket Connection Issues**: High WebSocket disconnection rate

**Alert Configuration**:
```python
AlertRule(
    name="high_error_rate",
    condition="error_rate > 0.05",
    severity=AlertSeverity.HIGH,
    message_template="High error rate detected: {error_rate:.2%}",
    channels=["email", "slack"],
    threshold=0.05,
    duration_seconds=300
)
```

### 4. Monitoring Middleware

**Purpose**: Automatic request monitoring with minimal performance impact.

**Components**:
- **MonitoringMiddleware**: Comprehensive monitoring with metrics, tracing, and alerting
- **BusinessMetricsMiddleware**: Business-specific metrics tracking
- **MetricsCollectionMiddleware**: Lightweight metrics collection

**Features**:
- **Request Tracking**: Automatic request/response monitoring
- **Performance Monitoring**: Response time and resource usage tracking
- **Error Detection**: Automatic error condition detection
- **Business Logic Integration**: Custom business metrics from request patterns

## API Endpoints

### Metrics Endpoints

#### GET /api/v1/metrics
**Purpose**: Prometheus metrics export endpoint

**Response**: Plain text Prometheus metrics format
```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",endpoint="/api/v1/health",status_code="200"} 150
```

#### GET /api/v1/metrics/summary
**Purpose**: JSON metrics summary

**Response**:
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "correlation_id": "req-123456",
  "service": "api-gateway",
  "metrics_summary": {
    "total_requests": 1000,
    "successful_requests": 950,
    "failed_requests": 50,
    "success_rate": 0.95,
    "metrics_collected": 45,
    "uptime_seconds": 3600
  }
}
```

### Tracing Endpoints

#### GET /api/v1/trace
**Purpose**: Current trace context information

**Response**:
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "correlation_id": "req-123456",
  "service": "api-gateway",
  "trace_context": {
    "trace_id": "abc123def456",
    "span_id": "def456ghi789",
    "baggage": {}
  },
  "tracing_config": {
    "service_name": "api-gateway",
    "environment": "production",
    "sample_rate": 1.0
  }
}
```

#### POST /api/v1/trace/flush
**Purpose**: Force flush pending traces

**Response**:
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "correlation_id": "req-123456",
  "service": "api-gateway",
  "status": "success",
  "message": "Traces flushed successfully"
}
```

### Alert Management Endpoints

#### GET /api/v1/alerts
**Purpose**: Get active alerts with optional filtering

**Query Parameters**:
- `status`: Filter by alert status (firing, resolved, suppressed, acknowledged)
- `severity`: Filter by alert severity (critical, high, medium, low, info)

**Response**:
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "correlation_id": "req-123456",
  "service": "api-gateway",
  "alerts": [
    {
      "rule_name": "high_error_rate",
      "severity": "high",
      "status": "firing",
      "message": "High error rate detected: 7.5%",
      "started_at": "2024-01-15T10:25:00Z",
      "labels": {
        "service": "api-gateway"
      }
    }
  ],
  "total_count": 1
}
```

#### GET /api/v1/alerts/stats
**Purpose**: Alert statistics

**Response**:
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "correlation_id": "req-123456",
  "service": "api-gateway",
  "alert_statistics": {
    "active_alerts": 3,
    "resolved_alerts_last_7_days": 15,
    "active_by_severity": {
      "critical": 1,
      "high": 2,
      "medium": 0
    },
    "total_rules": 12,
    "enabled_rules": 12,
    "notification_channels": 3
  }
}
```

#### POST /api/v1/alerts/{fingerprint}/acknowledge
**Purpose**: Acknowledge an alert

**Query Parameters**:
- `acknowledged_by`: User acknowledging the alert

**Response**:
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "correlation_id": "req-123456",
  "service": "api-gateway",
  "status": "success",
  "message": "Alert abc123 acknowledged by user123"
}
```

#### POST /api/v1/alerts/{fingerprint}/suppress
**Purpose**: Suppress an alert

**Query Parameters**:
- `duration_minutes`: Suppression duration (1-1440 minutes)

**Response**:
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "correlation_id": "req-123456",
  "service": "api-gateway",
  "status": "success",
  "message": "Alert abc123 suppressed for 60 minutes"
}
```

### Observability Overview

#### GET /api/v1/observability
**Purpose**: Comprehensive observability status

**Response**:
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "correlation_id": "req-123456",
  "service": "api-gateway",
  "observability": {
    "metrics": {
      "status": "active",
      "summary": {
        "total_requests": 1000,
        "success_rate": 0.95
      }
    },
    "tracing": {
      "status": "active",
      "current_trace_id": "abc123def456",
      "service_name": "api-gateway",
      "environment": "production",
      "sample_rate": 1.0
    },
    "alerting": {
      "status": "active",
      "statistics": {
        "active_alerts": 3,
        "total_rules": 12
      }
    },
    "logging": {
      "status": "active",
      "service": "api-gateway",
      "environment": "production",
      "log_level": "info"
    }
  },
  "health": {
    "overall_status": "healthy",
    "components": {
      "metrics": "healthy",
      "tracing": "healthy",
      "alerting": "healthy",
      "logging": "healthy"
    }
  }
}
```

## Dashboard and Visualization

### Grafana Dashboards

The monitoring stack includes pre-configured Grafana dashboards:

#### API Gateway Overview Dashboard
- **Request Rate**: Requests per second over time
- **Response Time**: P95, P99 response time percentiles
- **Error Rate**: 4xx and 5xx error rates
- **Throughput**: Request and response sizes
- **Active Connections**: WebSocket and HTTP connections

#### Service Health Dashboard
- **Circuit Breaker Status**: State of all circuit breakers
- **Service Discovery**: Health status of all service instances
- **Connection Pools**: Pool utilization and performance
- **Dependency Health**: Status of downstream services

#### Business Metrics Dashboard
- **Code Generation**: Success rate, duration, framework breakdown
- **Image Generation**: Success rate, duration, usage patterns
- **WebSocket Usage**: Connection count, message rates, errors

#### Infrastructure Dashboard
- **System Resources**: CPU, memory, disk usage
- **Container Metrics**: Resource usage by container
- **Network Performance**: Request latency, connection stats
- **Security Events**: Authentication failures, rate limiting violations

### Alert Visualization

Grafana integration with AlertManager provides:
- **Alert Timeline**: Historical view of alert firing and resolution
- **Alert Heatmap**: Alert frequency by service and severity
- **MTTR Tracking**: Mean time to resolution for different alert types
- **Escalation Tracking**: Alert escalation patterns and effectiveness

## Deployment and Configuration

### Docker Compose Deployment

Use the provided `docker-compose.monitoring.yml` for complete monitoring stack:

```bash
# Start monitoring stack
docker-compose -f docker-compose.monitoring.yml up -d

# View logs
docker-compose -f docker-compose.monitoring.yml logs -f api-gateway

# Scale services
docker-compose -f docker-compose.monitoring.yml up -d --scale api-gateway=3
```

### Environment Configuration

```env
# Tracing Configuration
JAEGER_ENDPOINT=jaeger:14268
OTLP_ENDPOINT=otel-collector:4317
TRACE_SAMPLE_RATE=1.0

# Alerting Configuration
SLACK_WEBHOOK_URL=https://hooks.slack.com/your-webhook
ALERT_FROM_EMAIL=alerts@yourcompany.com
ALERT_TO_EMAILS=team@yourcompany.com,oncall@yourcompany.com

# SMTP Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# PagerDuty Configuration
PAGERDUTY_API_KEY=your-pagerduty-key
PAGERDUTY_SERVICE_KEY=your-service-key
```

### Kubernetes Deployment

For Kubernetes deployment, use the provided manifests:

```yaml
# monitoring-configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: monitoring-config
data:
  prometheus.yml: |
    # Prometheus configuration
  alertmanager.yml: |
    # AlertManager configuration
---
# monitoring-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/api/v1/metrics"
    spec:
      containers:
      - name: api-gateway
        image: api-gateway:latest
        env:
        - name: JAEGER_ENDPOINT
          value: "jaeger.monitoring.svc.cluster.local:14268"
        ports:
        - containerPort: 8000
```

## Performance Considerations

### Metrics Collection Impact
- **CPU Overhead**: < 2% additional CPU usage
- **Memory Overhead**: ~50MB for metrics storage
- **Network Overhead**: Metrics export ~1KB/s per service
- **Storage**: ~100MB/day for metrics data

### Tracing Performance Impact
- **Sampling**: Configure appropriate sampling rates (1.0 for development, 0.1-0.01 for production)
- **Batch Export**: Traces are exported in batches to minimize performance impact
- **Resource Usage**: ~10MB memory per 1000 active spans

### Alerting Performance
- **Evaluation Frequency**: Alerts evaluated every 30 seconds
- **Notification Rate Limiting**: Configurable rate limits to prevent spam
- **Resource Usage**: ~5MB memory for alert state management

## Best Practices

### Metrics Best Practices
1. **Label Cardinality**: Keep label cardinality low to avoid memory issues
2. **Metric Naming**: Use consistent naming conventions (counter_total, duration_seconds)
3. **Business Metrics**: Focus on metrics that matter to business outcomes
4. **Retention**: Configure appropriate retention periods (15 days default)

### Tracing Best Practices
1. **Sampling Strategy**: Use adaptive sampling based on service load
2. **Span Attributes**: Include relevant attributes for debugging
3. **Error Tracking**: Always record exceptions in spans
4. **Performance**: Minimize tracing overhead in hot paths

### Alerting Best Practices
1. **Alert Fatigue**: Configure alerts that are actionable
2. **Escalation**: Implement proper escalation for critical alerts
3. **Runbooks**: Provide runbooks for common alerts
4. **Testing**: Regularly test alert channels and escalation

### Dashboard Best Practices
1. **User-Focused**: Design dashboards for specific user roles
2. **Performance**: Optimize queries for dashboard responsiveness
3. **Context**: Provide sufficient context for troubleshooting
4. **Automation**: Use dashboard provisioning for consistency

## Troubleshooting

### Common Issues

#### Metrics Not Appearing
1. Check service is running and healthy
2. Verify `/api/v1/metrics` endpoint is accessible
3. Check Prometheus configuration and targets
4. Verify network connectivity between services

#### Traces Not Showing
1. Check Jaeger/OTLP endpoint configuration
2. Verify trace sampling rate is not too low
3. Check trace context propagation headers
4. Monitor trace export errors in logs

#### Alerts Not Firing
1. Verify alert rule conditions
2. Check metrics data availability
3. Verify AlertManager configuration
4. Test notification channels

#### High Resource Usage
1. Reduce metrics cardinality
2. Lower trace sampling rate
3. Increase batch export intervals
4. Optimize dashboard queries

### Debug Endpoints

Use debug endpoints for troubleshooting:

```bash
# Check current trace context
curl -X GET http://localhost:8000/api/v1/debug/trace-context

# Trigger test alert
curl -X POST "http://localhost:8000/api/v1/test/alert?severity=warning&message=Test"

# Get monitoring middleware stats
curl -X GET http://localhost:8000/api/v1/observability
```

## Security Considerations

### Metrics Security
- **Sensitive Data**: Never include sensitive data in metric labels
- **Access Control**: Secure metrics endpoints with authentication
- **Network Security**: Use TLS for metrics transmission

### Tracing Security
- **Data Sanitization**: Sanitize sensitive data from traces
- **Access Control**: Secure tracing backend access
- **Retention**: Configure appropriate trace retention periods

### Alerting Security
- **Webhook Security**: Secure webhook endpoints and validate payloads
- **Credential Management**: Use secure credential storage for SMTP/API keys
- **Access Logs**: Monitor access to alert management endpoints

## Future Enhancements

### Planned Features
- **Machine Learning Alerts**: Anomaly detection based alerts
- **Custom Dashboards**: User-configurable dashboard builder
- **SLA Monitoring**: Automated SLA compliance monitoring
- **Cost Analytics**: Resource usage and cost tracking
- **Mobile Alerts**: Mobile app integration for critical alerts

### Integration Roadmap
- **APM Integration**: Application Performance Monitoring integration
- **Log Analysis**: Advanced log analysis and correlation
- **Security Monitoring**: Enhanced security event monitoring
- **Business Intelligence**: Integration with BI tools and data warehouses

## Conclusion

The comprehensive monitoring and observability system provides complete visibility into the API Gateway service performance, health, and business metrics. The combination of metrics, tracing, and alerting ensures reliable service operation and quick issue resolution.

The system is designed for production use with appropriate performance considerations, security measures, and operational best practices. Regular monitoring of the monitoring system itself ensures continued reliability and effectiveness.