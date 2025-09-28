"""
Monitoring and Alerting Configuration
Production monitoring, alerting, and observability setup for Azure resources
"""
import asyncio
import json
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

try:
    from shared.monitoring.structured_logger import StructuredLogger
    from shared.monitoring.correlation import get_correlation_id
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger
    
    def get_correlation_id():
        import uuid
        return str(uuid.uuid4())[:8]


class AlertSeverity(Enum):
    """Alert severity levels"""
    CRITICAL = 0
    ERROR = 1  
    WARNING = 2
    INFORMATIONAL = 3


class AlertFrequency(Enum):
    """Alert evaluation frequency"""
    PT1M = "PT1M"   # Every 1 minute
    PT5M = "PT5M"   # Every 5 minutes
    PT15M = "PT15M" # Every 15 minutes
    PT30M = "PT30M" # Every 30 minutes
    PT1H = "PT1H"   # Every 1 hour


class MetricAggregation(Enum):
    """Metric aggregation types"""
    AVERAGE = "Average"
    MINIMUM = "Minimum"
    MAXIMUM = "Maximum"
    TOTAL = "Total"
    COUNT = "Count"


@dataclass
class AlertRule:
    """Configuration for an alert rule"""
    name: str
    description: str
    severity: AlertSeverity
    metric_name: str
    aggregation: MetricAggregation
    operator: str  # GreaterThan, LessThan, GreaterThanOrEqual, LessThanOrEqual
    threshold: float
    evaluation_frequency: AlertFrequency
    window_size: str  # PT5M, PT15M, PT30M, PT1H, etc.
    resource_type: str
    enabled: bool = True
    action_groups: List[str] = field(default_factory=list)
    dimensions: Dict[str, str] = field(default_factory=dict)
    
    def to_arm_resource(self, resource_prefix: str) -> Dict[str, Any]:
        """Convert to ARM template resource"""
        return {
            "type": "Microsoft.Insights/metricAlerts",
            "apiVersion": "2018-03-01",
            "name": f"{resource_prefix}-alert-{self.name}",
            "location": "global",
            "properties": {
                "description": self.description,
                "severity": self.severity.value,
                "enabled": self.enabled,
                "scopes": [
                    f"[resourceId('{self.resource_type}', concat(variables('resourcePrefix'), '-', variables('resourceSuffix')))]"
                ],
                "evaluationFrequency": self.evaluation_frequency.value,
                "windowSize": self.window_size,
                "criteria": {
                    "odata.type": "Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria",
                    "allOf": [
                        {
                            "name": f"{self.name}-criteria",
                            "metricName": self.metric_name,
                            "operator": self.operator,
                            "threshold": self.threshold,
                            "timeAggregation": self.aggregation.value,
                            "dimensions": [
                                {"name": key, "operator": "Include", "values": [value]}
                                for key, value in self.dimensions.items()
                            ]
                        }
                    ]
                },
                "actions": [
                    {"actionGroupId": f"[resourceId('Microsoft.Insights/actionGroups', '{ag}')]"}
                    for ag in self.action_groups
                ]
            }
        }


@dataclass
class ActionGroup:
    """Configuration for alert action group"""
    name: str
    short_name: str
    email_receivers: List[str] = field(default_factory=list)
    sms_receivers: List[Dict[str, str]] = field(default_factory=list)
    webhook_receivers: List[Dict[str, str]] = field(default_factory=list)
    logic_apps: List[Dict[str, str]] = field(default_factory=list)
    enabled: bool = True
    
    def to_arm_resource(self, resource_prefix: str) -> Dict[str, Any]:
        """Convert to ARM template resource"""
        return {
            "type": "Microsoft.Insights/actionGroups",
            "apiVersion": "2021-09-01",
            "name": f"{resource_prefix}-actiongroup-{self.name}",
            "location": "global",
            "properties": {
                "groupShortName": self.short_name,
                "enabled": self.enabled,
                "emailReceivers": [
                    {
                        "name": f"email-{i}",
                        "emailAddress": email,
                        "useCommonAlertSchema": True
                    }
                    for i, email in enumerate(self.email_receivers)
                ],
                "smsReceivers": [
                    {
                        "name": receiver["name"],
                        "countryCode": receiver.get("country_code", "1"),
                        "phoneNumber": receiver["phone_number"]
                    }
                    for receiver in self.sms_receivers
                ],
                "webhookReceivers": [
                    {
                        "name": receiver["name"],
                        "serviceUri": receiver["url"],
                        "useCommonAlertSchema": True
                    }
                    for receiver in self.webhook_receivers
                ],
                "logicAppReceivers": [
                    {
                        "name": app["name"],
                        "resourceId": app["resource_id"],
                        "callbackUrl": app["callback_url"],
                        "useCommonAlertSchema": True
                    }
                    for app in self.logic_apps
                ]
            }
        }


