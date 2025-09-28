"""
Monitoring and Observability Routes
Endpoints for metrics, health checks, and monitoring management
"""
from typing import Dict, Any, List
import json

from fastapi import APIRouter, Request, Response, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, JSONResponse

from app.monitoring.prometheus_metrics import PrometheusMetrics
from app.monitoring.opentelemetry_tracing import TracingManager
from app.monitoring.alerting import AlertManager
from shared.monitoring.structured_logger import StructuredLogger
from shared.monitoring.correlation import get_correlation_id

router = APIRouter()

def get_metrics(request: Request) -> PrometheusMetrics:
    """Dependency to get metrics from app state"""
    return request.app.state.metrics

def get_tracing(request: Request) -> TracingManager:
    """Dependency to get tracing manager from app state"""
    return request.app.state.tracing

def get_alerting(request: Request) -> AlertManager:
    """Dependency to get alert manager from app state"""
    return request.app.state.alerting

def get_logger(request: Request) -> StructuredLogger:
    """Dependency to get logger from app state"""
    return request.app.state.logger

@router.get("/metrics")
async def get_prometheus_metrics(
    request: Request,
    metrics: PrometheusMetrics = Depends(get_metrics)
) -> Response:
    """Prometheus metrics endpoint"""
    try:
        metrics_data = metrics.get_metrics()
        return PlainTextResponse(
            content=metrics_data,
            media_type=metrics.get_content_type()
        )
    except Exception as e:
        logger = get_logger(request)
        logger.error("Failed to get metrics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")

@router.get("/metrics/summary")
async def get_metrics_summary(
    request: Request,
    metrics: PrometheusMetrics = Depends(get_metrics),
    logger: StructuredLogger = Depends(get_logger)
) -> JSONResponse:
    """Get metrics summary in JSON format"""
    correlation_id = get_correlation_id()
    
    try:
        summary_stats = metrics.get_summary_stats()
        
        response_data = {
            "timestamp": logger._get_timestamp(),
            "correlation_id": correlation_id,
            "service": request.app.state.settings.service_name,
            "metrics_summary": summary_stats
        }
        
        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error("Failed to get metrics summary",
                    error=str(e),
                    correlation_id=correlation_id)
        
        return JSONResponse(
            content={
                "error": "Failed to retrieve metrics summary",
                "correlation_id": correlation_id,
                "timestamp": logger._get_timestamp()
            },
            status_code=500
        )

@router.get("/trace")
async def get_trace_info(
    request: Request,
    tracing: TracingManager = Depends(get_tracing),
    logger: StructuredLogger = Depends(get_logger)
) -> JSONResponse:
    """Get current trace information"""
    correlation_id = get_correlation_id()
    
    try:
        span_context = tracing.get_current_span_context()
        
        response_data = {
            "timestamp": logger._get_timestamp(),
            "correlation_id": correlation_id,
            "service": request.app.state.settings.service_name,
            "trace_context": {
                "trace_id": span_context.trace_id if span_context else None,
                "span_id": span_context.span_id if span_context else None,
                "baggage": span_context.baggage if span_context else {}
            },
            "tracing_config": {
                "service_name": tracing.config.service_name,
                "environment": tracing.config.environment,
                "sample_rate": tracing.config.sample_rate
            }
        }
        
        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error("Failed to get trace info",
                    error=str(e),
                    correlation_id=correlation_id)
        
        return JSONResponse(
            content={
                "error": "Failed to retrieve trace information",
                "correlation_id": correlation_id,
                "timestamp": logger._get_timestamp()
            },
            status_code=500
        )

@router.post("/trace/flush")
async def flush_traces(
    request: Request,
    tracing: TracingManager = Depends(get_tracing),
    logger: StructuredLogger = Depends(get_logger)
) -> JSONResponse:
    """Flush pending traces"""
    correlation_id = get_correlation_id()
    
    try:
        await tracing.flush_spans()
        
        response_data = {
            "timestamp": logger._get_timestamp(),
            "correlation_id": correlation_id,
            "service": request.app.state.settings.service_name,
            "status": "success",
            "message": "Traces flushed successfully"
        }
        
        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error("Failed to flush traces",
                    error=str(e),
                    correlation_id=correlation_id)
        
        return JSONResponse(
            content={
                "error": "Failed to flush traces",
                "correlation_id": correlation_id,
                "timestamp": logger._get_timestamp()
            },
            status_code=500
        )

