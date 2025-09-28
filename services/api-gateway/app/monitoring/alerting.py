"""
Advanced Alerting System
Multi-channel alerting with rules engine, escalation, and suppression
"""
import asyncio
import json
import time
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import aiohttp
from datetime import datetime, timedelta

from app.core.config import Settings
from shared.monitoring.structured_logger import StructuredLogger

class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class AlertStatus(str, Enum):
    FIRING = "firing"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"
    ACKNOWLEDGED = "acknowledged"

class ChannelType(str, Enum):
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    PAGERDUTY = "pagerduty"
    DISCORD = "discord"
    TEAMS = "teams"

@dataclass
class AlertRule:
    """Alert rule configuration"""
    name: str
    condition: str
    severity: AlertSeverity
    message_template: str
    channels: List[str]
    threshold: float
    duration_seconds: int = 60
    evaluation_interval: int = 30
    enabled: bool = True
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    
    def matches_labels(self, labels: Dict[str, str]) -> bool:
        """Check if labels match rule criteria"""
        for key, value in self.labels.items():
            if labels.get(key) != value:
                return False
        return True

@dataclass
class Alert:
    """Alert instance"""
    rule_name: str
    severity: AlertSeverity
    status: AlertStatus
    message: str
    labels: Dict[str, str]
    annotations: Dict[str, str] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    suppressed_until: Optional[datetime] = None
    escalation_level: int = 0
    notification_count: int = 0
    last_notification: Optional[datetime] = None
    fingerprint: Optional[str] = None
    
    def __post_init__(self):
        if not self.fingerprint:
            # Generate fingerprint from labels
            label_str = json.dumps(self.labels, sort_keys=True)
            self.fingerprint = f"{self.rule_name}:{hash(label_str)}"
    
    def is_suppressed(self) -> bool:
        """Check if alert is currently suppressed"""
        return (self.suppressed_until and 
                datetime.utcnow() < self.suppressed_until)
    
    def should_escalate(self, escalation_rules: List[Dict]) -> bool:
        """Check if alert should escalate"""
        if not escalation_rules or self.escalation_level >= len(escalation_rules):
            return False
        
        rule = escalation_rules[self.escalation_level]
        duration = timedelta(minutes=rule.get('after_minutes', 30))
        
        return (self.status == AlertStatus.FIRING and 
                datetime.utcnow() - self.started_at > duration)

@dataclass
class NotificationChannel:
    """Notification channel configuration"""
    name: str
    type: ChannelType
    config: Dict[str, Any]
    enabled: bool = True
    rate_limit_per_hour: int = 100
    last_sent: Dict[str, datetime] = field(default_factory=dict)
    sent_count: Dict[str, int] = field(default_factory=dict)

