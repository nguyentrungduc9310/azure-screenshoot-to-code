"""
Copilot Studio Agent Deployer
Automated deployment and configuration of Copilot Studio agents
"""
import asyncio
import json
import aiohttp
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum
import uuid

try:
    from shared.monitoring.structured_logger import StructuredLogger
    from shared.monitoring.correlation import get_correlation_id
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger


class DeploymentEnvironment(Enum):
    """Deployment environment types"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class AgentStatus(Enum):
    """Agent deployment status"""
    NOT_DEPLOYED = "not_deployed"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    FAILED = "failed"
    UPDATING = "updating"


@dataclass
class DeploymentConfig:
    """Configuration for agent deployment"""
    environment: DeploymentEnvironment
    tenant_id: str
    application_id: str
    client_secret: str
    webhook_url: str
    webhook_secret: str
    
    # Agent configuration
    agent_name: str = "Screenshot to Code Assistant"
    agent_description: str = "AI-powered assistant that converts UI screenshots into clean, production-ready code"
    supported_languages: List[str] = None
    
    def __post_init__(self):
        if self.supported_languages is None:
            self.supported_languages = ["en", "vi", "fr", "de", "ja", "zh"]


@dataclass
class DeploymentResult:
    """Result of agent deployment"""
    success: bool
    agent_id: Optional[str] = None
    agent_url: Optional[str] = None
    deployment_id: Optional[str] = None
    error: Optional[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class CopilotStudioAgentDeployer:
    """Handles deployment and management of Copilot Studio agents"""
    
    def __init__(self, logger: Optional[StructuredLogger] = None):
        self.logger = logger or StructuredLogger()
        self._session: Optional[aiohttp.ClientSession] = None
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        
        # Microsoft Graph API endpoints
        self.graph_base_url = "https://graph.microsoft.com/v1.0"
        self.copilot_base_url = "https://api.powerplatform.com/copilot/v1"
        
    async def start(self):
        """Initialize the deployer"""
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60)
        )
        self.logger.info("Copilot Studio Agent Deployer started")
    
    async def stop(self):
        """Clean up resources"""
        if self._session:
            await self._session.close()
        self.logger.info("Copilot Studio Agent Deployer stopped")
    
    async def _get_access_token(self, config: DeploymentConfig) -> str:
        """Get OAuth access token for Microsoft Graph API"""
        if (self._access_token and self._token_expires_at and 
            datetime.now(timezone.utc) < self._token_expires_at):
            return self._access_token
        
        token_url = f"https://login.microsoftonline.com/{config.tenant_id}/oauth2/v2.0/token"
        
        data = {
            "grant_type": "client_credentials",
            "client_id": config.application_id,
            "client_secret": config.client_secret,
            "scope": "https://graph.microsoft.com/.default"
        }
        
        async with self._session.post(token_url, data=data) as response:
            if response.status == 200:
                token_data = await response.json()
                self._access_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 3600)
                self._token_expires_at = datetime.now(timezone.utc).replace(
                    second=0, microsecond=0
                ) + timedelta(seconds=expires_in - 300)  # 5 min buffer
                
                self.logger.info("Access token obtained successfully")
                return self._access_token
            else:
                error_text = await response.text()
                raise Exception(f"Failed to get access token: {error_text}")
    
    async def deploy_agent(self, config: DeploymentConfig) -> DeploymentResult:
        """Deploy a new Copilot Studio agent"""
        correlation_id = get_correlation_id()
        
        self.logger.info("Starting agent deployment",
                        environment=config.environment.value,
                        agent_name=config.agent_name,
                        correlation_id=correlation_id)
        
        try:
            # Get access token
            access_token = await self._get_access_token(config)
            
            # Load agent manifest
            manifest = await self._load_agent_manifest(config)
            
            # Validate webhook endpoint
            webhook_valid = await self._validate_webhook_endpoint(config.webhook_url)
            if not webhook_valid:
                return DeploymentResult(
                    success=False,
                    error="Webhook endpoint validation failed"
                )
            
            # Create the agent
            agent_id = await self._create_agent(access_token, manifest, config)
            
            # Configure webhook
            await self._configure_webhook(access_token, agent_id, config)
            
            # Configure permissions
            await self._configure_permissions(access_token, agent_id, config)
            
            # Test the deployment
            test_result = await self._test_agent_deployment(access_token, agent_id, config)
            
            # Generate agent URL
            agent_url = self._generate_agent_url(agent_id, config)
            
            deployment_result = DeploymentResult(
                success=True,
                agent_id=agent_id,
                agent_url=agent_url,
                deployment_id=str(uuid.uuid4()),
                warnings=test_result.get("warnings", [])
            )
            
            self.logger.info("Agent deployment completed successfully",
                           agent_id=agent_id,
                           agent_url=agent_url,
                           correlation_id=correlation_id)
            
            return deployment_result
            
        except Exception as e:
            self.logger.error("Agent deployment failed",
                            error=str(e),
                            correlation_id=correlation_id)
            
            return DeploymentResult(
                success=False,
                error=str(e)
            )
    
    async def _load_agent_manifest(self, config: DeploymentConfig) -> Dict[str, Any]:
        """Load and customize agent manifest"""
        # Load base manifest
        manifest_path = "app/config/copilot_agent_manifest.json"
        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
        except FileNotFoundError:
            # Create minimal manifest if file not found
            manifest = {
                "name": config.agent_name,
                "description": config.agent_description,
                "version": "1.0.0"
            }
        
        # Customize for environment
        manifest["name"] = config.agent_name
        manifest["description"] = config.agent_description
        manifest["languages"] = config.supported_languages
        
        # Update endpoints
        if "endpoints" not in manifest:
            manifest["endpoints"] = {}
        
        manifest["endpoints"]["webhook"] = {
            "url": config.webhook_url,
            "method": "POST",
            "authentication": {
                "type": "signature",
                "signatureHeader": "X-Hub-Signature-256",
                "algorithm": "sha256"
            }
        }
        
        # Environment-specific customizations
        if config.environment == DeploymentEnvironment.DEVELOPMENT:
            manifest["name"] += " (Dev)"
            manifest["categories"] = ["Development", "Productivity"]
        elif config.environment == DeploymentEnvironment.STAGING:
            manifest["name"] += " (Test)"
            manifest["categories"] = ["Testing", "Productivity"]
        else:  # Production
            manifest["categories"] = ["Productivity", "Developer Tools", "AI"]
        
        return manifest
    
    async def _validate_webhook_endpoint(self, webhook_url: str) -> bool:
        """Validate that webhook endpoint is accessible"""
        try:
            health_url = webhook_url.replace("/webhook", "/webhook/health")
            
            async with self._session.get(health_url) as response:
                if response.status == 200:
                    health_data = await response.json()
                    return health_data.get("status") == "healthy"
                return False
                
        except Exception as e:
            self.logger.error("Webhook validation failed", error=str(e), url=webhook_url)
            return False
    
    async def _create_agent(self, access_token: str, manifest: Dict[str, Any], 
                          config: DeploymentConfig) -> str:
        """Create the Copilot Studio agent"""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # Copilot Studio agent creation payload
        agent_payload = {
            "displayName": manifest["name"],
            "description": manifest["description"],
            "capabilities": manifest.get("capabilities", {}),
            "conversationStarters": manifest.get("conversationStarters", []),
            "configuration": {
                "defaultLocale": "en-US",
                "supportedLocales": [f"{lang}-{lang.upper()}" for lang in config.supported_languages]
            }
        }
        
        # Create agent via Microsoft Graph API
        create_url = f"{self.copilot_base_url}/agents"
        
        async with self._session.post(create_url, headers=headers, json=agent_payload) as response:
            if response.status == 201:
                agent_data = await response.json()
                agent_id = agent_data["id"]
                
                self.logger.info("Agent created successfully", agent_id=agent_id)
                return agent_id
            else:
                error_text = await response.text()
                raise Exception(f"Failed to create agent: {error_text}")
    
    async def _configure_webhook(self, access_token: str, agent_id: str, 
                               config: DeploymentConfig):
        """Configure webhook for the agent"""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        webhook_config = {
            "url": config.webhook_url,
            "secret": config.webhook_secret,
            "events": ["message", "invoke", "conversationStart", "conversationEnd"]
        }
        
        webhook_url = f"{self.copilot_base_url}/agents/{agent_id}/webhook"
        
        async with self._session.put(webhook_url, headers=headers, json=webhook_config) as response:
            if response.status not in [200, 201]:
                error_text = await response.text()
                raise Exception(f"Failed to configure webhook: {error_text}")
        
        self.logger.info("Webhook configured successfully", agent_id=agent_id)
    
    async def _configure_permissions(self, access_token: str, agent_id: str,
                                   config: DeploymentConfig):
        """Configure permissions for the agent"""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        permissions_config = {
            "requiredPermissions": [
                "User.Read",
                "Files.ReadWrite",
                "Chat.ReadWrite"
            ],
            "optionalPermissions": [
                "OneDrive.ReadWrite",
                "Sites.ReadWrite.All"
            ]
        }
        
        permissions_url = f"{self.copilot_base_url}/agents/{agent_id}/permissions"
        
        async with self._session.put(permissions_url, headers=headers, json=permissions_config) as response:
            if response.status not in [200, 201]:
                error_text = await response.text()
                self.logger.warning("Failed to configure permissions", error=error_text)
                # Don't fail deployment for permission issues
        
        self.logger.info("Permissions configured", agent_id=agent_id)
    
    async def _test_agent_deployment(self, access_token: str, agent_id: str,
                                   config: DeploymentConfig) -> Dict[str, Any]:
        """Test the deployed agent"""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        test_results = {"warnings": []}
        
        # Test 1: Agent status check
        status_url = f"{self.copilot_base_url}/agents/{agent_id}"
        async with self._session.get(status_url, headers=headers) as response:
            if response.status != 200:
                test_results["warnings"].append("Agent status check failed")
        
        # Test 2: Webhook connectivity
        webhook_test_payload = {
            "activities": [{
                "type": "event",
                "id": "test-event",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "value": {"type": "deploymentTest"}
            }]
        }
        
        try:
            async with self._session.post(config.webhook_url, json=webhook_test_payload) as response:
                if response.status not in [200, 201]:
                    test_results["warnings"].append("Webhook connectivity test failed")
        except Exception:
            test_results["warnings"].append("Webhook connectivity test failed")
        
        return test_results
    
    def _generate_agent_url(self, agent_id: str, config: DeploymentConfig) -> str:
        """Generate the agent URL for users"""
        base_url = "https://copilotstudio.microsoft.com"
        
        if config.environment == DeploymentEnvironment.DEVELOPMENT:
            return f"{base_url}/environments/development/agents/{agent_id}"
        elif config.environment == DeploymentEnvironment.STAGING:
            return f"{base_url}/environments/staging/agents/{agent_id}"
        else:
            return f"{base_url}/agents/{agent_id}"
    
    async def get_agent_status(self, agent_id: str, config: DeploymentConfig) -> Dict[str, Any]:
        """Get current status of deployed agent"""
        try:
            access_token = await self._get_access_token(config)
            headers = {"Authorization": f"Bearer {access_token}"}
            
            status_url = f"{self.copilot_base_url}/agents/{agent_id}"
            
            async with self._session.get(status_url, headers=headers) as response:
                if response.status == 200:
                    agent_data = await response.json()
                    
                    return {
                        "agent_id": agent_id,
                        "status": AgentStatus.DEPLOYED.value,
                        "name": agent_data.get("displayName"),
                        "description": agent_data.get("description"),
                        "created_at": agent_data.get("createdDateTime"),
                        "last_modified": agent_data.get("lastModifiedDateTime"),
                        "webhook_configured": bool(agent_data.get("webhookUrl")),
                        "environment": config.environment.value
                    }
                else:
                    return {
                        "agent_id": agent_id,
                        "status": AgentStatus.FAILED.value,
                        "error": f"HTTP {response.status}"
                    }
                    
        except Exception as e:
            return {
                "agent_id": agent_id,
                "status": AgentStatus.FAILED.value,
                "error": str(e)
            }
    
    async def update_agent(self, agent_id: str, config: DeploymentConfig,
                          manifest: Optional[Dict[str, Any]] = None) -> DeploymentResult:
        """Update existing agent configuration"""
        correlation_id = get_correlation_id()
        
        self.logger.info("Starting agent update",
                        agent_id=agent_id,
                        environment=config.environment.value,
                        correlation_id=correlation_id)
        
        try:
            access_token = await self._get_access_token(config)
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Load manifest if not provided
            if manifest is None:
                manifest = await self._load_agent_manifest(config)
            
            # Update agent
            update_payload = {
                "displayName": manifest["name"],
                "description": manifest["description"],
                "capabilities": manifest.get("capabilities", {}),
                "conversationStarters": manifest.get("conversationStarters", [])
            }
            
            update_url = f"{self.copilot_base_url}/agents/{agent_id}"
            
            async with self._session.patch(update_url, headers=headers, json=update_payload) as response:
                if response.status not in [200, 204]:
                    error_text = await response.text()
                    raise Exception(f"Failed to update agent: {error_text}")
            
            # Update webhook if needed
            await self._configure_webhook(access_token, agent_id, config)
            
            self.logger.info("Agent updated successfully",
                           agent_id=agent_id,
                           correlation_id=correlation_id)
            
            return DeploymentResult(
                success=True,
                agent_id=agent_id,
                agent_url=self._generate_agent_url(agent_id, config)
            )
            
        except Exception as e:
            self.logger.error("Agent update failed",
                            agent_id=agent_id,
                            error=str(e),
                            correlation_id=correlation_id)
            
            return DeploymentResult(
                success=False,
                error=str(e)
            )
    
    async def delete_agent(self, agent_id: str, config: DeploymentConfig) -> bool:
        """Delete agent from Copilot Studio"""
        try:
            access_token = await self._get_access_token(config)
            headers = {"Authorization": f"Bearer {access_token}"}
            
            delete_url = f"{self.copilot_base_url}/agents/{agent_id}"
            
            async with self._session.delete(delete_url, headers=headers) as response:
                success = response.status in [200, 204, 404]  # 404 means already deleted
                
                if success:
                    self.logger.info("Agent deleted successfully", agent_id=agent_id)
                else:
                    error_text = await response.text()
                    self.logger.error("Failed to delete agent",
                                    agent_id=agent_id, error=error_text)
                
                return success
                
        except Exception as e:
            self.logger.error("Agent deletion failed",
                            agent_id=agent_id, error=str(e))
            return False


# Global deployer instance
_agent_deployer: Optional[CopilotStudioAgentDeployer] = None


async def get_agent_deployer() -> CopilotStudioAgentDeployer:
    """Get agent deployer instance"""
    global _agent_deployer
    if _agent_deployer is None:
        _agent_deployer = CopilotStudioAgentDeployer()
        await _agent_deployer.start()
    return _agent_deployer