@dataclass
class DashboardConfig:
    """Configuration for monitoring dashboard"""
    name: str
    title: str
    tiles: List[Dict[str, Any]] = field(default_factory=list)
    refresh_interval: int = 300  # seconds
    time_range: str = "PT4H"  # 4 hours
    
    def add_metric_tile(self, title: str, metric_name: str, resource_type: str, 
                       aggregation: str = "Average", position: Dict[str, int] = None):
        """Add a metric tile to the dashboard"""
        if position is None:
            position = {"x": 0, "y": len(self.tiles), "width": 6, "height": 4}
        
        tile = {
            "name": f"tile-{len(self.tiles)}",
            "tileType": "Extension/HubsExtension/PartType/MonitorChartPart",
            "position": position,
            "metadata": {
                "inputs": [
                    {
                        "name": "options",
                        "value": {
                            "chart": {
                                "metrics": [
                                    {
                                        "resourceMetadata": {
                                            "resourceType": resource_type
                                        },
                                        "name": metric_name,
                                        "aggregationType": aggregation,
                                        "namespace": "microsoft.web/sites"
                                    }
                                ],
                                "title": title,
                                "titleKind": 1,
                                "visualization": {
                                    "chartType": 2
                                }
                            }
                        }
                    }
                ]
            }
        }
        self.tiles.append(tile)


