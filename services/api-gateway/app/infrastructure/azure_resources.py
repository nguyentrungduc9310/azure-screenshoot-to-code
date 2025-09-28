"""
Azure Resource Configuration
Production Azure resource setup and management for the Screenshot-to-Code system
"""
import asyncio
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

try:
    from shared.monitoring.structured_logger import StructuredLogger
    from shared.monitoring.correlation import get_correlation_id
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger
    
    def get_correlation_id():
        import uuid
        return str(uuid.uuid4())[:8]


class AzureEnvironment(Enum):
    """Azure deployment environments"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class ResourceTier(Enum):
    """Azure resource performance tiers"""
    BASIC = "basic"
    STANDARD = "standard"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


@dataclass
class AzureResourceConfig:
    """Configuration for Azure resources"""
    subscription_id: str
    resource_group: str
    location: str = "East US"
    environment: AzureEnvironment = AzureEnvironment.PRODUCTION
    tier: ResourceTier = ResourceTier.STANDARD
    tags: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        # Add default tags
        default_tags = {
            "Project": "Screenshot-to-Code",
            "Environment": self.environment.value,
            "Tier": self.tier.value,
            "ManagedBy": "AutoDeployment",
            "CreatedDate": datetime.utcnow().strftime("%Y-%m-%d")
        }
        self.tags = {**default_tags, **self.tags}


@dataclass
class AppServiceConfig:
    """Azure App Service configuration"""
    name: str
    sku: str = "P1v3"  # Premium v3 Small
    instances: int = 2
    auto_scale_enabled: bool = True
    min_instances: int = 2
    max_instances: int = 10
    cpu_threshold: int = 70
    memory_threshold: int = 80
    always_on: bool = True
    health_check_path: str = "/health"
    
    def get_scaling_rules(self) -> List[Dict[str, Any]]:
        """Get auto-scaling rules"""
        return [
            {
                "name": "cpu_scale_out",
                "metric": "CpuPercentage",
                "operator": "GreaterThan",
                "threshold": self.cpu_threshold,
                "duration": "PT5M",
                "action": "Increase",
                "instance_count": 1
            },
            {
                "name": "cpu_scale_in",
                "metric": "CpuPercentage", 
                "operator": "LessThan",
                "threshold": self.cpu_threshold - 20,
                "duration": "PT10M",
                "action": "Decrease",
                "instance_count": 1
            },
            {
                "name": "memory_scale_out",
                "metric": "MemoryPercentage",
                "operator": "GreaterThan",
                "threshold": self.memory_threshold,
                "duration": "PT5M",
                "action": "Increase",
                "instance_count": 1
            }
        ]


@dataclass
class CosmosDBConfig:
    """Azure Cosmos DB configuration"""
    account_name: str
    consistency_level: str = "Session"
    enable_automatic_failover: bool = True
    enable_multiple_write_locations: bool = True
    databases: List[str] = field(default_factory=lambda: ["conversations", "users", "analytics"])
    throughput: int = 4000  # RU/s
    backup_retention_days: int = 30
    geo_redundancy: bool = True
    
    def get_regions(self) -> List[Dict[str, Any]]:
        """Get regions for geo-replication"""
        return [
            {"region": "East US", "failover_priority": 0, "is_zone_redundant": True},
            {"region": "West US 2", "failover_priority": 1, "is_zone_redundant": True},
            {"region": "North Europe", "failover_priority": 2, "is_zone_redundant": False}
        ]


@dataclass
class RedisCacheConfig:
    """Azure Redis Cache configuration"""
    name: str
    sku: str = "Premium"
    size: str = "P1"  # 6GB
    enable_non_ssl_port: bool = False
    redis_version: str = "6"
    max_memory_policy: str = "allkeys-lru"
    backup_enabled: bool = True
    backup_frequency: int = 60  # minutes
    backup_retention_days: int = 7
    geo_replication: bool = True
    
    def get_configuration(self) -> Dict[str, str]:
        """Get Redis configuration settings"""
        return {
            "maxmemory-policy": self.max_memory_policy,
            "notify-keyspace-events": "Ex",
            "timeout": "300",
            "tcp-keepalive": "60",
            "maxmemory-delta": "10",
            "maxmemory-reserved": "10"
        }


@dataclass
class StorageConfig:
    """Azure Storage Account configuration"""
    account_name: str
    sku: str = "Standard_GRS"  # Geo-redundant storage
    kind: str = "StorageV2"
    access_tier: str = "Hot"
    enable_https_only: bool = True
    enable_blob_encryption: bool = True
    enable_file_encryption: bool = True
    blob_retention_days: int = 365
    containers: List[str] = field(default_factory=lambda: [
        "screenshots", "generated-code", "user-uploads", "backups", "logs"
    ])
    
    def get_blob_policies(self) -> Dict[str, Any]:
        """Get blob lifecycle policies"""
        return {
            "rules": [
                {
                    "name": "move_to_cool",
                    "type": "Lifecycle",
                    "definition": {
                        "filters": {
                            "blobTypes": ["blockBlob"],
                            "prefixMatch": ["screenshots/", "generated-code/"]
                        },
                        "actions": {
                            "baseBlob": {
                                "tierToCool": {"daysAfterModificationGreaterThan": 30},
                                "tierToArchive": {"daysAfterModificationGreaterThan": 90},
                                "delete": {"daysAfterModificationGreaterThan": 365}
                            }
                        }
                    }
                },
                {
                    "name": "cleanup_logs",
                    "type": "Lifecycle", 
                    "definition": {
                        "filters": {
                            "blobTypes": ["blockBlob"],
                            "prefixMatch": ["logs/"]
                        },
                        "actions": {
                            "baseBlob": {
                                "delete": {"daysAfterModificationGreaterThan": 90}
                            }
                        }
                    }
                }
            ]
        }


@dataclass
class KeyVaultConfig:
    """Azure Key Vault configuration"""
    name: str
    sku: str = "Standard"
    enable_soft_delete: bool = True
    soft_delete_retention_days: int = 90
    enable_purge_protection: bool = True
    enable_rbac_authorization: bool = True
    network_acls_default_action: str = "Deny"
    
    def get_access_policies(self) -> List[Dict[str, Any]]:
        """Get Key Vault access policies"""
        return [
            {
                "tenant_id": "common",
                "object_id": "app-service-principal",
                "permissions": {
                    "secrets": ["get", "list"],
                    "certificates": ["get", "list"],
                    "keys": ["get", "list", "decrypt", "encrypt"]
                }
            }
        ]


class AzureResourceManager:
    """Azure resource management and deployment"""
    
    def __init__(self, 
                 config: AzureResourceConfig,
                 logger: Optional[StructuredLogger] = None):
        
        self.config = config
        self.logger = logger or StructuredLogger()
        
        # Resource configurations
        self.app_service_config: Optional[AppServiceConfig] = None
        self.cosmos_config: Optional[CosmosDBConfig] = None
        self.redis_config: Optional[RedisCacheConfig] = None
        self.storage_config: Optional[StorageConfig] = None
        self.keyvault_config: Optional[KeyVaultConfig] = None
        
        # Deployment state
        self.deployment_status = {}
        self.resource_endpoints = {}
    
    def configure_app_service(self, config: AppServiceConfig):
        """Configure App Service settings"""
        self.app_service_config = config
        self.logger.info(
            "App Service configured",
            name=config.name,
            sku=config.sku,
            instances=config.instances,
            auto_scale=config.auto_scale_enabled
        )
    
    def configure_cosmos_db(self, config: CosmosDBConfig):
        """Configure Cosmos DB settings"""
        self.cosmos_config = config
        self.logger.info(
            "Cosmos DB configured",
            account_name=config.account_name,
            consistency_level=config.consistency_level,
            throughput=config.throughput,
            geo_redundancy=config.geo_redundancy
        )
    
    def configure_redis_cache(self, config: RedisCacheConfig):
        """Configure Redis Cache settings"""
        self.redis_config = config
        self.logger.info(
            "Redis Cache configured",
            name=config.name,
            sku=config.sku,
            size=config.size,
            backup_enabled=config.backup_enabled
        )
    
    def configure_storage(self, config: StorageConfig):
        """Configure Storage Account settings"""
        self.storage_config = config
        self.logger.info(
            "Storage Account configured",
            account_name=config.account_name,
            sku=config.sku,
            containers=len(config.containers)
        )
    
    def configure_key_vault(self, config: KeyVaultConfig):
        """Configure Key Vault settings"""
        self.keyvault_config = config
        self.logger.info(
            "Key Vault configured",
            name=config.name,
            soft_delete_enabled=config.enable_soft_delete,
            purge_protection=config.enable_purge_protection
        )
    
    async def generate_arm_template(self) -> Dict[str, Any]:
        """Generate Azure Resource Manager (ARM) template"""
        
        correlation_id = get_correlation_id()
        
        template = {
            "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
            "contentVersion": "1.0.0.0",
            "parameters": {
                "environment": {
                    "type": "string",
                    "defaultValue": self.config.environment.value,
                    "allowedValues": [env.value for env in AzureEnvironment]
                },
                "location": {
                    "type": "string",
                    "defaultValue": self.config.location
                }
            },
            "variables": {
                "resourcePrefix": f"sktc-{self.config.environment.value}",
                "tags": self.config.tags
            },
            "resources": [],
            "outputs": {}
        }
        
        # Add App Service resources
        if self.app_service_config:
            app_service_resources = await self._generate_app_service_resources()
            template["resources"].extend(app_service_resources)
        
        # Add Cosmos DB resources
        if self.cosmos_config:
            cosmos_resources = await self._generate_cosmos_resources()
            template["resources"].extend(cosmos_resources)
        
        # Add Redis Cache resources
        if self.redis_config:
            redis_resources = await self._generate_redis_resources()
            template["resources"].extend(redis_resources)
        
        # Add Storage resources
        if self.storage_config:
            storage_resources = await self._generate_storage_resources()
            template["resources"].extend(storage_resources)
        
        # Add Key Vault resources
        if self.keyvault_config:
            keyvault_resources = await self._generate_keyvault_resources()
            template["resources"].extend(keyvault_resources)
        
        # Add Application Insights
        insights_resources = await self._generate_insights_resources()
        template["resources"].extend(insights_resources)
        
        self.logger.info(
            "ARM template generated",
            resource_count=len(template["resources"]),
            correlation_id=correlation_id
        )
        
        return template
    
    async def _generate_app_service_resources(self) -> List[Dict[str, Any]]:
        """Generate App Service resources"""
        
        if not self.app_service_config:
            return []
        
        resources = []
        
        # App Service Plan
        app_service_plan = {
            "type": "Microsoft.Web/serverfarms",
            "apiVersion": "2021-02-01",
            "name": f"[concat(variables('resourcePrefix'), '-asp')]",
            "location": "[parameters('location')]",
            "tags": "[variables('tags')]",
            "sku": {
                "name": self.app_service_config.sku,
                "capacity": self.app_service_config.instances
            },
            "kind": "linux",
            "properties": {
                "reserved": True,
                "targetWorkerCount": self.app_service_config.instances,
                "targetWorkerSizeId": 0
            }
        }
        resources.append(app_service_plan)
        
        # App Service
        app_service = {
            "type": "Microsoft.Web/sites",
            "apiVersion": "2021-02-01",
            "name": f"[concat(variables('resourcePrefix'), '-api')]",
            "location": "[parameters('location')]",
            "tags": "[variables('tags')]",
            "dependsOn": [
                f"[resourceId('Microsoft.Web/serverfarms', concat(variables('resourcePrefix'), '-asp'))]"
            ],
            "properties": {
                "serverFarmId": f"[resourceId('Microsoft.Web/serverfarms', concat(variables('resourcePrefix'), '-asp'))]",
                "httpsOnly": True,
                "siteConfig": {
                    "alwaysOn": self.app_service_config.always_on,
                    "healthCheckPath": self.app_service_config.health_check_path,
                    "linuxFxVersion": "PYTHON|3.11",
                    "appSettings": [
                        {"name": "ENVIRONMENT", "value": "[parameters('environment')]"},
                        {"name": "PERFORMANCE_OPTIMIZATION_LEVEL", "value": "aggressive"},
                        {"name": "CACHE_ENABLED", "value": "true"},
                        {"name": "REDIS_ENABLED", "value": "true"}
                    ]
                }
            }
        }
        resources.append(app_service)
        
        # Auto-scaling settings
        if self.app_service_config.auto_scale_enabled:
            autoscale = {
                "type": "Microsoft.Insights/autoscalesettings",
                "apiVersion": "2015-04-01",
                "name": f"[concat(variables('resourcePrefix'), '-autoscale')]",
                "location": "[parameters('location')]",
                "dependsOn": [
                    f"[resourceId('Microsoft.Web/serverfarms', concat(variables('resourcePrefix'), '-asp'))]"
                ],
                "properties": {
                    "profiles": [
                        {
                            "name": "DefaultAutoscaleProfile",
                            "capacity": {
                                "minimum": str(self.app_service_config.min_instances),
                                "maximum": str(self.app_service_config.max_instances),
                                "default": str(self.app_service_config.instances)
                            },
                            "rules": self.app_service_config.get_scaling_rules()
                        }
                    ],
                    "enabled": True,
                    "targetResourceUri": f"[resourceId('Microsoft.Web/serverfarms', concat(variables('resourcePrefix'), '-asp'))]"
                }
            }
            resources.append(autoscale)
        
        return resources
    
    async def _generate_cosmos_resources(self) -> List[Dict[str, Any]]:
        """Generate Cosmos DB resources"""
        
        if not self.cosmos_config:
            return []
        
        cosmos_account = {
            "type": "Microsoft.DocumentDB/databaseAccounts",
            "apiVersion": "2021-10-15",
            "name": f"[concat(variables('resourcePrefix'), '-cosmos')]",
            "location": "[parameters('location')]",
            "tags": "[variables('tags')]",
            "kind": "GlobalDocumentDB",
            "properties": {
                "consistencyPolicy": {
                    "defaultConsistencyLevel": self.cosmos_config.consistency_level
                },
                "locations": self.cosmos_config.get_regions(),
                "databaseAccountOfferType": "Standard",
                "enableAutomaticFailover": self.cosmos_config.enable_automatic_failover,
                "enableMultipleWriteLocations": self.cosmos_config.enable_multiple_write_locations,
                "backupPolicy": {
                    "type": "Periodic",
                    "periodicModeProperties": {
                        "backupIntervalInMinutes": 240,
                        "backupRetentionIntervalInHours": self.cosmos_config.backup_retention_days * 24
                    }
                }
            }
        }
        
        return [cosmos_account]
    
    async def _generate_redis_resources(self) -> List[Dict[str, Any]]:
        """Generate Redis Cache resources"""
        
        if not self.redis_config:
            return []
        
        redis_cache = {
            "type": "Microsoft.Cache/Redis",
            "apiVersion": "2020-12-01",
            "name": f"[concat(variables('resourcePrefix'), '-redis')]",
            "location": "[parameters('location')]",
            "tags": "[variables('tags')]",
            "properties": {
                "sku": {
                    "name": self.redis_config.sku,
                    "family": "P",
                    "capacity": int(self.redis_config.size[1])
                },
                "enableNonSslPort": self.redis_config.enable_non_ssl_port,
                "redisVersion": self.redis_config.redis_version,
                "redisConfiguration": self.redis_config.get_configuration()
            }
        }
        
        return [redis_cache]
    
    async def _generate_storage_resources(self) -> List[Dict[str, Any]]:
        """Generate Storage Account resources"""
        
        if not self.storage_config:
            return []
        
        storage_account = {
            "type": "Microsoft.Storage/storageAccounts",
            "apiVersion": "2021-09-01",
            "name": f"[concat(variables('resourcePrefix'), 'storage')]",
            "location": "[parameters('location')]",
            "tags": "[variables('tags')]",
            "sku": {
                "name": self.storage_config.sku
            },
            "kind": self.storage_config.kind,
            "properties": {
                "accessTier": self.storage_config.access_tier,
                "supportsHttpsTrafficOnly": self.storage_config.enable_https_only,
                "encryption": {
                    "services": {
                        "blob": {"enabled": self.storage_config.enable_blob_encryption},
                        "file": {"enabled": self.storage_config.enable_file_encryption}
                    },
                    "keySource": "Microsoft.Storage"
                }
            }
        }
        
        return [storage_account]
    
    async def _generate_keyvault_resources(self) -> List[Dict[str, Any]]:
        """Generate Key Vault resources"""
        
        if not self.keyvault_config:
            return []
        
        key_vault = {
            "type": "Microsoft.KeyVault/vaults",
            "apiVersion": "2021-11-01-preview",
            "name": f"[concat(variables('resourcePrefix'), '-kv')]",
            "location": "[parameters('location')]",
            "tags": "[variables('tags')]",
            "properties": {
                "sku": {
                    "name": self.keyvault_config.sku,
                    "family": "A"
                },
                "tenantId": "[subscription().tenantId]",
                "enableSoftDelete": self.keyvault_config.enable_soft_delete,
                "softDeleteRetentionInDays": self.keyvault_config.soft_delete_retention_days,
                "enablePurgeProtection": self.keyvault_config.enable_purge_protection,
                "enableRbacAuthorization": self.keyvault_config.enable_rbac_authorization,
                "networkAcls": {
                    "defaultAction": self.keyvault_config.network_acls_default_action,
                    "bypass": "AzureServices"
                }
            }
        }
        
        return [key_vault]
    
    async def _generate_insights_resources(self) -> List[Dict[str, Any]]:
        """Generate Application Insights resources"""
        
        app_insights = {
            "type": "Microsoft.Insights/components",
            "apiVersion": "2020-02-02",
            "name": f"[concat(variables('resourcePrefix'), '-insights')]",
            "location": "[parameters('location')]",
            "tags": "[variables('tags')]",
            "kind": "web",
            "properties": {
                "Application_Type": "web",
                "RetentionInDays": 90,
                "SamplingPercentage": 100,
                "DisableIpMasking": False,
                "WorkspaceResourceId": f"[resourceId('Microsoft.OperationalInsights/workspaces', concat(variables('resourcePrefix'), '-workspace'))]"
            }
        }
        
        # Log Analytics Workspace
        log_workspace = {
            "type": "Microsoft.OperationalInsights/workspaces",
            "apiVersion": "2021-12-01-preview",
            "name": f"[concat(variables('resourcePrefix'), '-workspace')]",
            "location": "[parameters('location')]",
            "tags": "[variables('tags')]",
            "properties": {
                "sku": {"name": "PerGB2018"},
                "retentionInDays": 90,
                "features": {
                    "enableLogAccessUsingOnlyResourcePermissions": True
                }
            }
        }
        
        return [log_workspace, app_insights]
    
    async def validate_template(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """Validate ARM template"""
        
        correlation_id = get_correlation_id()
        
        validation_results = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "resource_count": len(template.get("resources", [])),
            "correlation_id": correlation_id
        }
        
        try:
            # Basic template validation
            required_fields = ["$schema", "contentVersion", "resources"]
            for field in required_fields:
                if field not in template:
                    validation_results["errors"].append(f"Missing required field: {field}")
                    validation_results["is_valid"] = False
            
            # Resource validation
            resources = template.get("resources", [])
            resource_names = set()
            
            for i, resource in enumerate(resources):
                # Check required resource fields
                required_resource_fields = ["type", "apiVersion", "name"]
                for field in required_resource_fields:
                    if field not in resource:
                        validation_results["errors"].append(
                            f"Resource {i}: Missing required field '{field}'"
                        )
                        validation_results["is_valid"] = False
                
                # Check for duplicate resource names
                resource_name = resource.get("name", "")
                if resource_name in resource_names:
                    validation_results["errors"].append(
                        f"Duplicate resource name: {resource_name}"
                    )
                    validation_results["is_valid"] = False
                else:
                    resource_names.add(resource_name)
            
            # Performance and cost warnings
            if len(resources) > 50:
                validation_results["warnings"].append(
                    f"Large template with {len(resources)} resources may take longer to deploy"
                )
            
            if validation_results["is_valid"]:
                self.logger.info(
                    "ARM template validation successful",
                    resource_count=validation_results["resource_count"],
                    warnings=len(validation_results["warnings"]),
                    correlation_id=correlation_id
                )
            else:
                self.logger.error(
                    "ARM template validation failed",
                    errors=validation_results["errors"],
                    correlation_id=correlation_id
                )
            
        except Exception as e:
            validation_results["is_valid"] = False
            validation_results["errors"].append(f"Validation exception: {str(e)}")
            
            self.logger.error(
                "ARM template validation error",
                error=str(e),
                correlation_id=correlation_id
            )
        
        return validation_results
    
    async def estimate_costs(self) -> Dict[str, Any]:
        """Estimate monthly costs for resources"""
        
        # Cost estimates in USD per month (approximate)
        cost_estimates = {
            "app_service": 0,
            "cosmos_db": 0,
            "redis_cache": 0,
            "storage": 0,
            "key_vault": 0,
            "application_insights": 0,
            "total": 0
        }
        
        # App Service costs
        if self.app_service_config:
            app_service_costs = {
                "P1v3": 146,  # Premium v3 Small
                "P2v3": 292,  # Premium v3 Medium
                "P3v3": 584   # Premium v3 Large
            }
            base_cost = app_service_costs.get(self.app_service_config.sku, 146)
            cost_estimates["app_service"] = base_cost * self.app_service_config.instances
        
        # Cosmos DB costs
        if self.cosmos_config:
            # Base cost for throughput + storage
            throughput_cost = (self.cosmos_config.throughput / 100) * 6  # $6 per 100 RU/s
            storage_cost = 25  # Estimated storage cost
            backup_cost = 10 if self.cosmos_config.backup_retention_days > 7 else 5
            cost_estimates["cosmos_db"] = throughput_cost + storage_cost + backup_cost
        
        # Redis cache costs
        if self.redis_config:
            redis_costs = {
                "P1": 381,  # Premium 6GB
                "P2": 763,  # Premium 13GB
                "P3": 1525, # Premium 26GB
                "P4": 3050  # Premium 53GB
            }
            cost_estimates["redis_cache"] = redis_costs.get(self.redis_config.size, 381)
        
        # Storage costs (estimated)
        if self.storage_config:
            cost_estimates["storage"] = 50  # Estimated monthly storage costs
        
        # Key Vault costs
        if self.keyvault_config:
            cost_estimates["key_vault"] = 5  # Base Key Vault cost
        
        # Application Insights
        cost_estimates["application_insights"] = 25  # Estimated monitoring costs
        
        # Calculate total
        cost_estimates["total"] = sum(
            cost for key, cost in cost_estimates.items() if key != "total"
        )
        
        self.logger.info(
            "Cost estimation completed",
            total_monthly_cost=cost_estimates["total"],
            environment=self.config.environment.value
        )
        
        return cost_estimates
    
    def get_deployment_summary(self) -> Dict[str, Any]:
        """Get deployment configuration summary"""
        
        summary = {
            "environment": self.config.environment.value,
            "location": self.config.location,
            "resource_group": self.config.resource_group,
            "tier": self.config.tier.value,
            "components": {},
            "estimated_monthly_cost": 0
        }
        
        if self.app_service_config:
            summary["components"]["app_service"] = {
                "sku": self.app_service_config.sku,
                "instances": self.app_service_config.instances,
                "auto_scale": self.app_service_config.auto_scale_enabled
            }
        
        if self.cosmos_config:
            summary["components"]["cosmos_db"] = {
                "consistency_level": self.cosmos_config.consistency_level,
                "throughput": self.cosmos_config.throughput,
                "geo_redundancy": self.cosmos_config.geo_redundancy
            }
        
        if self.redis_config:
            summary["components"]["redis_cache"] = {
                "sku": self.redis_config.sku,
                "size": self.redis_config.size,
                "backup_enabled": self.redis_config.backup_enabled
            }
        
        if self.storage_config:
            summary["components"]["storage"] = {
                "sku": self.storage_config.sku,
                "containers": len(self.storage_config.containers)
            }
        
        if self.keyvault_config:
            summary["components"]["key_vault"] = {
                "sku": self.keyvault_config.sku,
                "soft_delete": self.keyvault_config.enable_soft_delete
            }
        
        return summary