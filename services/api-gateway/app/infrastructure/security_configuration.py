"""
Security Configuration
Production security setup and network security configuration for Azure resources
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


class SecurityTier(Enum):
    """Security tier levels"""
    BASIC = "basic"
    STANDARD = "standard"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class ThreatLevel(Enum):
    """Threat assessment levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class NetworkSecurityGroup:
    """Network Security Group configuration"""
    name: str
    description: str
    rules: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_rule(self, name: str, direction: str, access: str, protocol: str,
                source_port_range: str, destination_port_range: str,
                source_address_prefix: str, destination_address_prefix: str,
                priority: int = 1000):
        """Add security rule to NSG"""
        rule = {
            "name": name,
            "properties": {
                "description": f"Security rule: {name}",
                "protocol": protocol,
                "sourcePortRange": source_port_range,
                "destinationPortRange": destination_port_range,
                "sourceAddressPrefix": source_address_prefix,
                "destinationAddressPrefix": destination_address_prefix,
                "access": access,
                "priority": priority,
                "direction": direction
            }
        }
        self.rules.append(rule)
    
    def to_arm_resource(self, resource_prefix: str) -> Dict[str, Any]:
        """Convert to ARM template resource"""
        return {
            "type": "Microsoft.Network/networkSecurityGroups",
            "apiVersion": "2021-05-01",
            "name": f"{resource_prefix}-{self.name}-nsg",
            "location": "[parameters('location')]",
            "properties": {
                "securityRules": self.rules
            }
        }


@dataclass
class SSLCertificateConfig:
    """SSL Certificate configuration"""
    domain_name: str
    certificate_type: str = "managed"  # managed or custom
    key_vault_secret_name: Optional[str] = None
    auto_renewal: bool = True
    certificate_authority: str = "DigiCert"
    
    def to_arm_resource(self, resource_prefix: str, app_service_name: str) -> Dict[str, Any]:
        """Convert to ARM template resource"""
        if self.certificate_type == "managed":
            return {
                "type": "Microsoft.Web/sites/hostNameBindings",
                "apiVersion": "2021-02-01",
                "name": f"{app_service_name}/{self.domain_name}",
                "dependsOn": [
                    f"[resourceId('Microsoft.Web/sites', '{app_service_name}')]"
                ],
                "properties": {
                    "sslState": "SniEnabled",
                    "thumbprint": "[reference(resourceId('Microsoft.Web/certificates', variables('certificateName'))).Thumbprint]"
                }
            }
        else:
            return {
                "type": "Microsoft.Web/certificates",
                "apiVersion": "2021-02-01",
                "name": f"{resource_prefix}-cert-{self.domain_name.replace('.', '-')}",
                "location": "[parameters('location')]",
                "properties": {
                    "keyVaultId": f"[resourceId('Microsoft.KeyVault/vaults', '{resource_prefix}-kv')]",
                    "keyVaultSecretName": self.key_vault_secret_name or f"{self.domain_name.replace('.', '-')}-cert"
                }
            }


@dataclass
class FirewallRule:
    """Firewall rule configuration"""
    name: str
    start_ip: str
    end_ip: str
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "name": self.name,
            "startIpAddress": self.start_ip,
            "endIpAddress": self.end_ip
        }


@dataclass
class AccessPolicy:
    """Access policy configuration"""
    principal_type: str  # User, Group, ServicePrincipal
    principal_id: str
    permissions: Dict[str, List[str]]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "tenantId": "[subscription().tenantId]",
            "objectId": self.principal_id,
            "permissions": self.permissions
        }