class MonitoringManager:
    """Azure monitoring and alerting configuration manager"""
    
    def __init__(self, logger: Optional[StructuredLogger] = None):
        self.logger = logger or StructuredLogger()
        
        # Alert configurations
        self.alert_rules: List[AlertRule] = []
        self.action_groups: List[ActionGroup] = []
        self.dashboards: List[DashboardConfig] = []
        
        # Initialize default configurations
        self._initialize_default_alerts()
        self._initialize_default_action_groups()
        self._initialize_default_dashboards()
    
    def _initialize_default_alerts(self):
        """Initialize default alert rules"""
        
        # App Service alerts
        self.alert_rules.extend([
            AlertRule(
                name="high-cpu-usage",
                description="App Service CPU usage is high",
                severity=AlertSeverity.WARNING,
                metric_name="CpuPercentage",
                aggregation=MetricAggregation.AVERAGE,
                operator="GreaterThan",
                threshold=80.0,
                evaluation_frequency=AlertFrequency.PT5M,
                window_size="PT15M",
                resource_type="Microsoft.Web/sites",
                action_groups=["critical-alerts", "operations-team"]
            ),
            AlertRule(
                name="high-memory-usage",
                description="App Service memory usage is high",
                severity=AlertSeverity.WARNING,
                metric_name="MemoryPercentage",
                aggregation=MetricAggregation.AVERAGE,
                operator="GreaterThan",
                threshold=85.0,
                evaluation_frequency=AlertFrequency.PT5M,
                window_size="PT15M",
                resource_type="Microsoft.Web/sites",
                action_groups=["critical-alerts", "operations-team"]
            ),
            AlertRule(
                name="high-response-time",
                description="App Service response time is high",
                severity=AlertSeverity.ERROR,
                metric_name="AverageResponseTime",
                aggregation=MetricAggregation.AVERAGE,
                operator="GreaterThan",
                threshold=5.0,  # 5 seconds
                evaluation_frequency=AlertFrequency.PT1M,
                window_size="PT5M",
                resource_type="Microsoft.Web/sites",
                action_groups=["critical-alerts"]
            ),
            AlertRule(
                name="high-error-rate",
                description="App Service error rate is high",
                severity=AlertSeverity.CRITICAL,
                metric_name="Http5xx",
                aggregation=MetricAggregation.TOTAL,
                operator="GreaterThan",
                threshold=10.0,
                evaluation_frequency=AlertFrequency.PT1M,
                window_size="PT5M",
                resource_type="Microsoft.Web/sites",
                action_groups=["critical-alerts", "operations-team", "development-team"]
            )
        ])
        
        # Cosmos DB alerts
        self.alert_rules.extend([
            AlertRule(
                name="cosmos-high-ru-consumption",
                description="Cosmos DB RU consumption is high",
                severity=AlertSeverity.WARNING,
                metric_name="TotalRequestUnits",
                aggregation=MetricAggregation.TOTAL,
                operator="GreaterThan",
                threshold=3500.0,  # 3500 RU out of 4000
                evaluation_frequency=AlertFrequency.PT5M,
                window_size="PT15M",
                resource_type="Microsoft.DocumentDB/databaseAccounts",
                action_groups=["operations-team"]
            ),
            AlertRule(
                name="cosmos-throttling",
                description="Cosmos DB requests are being throttled",
                severity=AlertSeverity.ERROR,
                metric_name="TotalRequests",
                aggregation=MetricAggregation.COUNT,
                operator="GreaterThan",
                threshold=0,
                evaluation_frequency=AlertFrequency.PT1M,
                window_size="PT5M",
                resource_type="Microsoft.DocumentDB/databaseAccounts",
                dimensions={"StatusCode": "429"},
                action_groups=["critical-alerts", "operations-team"]
            ),
            AlertRule(
                name="cosmos-availability",
                description="Cosmos DB availability is low",
                severity=AlertSeverity.CRITICAL,
                metric_name="ServiceAvailability",
                aggregation=MetricAggregation.AVERAGE,
                operator="LessThan",
                threshold=99.0,  # Less than 99% availability
                evaluation_frequency=AlertFrequency.PT5M,
                window_size="PT15M",
                resource_type="Microsoft.DocumentDB/databaseAccounts",
                action_groups=["critical-alerts", "operations-team", "development-team"]
            )
        ])
        
        # Redis Cache alerts
        self.alert_rules.extend([
            AlertRule(
                name="redis-high-cpu",
                description="Redis Cache CPU usage is high",
                severity=AlertSeverity.WARNING,
                metric_name="percentProcessorTime",
                aggregation=MetricAggregation.AVERAGE,
                operator="GreaterThan",
                threshold=80.0,
                evaluation_frequency=AlertFrequency.PT5M,
                window_size="PT15M",
                resource_type="Microsoft.Cache/Redis",
                action_groups=["operations-team"]
            ),
            AlertRule(
                name="redis-high-memory",
                description="Redis Cache memory usage is high",
                severity=AlertSeverity.WARNING,
                metric_name="usedmemorypercentage",
                aggregation=MetricAggregation.AVERAGE,
                operator="GreaterThan",
                threshold=85.0,
                evaluation_frequency=AlertFrequency.PT5M,
                window_size="PT15M",
                resource_type="Microsoft.Cache/Redis",
                action_groups=["operations-team"]
            ),
            AlertRule(
                name="redis-connection-errors",
                description="Redis Cache connection errors detected",
                severity=AlertSeverity.ERROR,
                metric_name="errors",
                aggregation=MetricAggregation.MAXIMUM,
                operator="GreaterThan",
                threshold=5.0,
                evaluation_frequency=AlertFrequency.PT1M,
                window_size="PT5M",
                resource_type="Microsoft.Cache/Redis",
                dimensions={"ErrorType": "Failover"},
                action_groups=["critical-alerts", "operations-team"]
            )
        ])
        
        # Application Insights alerts
        self.alert_rules.extend([
            AlertRule(
                name="application-exceptions",
                description="High number of application exceptions",
                severity=AlertSeverity.ERROR,
                metric_name="exceptions/count",
                aggregation=MetricAggregation.COUNT,
                operator="GreaterThan",
                threshold=20.0,
                evaluation_frequency=AlertFrequency.PT5M,
                window_size="PT15M",
                resource_type="Microsoft.Insights/components",
                action_groups=["development-team", "operations-team"]
            ),
            AlertRule(
                name="dependency-failures",
                description="High number of dependency failures",
                severity=AlertSeverity.WARNING,
                metric_name="dependencies/failed",
                aggregation=MetricAggregation.COUNT,
                operator="GreaterThan",
                threshold=10.0,
                evaluation_frequency=AlertFrequency.PT5M,
                window_size="PT15M",
                resource_type="Microsoft.Insights/components",
                action_groups=["development-team"]
            )
        ])
    
    def _initialize_default_action_groups(self):
        """Initialize default action groups"""
        
        self.action_groups = [
            ActionGroup(
                name="critical-alerts",
                short_name="Critical",
                email_receivers=[
                    "ops-team@company.com",
                    "on-call@company.com"
                ],
                sms_receivers=[
                    {"name": "ops-manager", "phone_number": "+1234567890"}
                ],
                webhook_receivers=[
                    {
                        "name": "slack-critical",
                        "url": "${SLACK_WEBHOOK_CRITICAL}"
                    },
                    {
                        "name": "pagerduty",
                        "url": "${PAGERDUTY_WEBHOOK}"
                    }
                ]
            ),
            ActionGroup(
                name="operations-team",
                short_name="OpsTeam",
                email_receivers=[
                    "ops-team@company.com",
                    "infrastructure@company.com"
                ],
                webhook_receivers=[
                    {
                        "name": "slack-ops",
                        "url": "${SLACK_WEBHOOK_OPS}"
                    }
                ]
            ),
            ActionGroup(
                name="development-team",
                short_name="DevTeam",
                email_receivers=[
                    "dev-team@company.com",
                    "backend-team@company.com"
                ],
                webhook_receivers=[
                    {
                        "name": "slack-dev",
                        "url": "${SLACK_WEBHOOK_DEV}"
                    }
                ]
            )
        ]
    
    def _initialize_default_dashboards(self):
        """Initialize default monitoring dashboards"""
        
        # Main system dashboard
        main_dashboard = DashboardConfig(
            name="system-overview",
            title="Screenshot-to-Code System Overview",
            refresh_interval=300,
            time_range="PT4H"
        )
        
        # Add tiles to main dashboard
        main_dashboard.add_metric_tile("CPU Usage", "CpuPercentage", "Microsoft.Web/sites", "Average", {"x": 0, "y": 0, "width": 6, "height": 4})
        main_dashboard.add_metric_tile("Memory Usage", "MemoryPercentage", "Microsoft.Web/sites", "Average", {"x": 6, "y": 0, "width": 6, "height": 4})
        main_dashboard.add_metric_tile("Response Time", "AverageResponseTime", "Microsoft.Web/sites", "Average", {"x": 0, "y": 4, "width": 6, "height": 4})
        main_dashboard.add_metric_tile("Request Count", "Requests", "Microsoft.Web/sites", "Total", {"x": 6, "y": 4, "width": 6, "height": 4})
        main_dashboard.add_metric_tile("Error Rate", "Http5xx", "Microsoft.Web/sites", "Total", {"x": 0, "y": 8, "width": 6, "height": 4})
        main_dashboard.add_metric_tile("Cosmos RU Usage", "TotalRequestUnits", "Microsoft.DocumentDB/databaseAccounts", "Total", {"x": 6, "y": 8, "width": 6, "height": 4})
        
        self.dashboards.append(main_dashboard)
        
        # Performance dashboard
        perf_dashboard = DashboardConfig(
            name="performance-metrics",
            title="Performance Metrics Dashboard",
            refresh_interval=60,
            time_range="PT1H"
        )
        
        perf_dashboard.add_metric_tile("App Service CPU", "CpuPercentage", "Microsoft.Web/sites", "Average")
        perf_dashboard.add_metric_tile("App Service Memory", "MemoryPercentage", "Microsoft.Web/sites", "Average")
        perf_dashboard.add_metric_tile("Redis CPU", "percentProcessorTime", "Microsoft.Cache/Redis", "Average")
        perf_dashboard.add_metric_tile("Redis Memory", "usedmemorypercentage", "Microsoft.Cache/Redis", "Average")
        
        self.dashboards.append(perf_dashboard)
    
    def add_custom_alert(self, alert_rule: AlertRule):
        """Add a custom alert rule"""
        self.alert_rules.append(alert_rule)
        self.logger.info(
            "Custom alert rule added",
            name=alert_rule.name,
            severity=alert_rule.severity.name,
            metric=alert_rule.metric_name
        )
    
    def add_custom_action_group(self, action_group: ActionGroup):
        """Add a custom action group"""
        self.action_groups.append(action_group)
        self.logger.info(
            "Custom action group added",
            name=action_group.name,
            email_count=len(action_group.email_receivers),
            webhook_count=len(action_group.webhook_receivers)
        )
    
    async def generate_monitoring_arm_template(self, resource_prefix: str) -> Dict[str, Any]:
        """Generate ARM template for monitoring resources"""
        
        correlation_id = get_correlation_id()
        
        template = {
            "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
            "contentVersion": "1.0.0.0",
            "parameters": {
                "resourcePrefix": {
                    "type": "string",
                    "defaultValue": resource_prefix
                }
            },
            "variables": {
                "resourcePrefix": "[parameters('resourcePrefix')]"
            },
            "resources": [],
            "outputs": {}
        }
        
        # Add action groups
        for action_group in self.action_groups:
            template["resources"].append(action_group.to_arm_resource(resource_prefix))
        
        # Add alert rules (after action groups)
        for alert_rule in self.alert_rules:
            alert_resource = alert_rule.to_arm_resource(resource_prefix)
            # Add dependency on action groups
            alert_resource["dependsOn"] = [
                f"[resourceId('Microsoft.Insights/actionGroups', '{resource_prefix}-actiongroup-{ag}')]"
                for ag in alert_rule.action_groups
            ]
            template["resources"].append(alert_resource)
        
        # Add Log Analytics workspace queries
        log_queries = await self._generate_log_queries()
        for query in log_queries:
            template["resources"].append(query)
        
        self.logger.info(
            "Monitoring ARM template generated",
            action_groups=len(self.action_groups),
            alert_rules=len(self.alert_rules),
            log_queries=len(log_queries),
            correlation_id=correlation_id
        )
        
        return template
    
    async def _generate_log_queries(self) -> List[Dict[str, Any]]:
        """Generate saved Log Analytics queries"""
        
        queries = [
            {
                "type": "Microsoft.OperationalInsights/workspaces/savedSearches",
                "apiVersion": "2020-08-01",
                "name": "[concat(variables('resourcePrefix'), '-workspace/error-analysis')]",
                "properties": {
                    "displayName": "Error Analysis",
                    "category": "Application",
                    "query": """
                        AppExceptions
                        | where TimeGenerated > ago(1h)
                        | summarize count() by Type, bin(TimeGenerated, 5m)
                        | order by TimeGenerated desc
                    """,
                    "tags": [
                        {"name": "Group", "value": "Application Monitoring"}
                    ]
                }
            },
            {
                "type": "Microsoft.OperationalInsights/workspaces/savedSearches",
                "apiVersion": "2020-08-01",
                "name": "[concat(variables('resourcePrefix'), '-workspace/performance-trends')]",
                "properties": {
                    "displayName": "Performance Trends",
                    "category": "Performance",
                    "query": """
                        AppRequests
                        | where TimeGenerated > ago(4h)
                        | summarize 
                            avg(DurationMs),
                            percentile(DurationMs, 95),
                            count()
                        by bin(TimeGenerated, 10m)
                        | order by TimeGenerated desc
                    """,
                    "tags": [
                        {"name": "Group", "value": "Performance Monitoring"}
                    ]
                }
            },
            {
                "type": "Microsoft.OperationalInsights/workspaces/savedSearches",
                "apiVersion": "2020-08-01",
                "name": "[concat(variables('resourcePrefix'), '-workspace/dependency-failures')]",
                "properties": {
                    "displayName": "Dependency Failures",
                    "category": "Dependencies",
                    "query": """
                        AppDependencies
                        | where TimeGenerated > ago(1h)
                        | where Success == false
                        | summarize count() by Type, Target, bin(TimeGenerated, 5m)
                        | order by count_ desc
                    """,
                    "tags": [
                        {"name": "Group", "value": "Dependency Monitoring"}
                    ]
                }
            }
        ]
        
        return queries
    
    async def create_workbook_template(self) -> Dict[str, Any]:
        """Create Azure Workbook template for comprehensive monitoring"""
        
        workbook = {
            "type": "Microsoft.Insights/workbooks",
            "apiVersion": "2021-08-01",
            "name": "[guid(resourceGroup().id, 'screenshot-to-code-workbook')]",
            "location": "[resourceGroup().location]",
            "kind": "shared",
            "properties": {
                "displayName": "Screenshot-to-Code System Monitoring",
                "serializedData": json.dumps({
                    "version": "Notebook/1.0",
                    "items": [
                        {
                            "type": 1,
                            "content": {
                                "json": "# Screenshot-to-Code System Monitoring\n\nComprehensive monitoring dashboard for the Screenshot-to-Code production system."
                            }
                        },
                        {
                            "type": 3,
                            "content": {
                                "version": "KqlItem/1.0",
                                "query": """
                                    AppRequests
                                    | where TimeGenerated > ago(1h)
                                    | summarize 
                                        Requests = count(),
                                        ['Avg Duration'] = avg(DurationMs),
                                        ['95th Percentile'] = percentile(DurationMs, 95),
                                        ['Success Rate'] = avg(case(Success == true, 100.0, 0.0))
                                    | project 
                                        Requests,
                                        ['Avg Duration (ms)'] = round(['Avg Duration'], 2),
                                        ['95th Percentile (ms)'] = round(['95th Percentile'], 2),
                                        ['Success Rate (%)'] = round(['Success Rate'], 2)
                                """,
                                "size": 0,
                                "title": "Request Overview (Last Hour)",
                                "queryType": 0,
                                "visualization": "table"
                            }
                        },
                        {
                            "type": 3,
                            "content": {
                                "version": "KqlItem/1.0",
                                "query": """
                                    AppRequests
                                    | where TimeGenerated > ago(4h)
                                    | summarize 
                                        count(),
                                        avg(DurationMs)
                                    by bin(TimeGenerated, 10m)
                                    | render timechart
                                """,
                                "size": 0,
                                "title": "Request Volume and Response Time Trends",
                                "queryType": 0,
                                "visualization": "timechart"
                            }
                        },
                        {
                            "type": 3,
                            "content": {
                                "version": "KqlItem/1.0",
                                "query": """
                                    AppExceptions
                                    | where TimeGenerated > ago(1h)
                                    | summarize count() by Type
                                    | order by count_ desc
                                    | limit 10
                                """,
                                "size": 0,
                                "title": "Top Exceptions (Last Hour)",
                                "queryType": 0,
                                "visualization": "barchart"
                            }
                        }
                    ]
                }, separators=(',', ':'))
            }
        }
        
        return workbook
    
    def get_monitoring_summary(self) -> Dict[str, Any]:
        """Get monitoring configuration summary"""
        
        return {
            "alert_rules": {
                "total": len(self.alert_rules),
                "by_severity": {
                    severity.name: len([rule for rule in self.alert_rules if rule.severity == severity])
                    for severity in AlertSeverity
                },
                "by_resource_type": {
                    resource_type: len([rule for rule in self.alert_rules if rule.resource_type == resource_type])
                    for resource_type in set(rule.resource_type for rule in self.alert_rules)
                }
            },
            "action_groups": {
                "total": len(self.action_groups),
                "total_email_receivers": sum(len(ag.email_receivers) for ag in self.action_groups),
                "total_webhook_receivers": sum(len(ag.webhook_receivers) for ag in self.action_groups)
            },
            "dashboards": {
                "total": len(self.dashboards),
                "names": [dashboard.name for dashboard in self.dashboards]
            }
        }
    
    async def validate_monitoring_config(self) -> Dict[str, Any]:
        """Validate monitoring configuration"""
        
        validation_results = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "recommendations": []
        }
        
        # Validate alert rules
        for rule in self.alert_rules:
            if not rule.action_groups:
                validation_results["warnings"].append(
                    f"Alert rule '{rule.name}' has no action groups configured"
                )
            
            if rule.threshold == 0 and rule.operator in ["GreaterThan", "LessThan"]:
                validation_results["warnings"].append(
                    f"Alert rule '{rule.name}' has threshold of 0 with {rule.operator} operator"
                )
        
        # Validate action groups
        action_group_names = [ag.name for ag in self.action_groups]
        for rule in self.alert_rules:
            for action_group in rule.action_groups:
                if action_group not in action_group_names:
                    validation_results["errors"].append(
                        f"Alert rule '{rule.name}' references non-existent action group '{action_group}'"
                    )
                    validation_results["is_valid"] = False
        
        # Check for empty action groups
        for ag in self.action_groups:
            if not ag.email_receivers and not ag.sms_receivers and not ag.webhook_receivers:
                validation_results["warnings"].append(
                    f"Action group '{ag.name}' has no receivers configured"
                )
        
        # Recommendations
        critical_alerts = [rule for rule in self.alert_rules if rule.severity == AlertSeverity.CRITICAL]
        if not critical_alerts:
            validation_results["recommendations"].append(
                "Consider adding critical severity alerts for essential system metrics"
            )
        
        high_frequency_alerts = [rule for rule in self.alert_rules if rule.evaluation_frequency == AlertFrequency.PT1M]
        if len(high_frequency_alerts) > 5:
            validation_results["recommendations"].append(
                f"You have {len(high_frequency_alerts)} alerts evaluating every minute. Consider reducing frequency for non-critical alerts to reduce costs."
            )
        
        return validation_results