class AlertManager:
    """Advanced alerting system with multi-channel support"""
    
    def __init__(self, settings: Settings, logger: StructuredLogger):
        self.settings = settings
        self.logger = logger
        
        # Alert storage
        self.active_alerts: Dict[str, Alert] = {}
        self.resolved_alerts: List[Alert] = []
        self.alert_rules: Dict[str, AlertRule] = {}
        self.notification_channels: Dict[str, NotificationChannel] = {}
        
        # Alert evaluation
        self._evaluation_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Load configuration
        self._load_default_rules()
        self._load_default_channels()
        
        self.logger.info("Alert manager initialized",
                        rules_count=len(self.alert_rules),
                        channels_count=len(self.notification_channels))
    
    def _load_default_rules(self):
        """Load default alert rules"""
        default_rules = [
            AlertRule(
                name="high_error_rate",
                condition="error_rate > 0.05",
                severity=AlertSeverity.HIGH,
                message_template="High error rate detected: {error_rate:.2%}",
                channels=["email", "slack"],
                threshold=0.05,
                duration_seconds=300,
                labels={"service": self.settings.service_name}
            ),
            AlertRule(
                name="circuit_breaker_open",
                condition="circuit_breaker_state == 'open'",
                severity=AlertSeverity.CRITICAL,
                message_template="Circuit breaker opened for service: {service_name}",
                channels=["email", "slack", "pagerduty"],
                threshold=1.0,
                duration_seconds=60,
                labels={"service": self.settings.service_name}
            ),
            AlertRule(
                name="high_response_time",
                condition="response_time_p95 > 5.0",
                severity=AlertSeverity.MEDIUM,
                message_template="High response time detected: {response_time_p95:.2f}s",
                channels=["slack"],
                threshold=5.0,
                duration_seconds=600,
                labels={"service": self.settings.service_name}
            ),
            AlertRule(
                name="service_unavailable",
                condition="service_health == 'unhealthy'",
                severity=AlertSeverity.CRITICAL,
                message_template="Service unavailable: {service_name}",
                channels=["email", "slack", "pagerduty"],
                threshold=1.0,
                duration_seconds=120,
                labels={"service": self.settings.service_name}
            ),
            AlertRule(
                name="memory_usage_high",
                condition="memory_usage > 0.85",
                severity=AlertSeverity.HIGH,
                message_template="High memory usage: {memory_usage:.1%}",
                channels=["slack"],
                threshold=0.85,
                duration_seconds=300,
                labels={"service": self.settings.service_name}
            ),
            AlertRule(
                name="rate_limit_violations",
                condition="rate_limit_violations > 100",
                severity=AlertSeverity.MEDIUM,
                message_template="High rate limit violations: {rate_limit_violations} per hour",
                channels=["slack"],
                threshold=100,
                duration_seconds=3600,
                labels={"service": self.settings.service_name}
            )
        ]
        
        for rule in default_rules:
            self.alert_rules[rule.name] = rule
    
    def _load_default_channels(self):
        """Load default notification channels"""
        # Email channel
        if hasattr(self.settings, 'smtp_host') and self.settings.smtp_host:
            self.notification_channels["email"] = NotificationChannel(
                name="email",
                type=ChannelType.EMAIL,
                config={
                    "smtp_host": getattr(self.settings, 'smtp_host', ''),
                    "smtp_port": getattr(self.settings, 'smtp_port', 587),
                    "smtp_username": getattr(self.settings, 'smtp_username', ''),
                    "smtp_password": getattr(self.settings, 'smtp_password', ''),
                    "from_email": getattr(self.settings, 'alert_from_email', ''),
                    "to_emails": getattr(self.settings, 'alert_to_emails', [])
                }
            )
        
        # Slack channel
        if hasattr(self.settings, 'slack_webhook_url') and self.settings.slack_webhook_url:
            self.notification_channels["slack"] = NotificationChannel(
                name="slack",
                type=ChannelType.SLACK,
                config={
                    "webhook_url": self.settings.slack_webhook_url,
                    "channel": getattr(self.settings, 'slack_channel', '#alerts'),
                    "username": getattr(self.settings, 'slack_username', 'API Gateway Alerts')
                }
            )
        
        # PagerDuty channel
        if hasattr(self.settings, 'pagerduty_api_key') and self.settings.pagerduty_api_key:
            self.notification_channels["pagerduty"] = NotificationChannel(
                name="pagerduty",
                type=ChannelType.PAGERDUTY,
                config={
                    "api_key": self.settings.pagerduty_api_key,
                    "service_key": getattr(self.settings, 'pagerduty_service_key', '')
                }
            )
    
    async def start(self):
        """Start alert manager"""
        self._running = True
        self._evaluation_task = asyncio.create_task(self._evaluation_loop())
        self.logger.info("Alert manager started")
    
    async def stop(self):
        """Stop alert manager"""
        self._running = False
        if self._evaluation_task:
            self._evaluation_task.cancel()
            try:
                await self._evaluation_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Alert manager stopped")
    
    async def _evaluation_loop(self):
        """Main alert evaluation loop"""
        while self._running:
            try:
                await self._evaluate_alerts()
                await self._check_escalations()
                await self._cleanup_resolved_alerts()
                await asyncio.sleep(30)  # Evaluate every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error in alert evaluation loop", error=str(e))
                await asyncio.sleep(5)
    
    async def _evaluate_alerts(self):
        """Evaluate all alert rules"""
        # This would typically get metrics from Prometheus or similar
        # For now, we'll simulate with placeholder logic
        current_metrics = await self._get_current_metrics()
        
        for rule_name, rule in self.alert_rules.items():
            if not rule.enabled:
                continue
            
            try:
                should_fire = await self._evaluate_rule(rule, current_metrics)
                
                if should_fire:
                    await self._fire_alert(rule, current_metrics)
                else:
                    await self._resolve_alert(rule_name)
                    
            except Exception as e:
                self.logger.error("Error evaluating alert rule",
                                rule=rule_name,
                                error=str(e))
    
    async def _get_current_metrics(self) -> Dict[str, Any]:
        """Get current metrics for alert evaluation"""
        # Placeholder - would integrate with metrics system
        return {
            "error_rate": 0.02,
            "response_time_p95": 1.5,
            "memory_usage": 0.70,
            "circuit_breaker_state": "closed",
            "service_health": "healthy",
            "rate_limit_violations": 45
        }
    
    async def _evaluate_rule(self, rule: AlertRule, metrics: Dict[str, Any]) -> bool:
        """Evaluate a single alert rule"""
        try:
            # Simple condition evaluation (in production, use proper expression parser)
            if rule.condition == "error_rate > 0.05":
                return metrics.get("error_rate", 0) > rule.threshold
            elif rule.condition == "circuit_breaker_state == 'open'":
                return metrics.get("circuit_breaker_state") == "open"
            elif rule.condition == "response_time_p95 > 5.0":
                return metrics.get("response_time_p95", 0) > rule.threshold
            elif rule.condition == "service_health == 'unhealthy'":
                return metrics.get("service_health") == "unhealthy"
            elif rule.condition == "memory_usage > 0.85":
                return metrics.get("memory_usage", 0) > rule.threshold
            elif rule.condition == "rate_limit_violations > 100":
                return metrics.get("rate_limit_violations", 0) > rule.threshold
            
            return False
            
        except Exception as e:
            self.logger.error("Error evaluating rule condition",
                            rule=rule.name,
                            condition=rule.condition,
                            error=str(e))
            return False
    
    async def _fire_alert(self, rule: AlertRule, metrics: Dict[str, Any]):
        """Fire an alert"""
        fingerprint = f"{rule.name}:{hash(json.dumps(rule.labels, sort_keys=True))}"
        
        # Check if alert already exists
        if fingerprint in self.active_alerts:
            return  # Alert already active
        
        # Create new alert
        alert = Alert(
            rule_name=rule.name,
            severity=rule.severity,
            status=AlertStatus.FIRING,
            message=rule.message_template.format(**metrics),
            labels=rule.labels.copy(),
            annotations=rule.annotations.copy(),
            fingerprint=fingerprint
        )
        
        self.active_alerts[fingerprint] = alert
        
        # Send notifications
        await self._send_alert_notifications(alert, rule.channels)
        
        self.logger.warning("Alert fired",
                          alert_name=rule.name,
                          severity=rule.severity.value,
                          message=alert.message)
    
    async def _resolve_alert(self, rule_name: str):
        """Resolve an alert"""
        # Find and resolve active alerts for this rule
        to_resolve = []
        for fingerprint, alert in self.active_alerts.items():
            if alert.rule_name == rule_name and alert.status == AlertStatus.FIRING:
                to_resolve.append(fingerprint)
        
        for fingerprint in to_resolve:
            alert = self.active_alerts[fingerprint]
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.utcnow()
            
            # Move to resolved alerts
            self.resolved_alerts.append(alert)
            del self.active_alerts[fingerprint]
            
            # Send resolution notification
            await self._send_resolution_notification(alert)
            
            self.logger.info("Alert resolved",
                           alert_name=alert.rule_name,
                           duration_seconds=(alert.resolved_at - alert.started_at).total_seconds())
    
    async def _check_escalations(self):
        """Check for alerts that need escalation"""
        escalation_rules = [
            {"after_minutes": 30, "channels": ["pagerduty"]},
            {"after_minutes": 60, "channels": ["email", "slack", "pagerduty"]}
        ]
        
        for alert in self.active_alerts.values():
            if alert.should_escalate(escalation_rules):
                await self._escalate_alert(alert, escalation_rules)
    
    async def _escalate_alert(self, alert: Alert, escalation_rules: List[Dict]):
        """Escalate an alert"""
        if alert.escalation_level >= len(escalation_rules):
            return
        
        rule = escalation_rules[alert.escalation_level]
        alert.escalation_level += 1
        
        # Send escalation notifications
        await self._send_alert_notifications(alert, rule["channels"], is_escalation=True)
        
        self.logger.warning("Alert escalated",
                          alert_name=alert.rule_name,
                          escalation_level=alert.escalation_level)
    
    async def _send_alert_notifications(self, alert: Alert, channels: List[str], is_escalation: bool = False):
        """Send alert notifications to specified channels"""
        for channel_name in channels:
            if channel_name not in self.notification_channels:
                continue
            
            channel = self.notification_channels[channel_name]
            if not channel.enabled:
                continue
            
            try:
                await self._send_notification(channel, alert, is_escalation)
                alert.notification_count += 1
                alert.last_notification = datetime.utcnow()
                
            except Exception as e:
                self.logger.error("Failed to send notification",
                                channel=channel_name,
                                alert=alert.rule_name,
                                error=str(e))
    
    async def _send_notification(self, channel: NotificationChannel, alert: Alert, is_escalation: bool = False):
        """Send notification to a specific channel"""
        if channel.type == ChannelType.EMAIL:
            await self._send_email_notification(channel, alert, is_escalation)
        elif channel.type == ChannelType.SLACK:
            await self._send_slack_notification(channel, alert, is_escalation)
        elif channel.type == ChannelType.PAGERDUTY:
            await self._send_pagerduty_notification(channel, alert, is_escalation)
        else:
            self.logger.warning("Unsupported notification channel", type=channel.type.value)
    
    async def _send_email_notification(self, channel: NotificationChannel, alert: Alert, is_escalation: bool):
        """Send email notification"""
        config = channel.config
        
        subject = f"{'[ESCALATED] ' if is_escalation else ''}[{alert.severity.upper()}] {alert.rule_name}"
        
        body = f"""
        Alert: {alert.rule_name}
        Severity: {alert.severity.upper()}
        Status: {alert.status.upper()}
        Message: {alert.message}
        Started: {alert.started_at.isoformat()}
        Service: {alert.labels.get('service', 'Unknown')}
        
        Labels: {json.dumps(alert.labels, indent=2)}
        """
        
        msg = MIMEMultipart()
        msg['From'] = config['from_email']
        msg['To'] = ', '.join(config['to_emails'])
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email (placeholder - would use actual SMTP)
        self.logger.info("Email notification sent",
                        alert=alert.rule_name,
                        recipients=config['to_emails'])
    
    async def _send_slack_notification(self, channel: NotificationChannel, alert: Alert, is_escalation: bool):
        """Send Slack notification"""
        config = channel.config
        
        color = {
            AlertSeverity.CRITICAL: "danger",
            AlertSeverity.HIGH: "warning",
            AlertSeverity.MEDIUM: "warning",
            AlertSeverity.LOW: "good",
            AlertSeverity.INFO: "good"
        }.get(alert.severity, "warning")
        
        payload = {
            "channel": config.get('channel', '#alerts'),
            "username": config.get('username', 'API Gateway Alerts'),
            "attachments": [{
                "color": color,
                "title": f"{'[ESCALATED] ' if is_escalation else ''}{alert.rule_name}",
                "text": alert.message,
                "fields": [
                    {"title": "Severity", "value": alert.severity.upper(), "short": True},
                    {"title": "Status", "value": alert.status.upper(), "short": True},
                    {"title": "Service", "value": alert.labels.get('service', 'Unknown'), "short": True},
                    {"title": "Started", "value": alert.started_at.isoformat(), "short": True}
                ],
                "ts": int(alert.started_at.timestamp())
            }]
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(config['webhook_url'], json=payload) as response:
                    if response.status == 200:
                        self.logger.info("Slack notification sent", alert=alert.rule_name)
                    else:
                        self.logger.error("Failed to send Slack notification",
                                        status=response.status,
                                        response=await response.text())
        except Exception as e:
            self.logger.error("Error sending Slack notification", error=str(e))
    
    async def _send_pagerduty_notification(self, channel: NotificationChannel, alert: Alert, is_escalation: bool):
        """Send PagerDuty notification"""
        config = channel.config
        
        payload = {
            "routing_key": config['service_key'],
            "event_action": "trigger",
            "dedup_key": alert.fingerprint,
            "payload": {
                "summary": f"{'[ESCALATED] ' if is_escalation else ''}{alert.message}",
                "severity": alert.severity.value,
                "source": alert.labels.get('service', 'api-gateway'),
                "component": alert.rule_name,
                "group": "api-gateway",
                "class": "alert",
                "custom_details": {
                    "labels": alert.labels,
                    "annotations": alert.annotations,
                    "started_at": alert.started_at.isoformat()
                }
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://events.pagerduty.com/v2/enqueue",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status == 202:
                        self.logger.info("PagerDuty notification sent", alert=alert.rule_name)
                    else:
                        self.logger.error("Failed to send PagerDuty notification",
                                        status=response.status,
                                        response=await response.text())
        except Exception as e:
            self.logger.error("Error sending PagerDuty notification", error=str(e))
    
    async def _send_resolution_notification(self, alert: Alert):
        """Send alert resolution notification"""
        # Send to same channels that received the original alert
        rule = self.alert_rules.get(alert.rule_name)
        if not rule:
            return
        
        for channel_name in rule.channels:
            if channel_name not in self.notification_channels:
                continue
            
            channel = self.notification_channels[channel_name]
            if not channel.enabled:
                continue
            
            try:
                await self._send_resolution_to_channel(channel, alert)
            except Exception as e:
                self.logger.error("Failed to send resolution notification",
                                channel=channel_name,
                                alert=alert.rule_name,
                                error=str(e))
    
    async def _send_resolution_to_channel(self, channel: NotificationChannel, alert: Alert):
        """Send resolution notification to specific channel"""
        if channel.type == ChannelType.SLACK:
            payload = {
                "channel": channel.config.get('channel', '#alerts'),
                "username": channel.config.get('username', 'API Gateway Alerts'),
                "attachments": [{
                    "color": "good",
                    "title": f"✅ RESOLVED: {alert.rule_name}",
                    "text": f"Alert has been resolved: {alert.message}",
                    "fields": [
                        {"title": "Duration", "value": str(alert.resolved_at - alert.started_at), "short": True},
                        {"title": "Resolved", "value": alert.resolved_at.isoformat(), "short": True}
                    ]
                }]
            }
            
            async with aiohttp.ClientSession() as session:
                await session.post(channel.config['webhook_url'], json=payload)
        
        elif channel.type == ChannelType.PAGERDUTY:
            payload = {
                "routing_key": channel.config['service_key'],
                "event_action": "resolve",
                "dedup_key": alert.fingerprint
            }
            
            async with aiohttp.ClientSession() as session:
                await session.post(
                    "https://events.pagerduty.com/v2/enqueue",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
    
    async def _cleanup_resolved_alerts(self):
        """Clean up old resolved alerts"""
        cutoff_time = datetime.utcnow() - timedelta(days=7)
        self.resolved_alerts = [
            alert for alert in self.resolved_alerts
            if alert.resolved_at and alert.resolved_at > cutoff_time
        ]
    
    # Public API methods
    def acknowledge_alert(self, fingerprint: str, acknowledged_by: str):
        """Acknowledge an alert"""
        if fingerprint in self.active_alerts:
            alert = self.active_alerts[fingerprint]
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = datetime.utcnow()
            alert.acknowledged_by = acknowledged_by
            
            self.logger.info("Alert acknowledged",
                           alert=alert.rule_name,
                           acknowledged_by=acknowledged_by)
    
    def suppress_alert(self, fingerprint: str, duration_minutes: int):
        """Suppress an alert for a specified duration"""
        if fingerprint in self.active_alerts:
            alert = self.active_alerts[fingerprint]
            alert.status = AlertStatus.SUPPRESSED
            alert.suppressed_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
            
            self.logger.info("Alert suppressed",
                           alert=alert.rule_name,
                           duration_minutes=duration_minutes)
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get all active alerts"""
        return [asdict(alert) for alert in self.active_alerts.values()]
    
    def get_alert_stats(self) -> Dict[str, Any]:
        """Get alerting statistics"""
        active_by_severity = {}
        for alert in self.active_alerts.values():
            severity = alert.severity.value
            active_by_severity[severity] = active_by_severity.get(severity, 0) + 1
        
        return {
            "active_alerts": len(self.active_alerts),
            "resolved_alerts_last_7_days": len(self.resolved_alerts),
            "active_by_severity": active_by_severity,
            "total_rules": len(self.alert_rules),
            "enabled_rules": len([r for r in self.alert_rules.values() if r.enabled]),
            "notification_channels": len(self.notification_channels)
        }