@router.get("/alerts")
async def get_alerts(
    request: Request,
    status: str = Query(None, description="Filter by alert status"),
    severity: str = Query(None, description="Filter by alert severity"),
    alerting: AlertManager = Depends(get_alerting),
    logger: StructuredLogger = Depends(get_logger)
) -> JSONResponse:
    """Get active alerts with optional filtering"""
    correlation_id = get_correlation_id()
    
    try:
        active_alerts = alerting.get_active_alerts()
        
        # Apply filters
        if status:
            active_alerts = [a for a in active_alerts if a['status'] == status]
        
        if severity:
            active_alerts = [a for a in active_alerts if a['severity'] == severity]
        
        response_data = {
            "timestamp": logger._get_timestamp(),
            "correlation_id": correlation_id,
            "service": request.app.state.settings.service_name,
            "alerts": active_alerts,
            "total_count": len(active_alerts),
            "filters": {
                "status": status,
                "severity": severity
            }
        }
        
        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error("Failed to get alerts",
                    error=str(e),
                    correlation_id=correlation_id)
        
        return JSONResponse(
            content={
                "error": "Failed to retrieve alerts",
                "correlation_id": correlation_id,
                "timestamp": logger._get_timestamp()
            },
            status_code=500
        )

@router.get("/alerts/stats")
async def get_alert_stats(
    request: Request,
    alerting: AlertManager = Depends(get_alerting),
    logger: StructuredLogger = Depends(get_logger)
) -> JSONResponse:
    """Get alerting statistics"""
    correlation_id = get_correlation_id()
    
    try:
        alert_stats = alerting.get_alert_stats()
        
        response_data = {
            "timestamp": logger._get_timestamp(),
            "correlation_id": correlation_id,
            "service": request.app.state.settings.service_name,
            "alert_statistics": alert_stats
        }
        
        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error("Failed to get alert stats",
                    error=str(e),
                    correlation_id=correlation_id)
        
        return JSONResponse(
            content={
                "error": "Failed to retrieve alert statistics",
                "correlation_id": correlation_id,
                "timestamp": logger._get_timestamp()
            },
            status_code=500
        )

@router.post("/alerts/{fingerprint}/acknowledge")
async def acknowledge_alert(
    fingerprint: str,
    request: Request,
    acknowledged_by: str = Query(..., description="User acknowledging the alert"),
    alerting: AlertManager = Depends(get_alerting),
    logger: StructuredLogger = Depends(get_logger)
) -> JSONResponse:
    """Acknowledge an alert"""
    correlation_id = get_correlation_id()
    
    try:
        alerting.acknowledge_alert(fingerprint, acknowledged_by)
        
        logger.info("Alert acknowledged via API",
                   fingerprint=fingerprint,
                   acknowledged_by=acknowledged_by,
                   correlation_id=correlation_id)
        
        response_data = {
            "timestamp": logger._get_timestamp(),
            "correlation_id": correlation_id,
            "service": request.app.state.settings.service_name,
            "status": "success",
            "message": f"Alert {fingerprint} acknowledged by {acknowledged_by}"
        }
        
        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error("Failed to acknowledge alert",
                    fingerprint=fingerprint,
                    error=str(e),
                    correlation_id=correlation_id)
        
        return JSONResponse(
            content={
                "error": "Failed to acknowledge alert",
                "correlation_id": correlation_id,
                "timestamp": logger._get_timestamp()
            },
            status_code=500
        )

@router.post("/alerts/{fingerprint}/suppress")
async def suppress_alert(
    fingerprint: str,
    request: Request,
    duration_minutes: int = Query(..., description="Suppression duration in minutes"),
    alerting: AlertManager = Depends(get_alerting),
    logger: StructuredLogger = Depends(get_logger)
) -> JSONResponse:
    """Suppress an alert for a specified duration"""
    correlation_id = get_correlation_id()
    
    try:
        if duration_minutes <= 0 or duration_minutes > 1440:  # Max 24 hours
            raise HTTPException(
                status_code=400,
                detail="Duration must be between 1 and 1440 minutes"
            )
        
        alerting.suppress_alert(fingerprint, duration_minutes)
        
        logger.info("Alert suppressed via API",
                   fingerprint=fingerprint,
                   duration_minutes=duration_minutes,
                   correlation_id=correlation_id)
        
        response_data = {
            "timestamp": logger._get_timestamp(),
            "correlation_id": correlation_id,
            "service": request.app.state.settings.service_name,
            "status": "success",
            "message": f"Alert {fingerprint} suppressed for {duration_minutes} minutes"
        }
        
        return JSONResponse(content=response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to suppress alert",
                    fingerprint=fingerprint,
                    error=str(e),
                    correlation_id=correlation_id)
        
        return JSONResponse(
            content={
                "error": "Failed to suppress alert",
                "correlation_id": correlation_id,
                "timestamp": logger._get_timestamp()
            },
            status_code=500
        )