class SecurityManager:
    """Security configuration and policy manager"""
    
    def __init__(self, security_tier: SecurityTier = SecurityTier.STANDARD,
                 logger: Optional[StructuredLogger] = None):
        self.security_tier = security_tier
        self.logger = logger or StructuredLogger()
        
        # Security configurations
        self.network_security_groups: List[NetworkSecurityGroup] = []
        self.ssl_certificates: List[SSLCertificateConfig] = []
        self.firewall_rules: List[FirewallRule] = []
        self.access_policies: List[AccessPolicy] = []
        
        # Initialize default configurations
        self._initialize_default_security()
    
    def _initialize_default_security(self):
        """Initialize default security configurations"""
        
        # Create default NSG for web tier
        web_nsg = NetworkSecurityGroup(
            name="web-tier",
            description="Network security group for web tier"
        )
        
        # Add default web tier rules
        web_nsg.add_rule(
            name="AllowHTTPS",
            direction="Inbound",
            access="Allow",
            protocol="Tcp",
            source_port_range="*",
            destination_port_range="443",
            source_address_prefix="Internet",
            destination_address_prefix="*",
            priority=100
        )
        
        web_nsg.add_rule(
            name="AllowHTTP",
            direction="Inbound", 
            access="Allow",
            protocol="Tcp",
            source_port_range="*",
            destination_port_range="80",
            source_address_prefix="Internet",
            destination_address_prefix="*",
            priority=110
        )
        
        web_nsg.add_rule(
            name="DenyAllInbound",
            direction="Inbound",
            access="Deny",
            protocol="*",
            source_port_range="*",
            destination_port_range="*",
            source_address_prefix="*",
            destination_address_prefix="*",
            priority=4096
        )
        
        self.network_security_groups.append(web_nsg)
        
        # Create default NSG for database tier
        db_nsg = NetworkSecurityGroup(
            name="database-tier",
            description="Network security group for database tier"
        )
        
        # Add database tier rules
        db_nsg.add_rule(
            name="AllowAppServiceCosmosDB",
            direction="Inbound",
            access="Allow", 
            protocol="Tcp",
            source_port_range="*",
            destination_port_range="443",
            source_address_prefix="VirtualNetwork",
            destination_address_prefix="*",
            priority=100
        )
        
        db_nsg.add_rule(
            name="AllowRedisCache",
            direction="Inbound",
            access="Allow",
            protocol="Tcp", 
            source_port_range="*",
            destination_port_range="6380",
            source_address_prefix="VirtualNetwork",
            destination_address_prefix="*",
            priority=110
        )
        
        db_nsg.add_rule(
            name="DenyAllInbound",
            direction="Inbound",
            access="Deny",
            protocol="*",
            source_port_range="*",
            destination_port_range="*",
            source_address_prefix="*",
            destination_address_prefix="*",
            priority=4096
        )
        
        self.network_security_groups.append(db_nsg)
        
        # Add default firewall rules based on security tier
        if self.security_tier in [SecurityTier.STANDARD, SecurityTier.PREMIUM, SecurityTier.ENTERPRISE]:
            self.firewall_rules.extend([
                FirewallRule(
                    name="AllowAzureServices",
                    start_ip="0.0.0.0",
                    end_ip="0.0.0.0",
                    description="Allow Azure services"
                ),
                FirewallRule(
                    name="AllowOfficeNetwork",
                    start_ip="203.0.113.0",
                    end_ip="203.0.113.255",
                    description="Allow office network access"
                )
            ])
        
        # Add default SSL certificate configuration
        self.ssl_certificates.append(
            SSLCertificateConfig(
                domain_name="screenshot-to-code.com",
                certificate_type="managed",
                auto_renewal=True
            )
        )
        
        # Add default access policies
        self.access_policies.extend([
            AccessPolicy(
                principal_type="ServicePrincipal",
                principal_id="[reference(resourceId('Microsoft.Web/sites', variables('appServiceName')), '2021-02-01', 'Full').identity.principalId]",
                permissions={
                    "secrets": ["get", "list"],
                    "certificates": ["get", "list"],
                    "keys": ["get", "list", "decrypt", "encrypt"]
                }
            )
        ])
    
    async def generate_security_arm_template(self, resource_prefix: str) -> Dict[str, Any]:
        """Generate ARM template for security resources"""
        
        correlation_id = get_correlation_id()
        
        template = {
            "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
            "contentVersion": "1.0.0.0",
            "parameters": {
                "location": {
                    "type": "string",
                    "defaultValue": "[resourceGroup().location]"
                },
                "resourcePrefix": {
                    "type": "string",
                    "defaultValue": resource_prefix
                }
            },
            "variables": {
                "resourcePrefix": "[parameters('resourcePrefix')]",
                "appServiceName": "[concat(variables('resourcePrefix'), '-api')]",
                "keyVaultName": "[concat(variables('resourcePrefix'), '-kv')]",
                "certificateName": "[concat(variables('resourcePrefix'), '-cert')]"
            },
            "resources": [],
            "outputs": {}
        }
        
        # Add Network Security Groups
        for nsg in self.network_security_groups:
            template["resources"].append(nsg.to_arm_resource(resource_prefix))
        
        # Add SSL Certificates
        for cert in self.ssl_certificates:
            template["resources"].append(
                cert.to_arm_resource(resource_prefix, "[variables('appServiceName')]")
            )
        
        # Add Application Gateway for advanced security
        if self.security_tier in [SecurityTier.PREMIUM, SecurityTier.ENTERPRISE]:
            app_gateway = await self._generate_application_gateway(resource_prefix)
            template["resources"].append(app_gateway)
        
        # Add Web Application Firewall
        if self.security_tier == SecurityTier.ENTERPRISE:
            waf_policy = await self._generate_waf_policy(resource_prefix)
            template["resources"].append(waf_policy)
        
        # Add DDoS Protection Plan for enterprise
        if self.security_tier == SecurityTier.ENTERPRISE:
            ddos_plan = await self._generate_ddos_protection(resource_prefix)
            template["resources"].append(ddos_plan)
        
        self.logger.info(
            "Security ARM template generated",
            resource_count=len(template["resources"]),
            security_tier=self.security_tier.value,
            correlation_id=correlation_id
        )
        
        return template
    
    async def _generate_application_gateway(self, resource_prefix: str) -> Dict[str, Any]:
        """Generate Application Gateway resource"""
        
        return {
            "type": "Microsoft.Network/applicationGateways", 
            "apiVersion": "2021-05-01",
            "name": f"{resource_prefix}-appgw",
            "location": "[parameters('location')]",
            "dependsOn": [
                f"[resourceId('Microsoft.Network/publicIPAddresses', '{resource_prefix}-appgw-pip')]",
                f"[resourceId('Microsoft.Network/virtualNetworks/subnets', '{resource_prefix}-vnet', 'appgw-subnet')]"
            ],
            "properties": {
                "sku": {
                    "name": "WAF_v2",
                    "tier": "WAF_v2",
                    "capacity": 2
                },
                "gatewayIPConfigurations": [
                    {
                        "name": "appGatewayIpConfig",
                        "properties": {
                            "subnet": {
                                "id": f"[resourceId('Microsoft.Network/virtualNetworks/subnets', '{resource_prefix}-vnet', 'appgw-subnet')]"
                            }
                        }
                    }
                ],
                "frontendIPConfigurations": [
                    {
                        "name": "appGwPublicFrontendIp",
                        "properties": {
                            "publicIPAddress": {
                                "id": f"[resourceId('Microsoft.Network/publicIPAddresses', '{resource_prefix}-appgw-pip')]"
                            }
                        }
                    }
                ],
                "frontendPorts": [
                    {
                        "name": "port_80",
                        "properties": {
                            "port": 80
                        }
                    },
                    {
                        "name": "port_443",
                        "properties": {
                            "port": 443
                        }
                    }
                ],
                "backendAddressPools": [
                    {
                        "name": "appServiceBackendPool",
                        "properties": {
                            "backendAddresses": [
                                {
                                    "fqdn": f"[concat(variables('appServiceName'), '.azurewebsites.net')]"
                                }
                            ]
                        }
                    }
                ],
                "backendHttpSettingsCollection": [
                    {
                        "name": "appServiceBackendHttpSettings",
                        "properties": {
                            "port": 443,
                            "protocol": "Https",
                            "cookieBasedAffinity": "Disabled",
                            "requestTimeout": 30,
                            "pickHostNameFromBackendAddress": True
                        }
                    }
                ],
                "httpListeners": [
                    {
                        "name": "appGwHttpListener",
                        "properties": {
                            "frontendIPConfiguration": {
                                "id": f"[resourceId('Microsoft.Network/applicationGateways/frontendIPConfigurations', '{resource_prefix}-appgw', 'appGwPublicFrontendIp')]"
                            },
                            "frontendPort": {
                                "id": f"[resourceId('Microsoft.Network/applicationGateways/frontendPorts', '{resource_prefix}-appgw', 'port_443')]"
                            },
                            "protocol": "Https",
                            "sslCertificate": {
                                "id": f"[resourceId('Microsoft.Network/applicationGateways/sslCertificates', '{resource_prefix}-appgw', 'appGwSslCertificate')]"
                            }
                        }
                    }
                ],
                "requestRoutingRules": [
                    {
                        "name": "rule1",
                        "properties": {
                            "ruleType": "Basic",
                            "httpListener": {
                                "id": f"[resourceId('Microsoft.Network/applicationGateways/httpListeners', '{resource_prefix}-appgw', 'appGwHttpListener')]"
                            },
                            "backendAddressPool": {
                                "id": f"[resourceId('Microsoft.Network/applicationGateways/backendAddressPools', '{resource_prefix}-appgw', 'appServiceBackendPool')]"
                            },
                            "backendHttpSettings": {
                                "id": f"[resourceId('Microsoft.Network/applicationGateways/backendHttpSettingsCollection', '{resource_prefix}-appgw', 'appServiceBackendHttpSettings')]"
                            }
                        }
                    }
                ],
                "enableHttp2": True,
                "autoscaleConfiguration": {
                    "minCapacity": 2,
                    "maxCapacity": 10
                }
            }
        }
    
    async def _generate_waf_policy(self, resource_prefix: str) -> Dict[str, Any]:
        """Generate Web Application Firewall policy"""
        
        return {
            "type": "Microsoft.Network/ApplicationGatewayWebApplicationFirewallPolicies",
            "apiVersion": "2021-05-01",
            "name": f"{resource_prefix}-waf-policy",
            "location": "[parameters('location')]",
            "properties": {
                "policySettings": {
                    "requestBodyCheck": True,
                    "maxRequestBodySizeInKb": 128,
                    "fileUploadLimitInMb": 100,
                    "mode": "Prevention",
                    "state": "Enabled"
                },
                "managedRules": {
                    "managedRuleSets": [
                        {
                            "ruleSetType": "OWASP",
                            "ruleSetVersion": "3.2",
                            "ruleGroupOverrides": []
                        },
                        {
                            "ruleSetType": "Microsoft_BotManagerRuleSet",
                            "ruleSetVersion": "0.1"
                        }
                    ]
                },
                "customRules": [
                    {
                        "name": "RateLimitRule",
                        "priority": 1,
                        "ruleType": "RateLimitRule",
                        "action": "Block",
                        "rateLimitDuration": "OneMin",
                        "rateLimitThreshold": 100,
                        "matchConditions": [
                            {
                                "matchVariables": [
                                    {
                                        "variableName": "RemoteAddr"
                                    }
                                ],
                                "operator": "IPMatch",
                                "matchValues": ["*"]
                            }
                        ]
                    },
                    {
                        "name": "BlockSQLInjection",
                        "priority": 2,
                        "ruleType": "MatchRule",
                        "action": "Block",
                        "matchConditions": [
                            {
                                "matchVariables": [
                                    {
                                        "variableName": "QueryString"
                                    },
                                    {
                                        "variableName": "RequestBody"
                                    }
                                ],
                                "operator": "Contains",
                                "matchValues": ["union", "select", "insert", "delete", "drop", "exec"]
                            }
                        ]
                    }
                ]
            }
        }
    
    async def _generate_ddos_protection(self, resource_prefix: str) -> Dict[str, Any]:
        """Generate DDoS Protection Plan"""
        
        return {
            "type": "Microsoft.Network/ddosProtectionPlans",
            "apiVersion": "2021-05-01",
            "name": f"{resource_prefix}-ddos-plan",
            "location": "[parameters('location')]",
            "properties": {}
        }
    
    async def create_security_policies(self) -> Dict[str, Any]:
        """Create comprehensive security policies"""
        
        policies = {
            "network_security": {
                "virtual_network": {
                    "description": "Virtual network security configuration",
                    "address_space": "10.0.0.0/16",
                    "subnets": {
                        "web_tier": {
                            "address_prefix": "10.0.1.0/24",
                            "security_group": "web-tier-nsg",
                            "service_endpoints": ["Microsoft.Web", "Microsoft.KeyVault"]
                        },
                        "database_tier": {
                            "address_prefix": "10.0.2.0/24",
                            "security_group": "database-tier-nsg",
                            "service_endpoints": ["Microsoft.DocumentDB", "Microsoft.Cache"]
                        },
                        "management_tier": {
                            "address_prefix": "10.0.3.0/24",
                            "security_group": "management-tier-nsg",
                            "service_endpoints": ["Microsoft.Storage", "Microsoft.KeyVault"]
                        }
                    }
                },
                "network_security_groups": [
                    {
                        "name": nsg.name,
                        "description": nsg.description,
                        "rules_count": len(nsg.rules)
                    }
                    for nsg in self.network_security_groups
                ]
            },
            "identity_and_access": {
                "authentication": {
                    "azure_ad_integration": True,
                    "multi_factor_authentication": self.security_tier != SecurityTier.BASIC,
                    "conditional_access": self.security_tier in [SecurityTier.PREMIUM, SecurityTier.ENTERPRISE],
                    "privileged_identity_management": self.security_tier == SecurityTier.ENTERPRISE
                },
                "authorization": {
                    "role_based_access_control": True,
                    "just_in_time_access": self.security_tier in [SecurityTier.PREMIUM, SecurityTier.ENTERPRISE],
                    "access_reviews": self.security_tier == SecurityTier.ENTERPRISE
                },
                "key_vault_policies": [
                    {
                        "principal_type": policy.principal_type,
                        "permissions": policy.permissions
                    }
                    for policy in self.access_policies
                ]
            },
            "data_protection": {
                "encryption": {
                    "at_rest": {
                        "cosmos_db": "Customer-managed keys",
                        "storage_account": "Microsoft-managed keys",
                        "redis_cache": "Microsoft-managed keys",
                        "key_vault": "HSM-protected keys" if self.security_tier == SecurityTier.ENTERPRISE else "Software-protected keys"
                    },
                    "in_transit": {
                        "https_only": True,
                        "tls_version": "1.2",
                        "certificate_management": "Automated renewal"
                    }
                },
                "backup_security": {
                    "backup_encryption": True,
                    "geo_redundant_backup": True,
                    "backup_retention": "30 days standard, 7 years compliance",
                    "backup_access_control": "RBAC with audit trail"
                }
            },
            "monitoring_and_compliance": {
                "security_monitoring": {
                    "azure_security_center": True,
                    "azure_sentinel": self.security_tier in [SecurityTier.PREMIUM, SecurityTier.ENTERPRISE],
                    "threat_detection": True,
                    "vulnerability_assessment": True
                },
                "compliance_frameworks": {
                    "gdpr": True,
                    "iso_27001": self.security_tier in [SecurityTier.PREMIUM, SecurityTier.ENTERPRISE],
                    "soc_2": self.security_tier == SecurityTier.ENTERPRISE,
                    "pci_dss": self.security_tier == SecurityTier.ENTERPRISE
                },
                "audit_logging": {
                    "activity_logs": True, 
                    "diagnostic_logs": True,
                    "security_logs": True,
                    "retention_period": "1 year"
                }
            },
            "incident_response": {
                "security_incident_plan": {
                    "detection": "Automated threat detection with SIEM integration",
                    "response_team": "24/7 SOC" if self.security_tier == SecurityTier.ENTERPRISE else "Business hours",
                    "communication": "Automated alerting and escalation procedures",
                    "recovery": "Documented recovery procedures with RTO/RPO targets"
                },
                "business_continuity": {
                    "disaster_recovery": True,
                    "backup_sites": "Geographic redundancy",
                    "failover_procedures": "Automated failover with manual override",
                    "recovery_testing": "Quarterly" if self.security_tier == SecurityTier.ENTERPRISE else "Semi-annual"
                }
            }
        }
        
        return policies
    
    async def assess_security_posture(self) -> Dict[str, Any]:
        """Assess current security posture and recommendations"""
        
        assessment = {
            "overall_score": 0,
            "category_scores": {},
            "strengths": [],
            "vulnerabilities": [],
            "recommendations": [],
            "compliance_status": {}
        }
        
        # Network Security Assessment
        network_score = 70  # Base score
        if len(self.network_security_groups) >= 2:
            network_score += 10
        if self.security_tier in [SecurityTier.PREMIUM, SecurityTier.ENTERPRISE]:
            network_score += 15  # Application Gateway + WAF
        if self.security_tier == SecurityTier.ENTERPRISE:
            network_score += 5   # DDoS Protection
        
        assessment["category_scores"]["network_security"] = min(network_score, 100)
        
        # Identity and Access Management Assessment
        iam_score = 60  # Base score
        if len(self.access_policies) > 0:
            iam_score += 20
        if self.security_tier != SecurityTier.BASIC:
            iam_score += 15  # MFA and conditional access
        if self.security_tier == SecurityTier.ENTERPRISE:
            iam_score += 5   # PIM
        
        assessment["category_scores"]["identity_access"] = min(iam_score, 100)
        
        # Data Protection Assessment
        data_score = 80  # Base score (encryption at rest and in transit)
        if len(self.ssl_certificates) > 0:
            data_score += 10
        if self.security_tier == SecurityTier.ENTERPRISE:
            data_score += 10  # HSM-protected keys
        
        assessment["category_scores"]["data_protection"] = min(data_score, 100)
        
        # Monitoring and Compliance Assessment
        monitoring_score = 65  # Base score
        if self.security_tier in [SecurityTier.PREMIUM, SecurityTier.ENTERPRISE]:
            monitoring_score += 20  # Azure Sentinel
        if self.security_tier == SecurityTier.ENTERPRISE:
            monitoring_score += 15  # Full compliance frameworks
        
        assessment["category_scores"]["monitoring_compliance"] = min(monitoring_score, 100)
        
        # Calculate overall score
        assessment["overall_score"] = sum(assessment["category_scores"].values()) // len(assessment["category_scores"])
        
        # Identify strengths
        if assessment["category_scores"]["data_protection"] >= 80:
            assessment["strengths"].append("Strong data encryption and protection measures")
        
        if self.security_tier in [SecurityTier.PREMIUM, SecurityTier.ENTERPRISE]:
            assessment["strengths"].append("Advanced threat protection with WAF and Application Gateway")
        
        if len(self.network_security_groups) >= 2:
            assessment["strengths"].append("Network segmentation with multiple security groups")
        
        # Identify vulnerabilities and recommendations
        if assessment["category_scores"]["network_security"] < 80:
            assessment["vulnerabilities"].append("Network security could be enhanced with additional protection layers")
            assessment["recommendations"].append("Consider upgrading to Premium or Enterprise tier for Application Gateway and WAF")
        
        if assessment["category_scores"]["identity_access"] < 85:
            assessment["vulnerabilities"].append("Identity and access management could be strengthened")
            assessment["recommendations"].append("Implement multi-factor authentication and conditional access policies")
        
        if self.security_tier == SecurityTier.BASIC:
            assessment["recommendations"].append("Upgrade security tier for enhanced protection and compliance features")
        
        # Compliance status
        assessment["compliance_status"] = {
            "gdpr": True,
            "iso_27001": self.security_tier in [SecurityTier.PREMIUM, SecurityTier.ENTERPRISE],
            "soc_2": self.security_tier == SecurityTier.ENTERPRISE,
            "pci_dss": self.security_tier == SecurityTier.ENTERPRISE
        }
        
        return assessment
    
    def get_security_summary(self) -> Dict[str, Any]:
        """Get security configuration summary"""
        
        return {
            "security_tier": self.security_tier.value,
            "network_security_groups": len(self.network_security_groups),
            "ssl_certificates": len(self.ssl_certificates),
            "firewall_rules": len(self.firewall_rules),
            "access_policies": len(self.access_policies),
            "features": {
                "application_gateway": self.security_tier in [SecurityTier.PREMIUM, SecurityTier.ENTERPRISE],
                "web_application_firewall": self.security_tier in [SecurityTier.PREMIUM, SecurityTier.ENTERPRISE],
                "ddos_protection": self.security_tier == SecurityTier.ENTERPRISE,
                "advanced_threat_protection": self.security_tier != SecurityTier.BASIC,
                "compliance_frameworks": self.security_tier == SecurityTier.ENTERPRISE
            }
        }
    
    async def generate_security_documentation(self) -> Dict[str, Any]:
        """Generate comprehensive security documentation"""
        
        documentation = {
            "security_overview": {
                "security_tier": self.security_tier.value,
                "threat_model": "STRIDE methodology with Azure security best practices",
                "security_principles": [
                    "Defense in depth",
                    "Zero trust architecture",
                    "Least privilege access",
                    "Continuous monitoring",
                    "Incident response readiness"
                ]
            },
            "network_security": {
                "architecture": "Multi-tier network security with NSGs and subnet isolation",
                "security_groups": [
                    {
                        "name": nsg.name,
                        "description": nsg.description,
                        "rules": len(nsg.rules)
                    }
                    for nsg in self.network_security_groups
                ],
                "traffic_flow": "Internet -> Application Gateway -> App Service -> Database services"
            },
            "identity_and_access": {
                "authentication_methods": [
                    "Azure Active Directory integration",
                    "Multi-factor authentication" if self.security_tier != SecurityTier.BASIC else "Single-factor authentication",
                    "Conditional access policies" if self.security_tier in [SecurityTier.PREMIUM, SecurityTier.ENTERPRISE] else "Basic access policies"
                ],
                "authorization_model": "Role-Based Access Control (RBAC) with custom roles",
                "key_management": "Azure Key Vault with automated rotation"
            },
            "data_protection": {
                "encryption_at_rest": "AES-256 encryption for all data stores",
                "encryption_in_transit": "TLS 1.2+ for all communications",
                "key_management": "Azure Key Vault with HSM backing" if self.security_tier == SecurityTier.ENTERPRISE else "Azure Key Vault with software keys",
                "backup_security": "Encrypted backups with geo-redundancy"
            },
            "monitoring_and_alerting": {
                "security_monitoring": "Azure Security Center with continuous assessment",
                "threat_detection": "Azure Sentinel SIEM" if self.security_tier in [SecurityTier.PREMIUM, SecurityTier.ENTERPRISE] else "Basic threat detection",
                "log_management": "Centralized logging with 1-year retention",
                "incident_response": "Automated alerting with escalation procedures"
            },
            "compliance_and_governance": {
                "frameworks": [
                    "GDPR - General Data Protection Regulation",
                    "ISO 27001" if self.security_tier in [SecurityTier.PREMIUM, SecurityTier.ENTERPRISE] else None,
                    "SOC 2" if self.security_tier == SecurityTier.ENTERPRISE else None,
                    "PCI DSS" if self.security_tier == SecurityTier.ENTERPRISE else None
                ],
                "governance": "Azure Policy for compliance automation",
                "audit_trail": "Comprehensive audit logging with tamper protection"
            }
        }
        
        # Remove None values from compliance frameworks
        documentation["compliance_and_governance"]["frameworks"] = [
            f for f in documentation["compliance_and_governance"]["frameworks"] if f is not None
        ]
        
        return documentation