@router.get("/observability")
async def get_observability_overview(
    request: Request,
    metrics: PrometheusMetrics = Depends(get_metrics),
    tracing: TracingManager = Depends(get_tracing),
    alerting: AlertManager = Depends(get_alerting),
    logger: StructuredLogger = Depends(get_logger)
) -> JSONResponse:
    """Get comprehensive observability overview"""
    correlation_id = get_correlation_id()
    
    try:
        # Get data from all monitoring components
        metrics_summary = metrics.get_summary_stats()
        alert_stats = alerting.get_alert_stats()
        span_context = tracing.get_current_span_context()
        
        response_data = {
            "timestamp": logger._get_timestamp(),
            "correlation_id": correlation_id,
            "service": request.app.state.settings.service_name,
            "observability": {
                "metrics": {
                    "status": "active",
                    "summary": metrics_summary
                },
                "tracing": {
                    "status": "active",
                    "current_trace_id": span_context.trace_id if span_context else None,
                    "service_name": tracing.config.service_name,
                    "environment": tracing.config.environment,
                    "sample_rate": tracing.config.sample_rate
                },
                "alerting": {
                    "status": "active",
                    "statistics": alert_stats
                },
                "logging": {
                    "status": "active",
                    "service": logger.service_name,
                    "environment": logger.environment,
                    "log_level": logger.log_level
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
        
        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error("Failed to get observability overview",
                    error=str(e),
                    correlation_id=correlation_id)
        
        return JSONResponse(
            content={
                "error": "Failed to retrieve observability overview",
                "correlation_id": correlation_id,
                "timestamp": logger._get_timestamp()
            },
            status_code=500
        )

@router.get("/debug/trace-context")
async def get_debug_trace_context(
    request: Request,
    tracing: TracingManager = Depends(get_tracing),
    logger: StructuredLogger = Depends(get_logger)
) -> JSONResponse:
    """Debug endpoint to show current trace context"""
    correlation_id = get_correlation_id()
    
    try:
        span_context = tracing.get_current_span_context()
        request_headers = dict(request.headers)
        
        response_data = {
            "timestamp": logger._get_timestamp(),
            "correlation_id": correlation_id,
            "service": request.app.state.settings.service_name,
            "debug_info": {
                "current_span_context": {
                    "trace_id": span_context.trace_id if span_context else None,
                    "span_id": span_context.span_id if span_context else None,
                    "baggage": span_context.baggage if span_context else {}
                } if span_context else None,
                "request_headers": {
                    k: v for k, v in request_headers.items()
                    if k.lower().startswith(('x-', 'trace', 'span', 'baggage'))
                },
                "tracing_config": {
                    "service_name": tracing.config.service_name,
                    "environment": tracing.config.environment,
                    "sample_rate": tracing.config.sample_rate,
                    "jaeger_endpoint": tracing.config.jaeger_endpoint,
                    "otlp_endpoint": tracing.config.otlp_endpoint
                }
            }
        }
        
        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error("Failed to get debug trace context",
                    error=str(e),
                    correlation_id=correlation_id)
        
        return JSONResponse(
            content={
                "error": "Failed to retrieve debug trace context",
                "correlation_id": correlation_id,
                "timestamp": logger._get_timestamp()
            },
            status_code=500
        )

@router.post("/test/alert")
async def trigger_test_alert(
    request: Request,
    severity: str = Query("medium", description="Alert severity"),
    message: str = Query("Test alert", description="Test alert message"),
    alerting: AlertManager = Depends(get_alerting),
    logger: StructuredLogger = Depends(get_logger)
) -> JSONResponse:
    """Trigger a test alert for testing purposes"""
    correlation_id = get_correlation_id()
    
    try:
        # This is a test endpoint - in production, you might want to restrict access
        logger.warning("Test alert triggered via API",
                      severity=severity,
                      message=message,
                      correlation_id=correlation_id,
                      test_alert=True)
        
        response_data = {
            "timestamp": logger._get_timestamp(),
            "correlation_id": correlation_id,
            "service": request.app.state.settings.service_name,
            "status": "success",
            "message": f"Test alert triggered with severity: {severity}"
        }
        
        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error("Failed to trigger test alert",
                    error=str(e),
                    correlation_id=correlation_id)
        
        return JSONResponse(
            content={
                "error": "Failed to trigger test alert",
                "correlation_id": correlation_id,
                "timestamp": logger._get_timestamp()
            },
            status_code=500
        )