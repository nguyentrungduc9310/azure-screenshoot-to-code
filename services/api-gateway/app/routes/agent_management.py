"""
Agent Management API Routes
FastAPI endpoints for managing Copilot Studio agent deployment and configuration
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Body, Query
from pydantic import BaseModel, Field, validator

from app.copilot.agent_deployer import (
    CopilotStudioAgentDeployer, get_agent_deployer,
    DeploymentConfig, DeploymentEnvironment, DeploymentResult
)

try:
    from shared.monitoring.structured_logger import StructuredLogger
    from shared.monitoring.correlation import set_correlation_id
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger


# Request/Response Models
class DeploymentConfigRequest(BaseModel):
    """Request model for agent deployment configuration"""
    environment: str = Field(..., description="Deployment environment")
    tenant_id: str = Field(..., description="Azure tenant ID")
    application_id: str = Field(..., description="Azure application ID")  
    client_secret: str = Field(..., description="Azure client secret")
    webhook_url: str = Field(..., description="Webhook endpoint URL")
    webhook_secret: str = Field(..., description="Webhook secret for signature verification")
    
    agent_name: Optional[str] = Field("Screenshot to Code Assistant", description="Agent display name")
    agent_description: Optional[str] = Field(
        "AI-powered assistant that converts UI screenshots into clean, production-ready code",
        description="Agent description"
    )
    supported_languages: Optional[List[str]] = Field(
        ["en", "vi", "fr", "de", "ja", "zh"],
        description="Supported languages"
    )
    
    @validator('environment')
    def validate_environment(cls, v):
        try:
            DeploymentEnvironment(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid environment. Must be one of: {[e.value for e in DeploymentEnvironment]}")


class AgentUpdateRequest(BaseModel):
    """Request model for agent updates"""
    agent_name: Optional[str] = Field(None, description="Updated agent name")
    agent_description: Optional[str] = Field(None, description="Updated agent description")
    webhook_url: Optional[str] = Field(None, description="Updated webhook URL")
    webhook_secret: Optional[str] = Field(None, description="Updated webhook secret")
    supported_languages: Optional[List[str]] = Field(None, description="Updated supported languages")


class DeploymentStatusResponse(BaseModel):
    """Response model for deployment status"""
    agent_id: str
    status: str
    name: Optional[str]
    description: Optional[str]
    environment: str
    created_at: Optional[str]
    last_modified: Optional[str]
    webhook_configured: bool
    agent_url: Optional[str]
    error: Optional[str] = None


class DeploymentResultResponse(BaseModel):
    """Response model for deployment operations"""
    success: bool
    agent_id: Optional[str] = None
    agent_url: Optional[str] = None
    deployment_id: Optional[str] = None
    error: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class AgentListResponse(BaseModel):
    """Response model for agent list"""
    agents: List[DeploymentStatusResponse]
    total_count: int
    environment_filter: Optional[str] = None


# Create router
router = APIRouter(prefix="/agent-management", tags=["agent-management"])

# Initialize logger
logger = StructuredLogger(service_name="agent-management")


@router.post("/deploy", response_model=DeploymentResultResponse)
async def deploy_agent(
    config_request: DeploymentConfigRequest = Body(...),
    deployer: CopilotStudioAgentDeployer = Depends(get_agent_deployer)
):
    """Deploy a new Copilot Studio agent"""
    correlation_id = set_correlation_id()
    
    try:
        # Convert request to deployment config
        config = DeploymentConfig(
            environment=DeploymentEnvironment(config_request.environment),
            tenant_id=config_request.tenant_id,
            application_id=config_request.application_id,
            client_secret=config_request.client_secret,
            webhook_url=config_request.webhook_url,
            webhook_secret=config_request.webhook_secret,
            agent_name=config_request.agent_name,
            agent_description=config_request.agent_description,
            supported_languages=config_request.supported_languages
        )
        
        # Deploy the agent
        result = await deployer.deploy_agent(config)
        
        logger.info("Agent deployment completed",
                   success=result.success,
                   agent_id=result.agent_id,
                   environment=config.environment.value,
                   correlation_id=correlation_id)
        
        return DeploymentResultResponse(
            success=result.success,
            agent_id=result.agent_id,
            agent_url=result.agent_url,
            deployment_id=result.deployment_id,
            error=result.error,
            warnings=result.warnings
        )
        
    except Exception as e:
        logger.error("Agent deployment failed",
                    error=str(e),
                    correlation_id=correlation_id)
        raise HTTPException(status_code=500, detail=f"Deployment failed: {str(e)}")


@router.get("/agents/{agent_id}/status", response_model=DeploymentStatusResponse)
async def get_agent_status(
    agent_id: str,
    environment: str = Query(..., description="Deployment environment"),
    tenant_id: str = Query(..., description="Azure tenant ID"),
    application_id: str = Query(..., description="Azure application ID"),
    client_secret: str = Query(..., description="Azure client secret"),
    deployer: CopilotStudioAgentDeployer = Depends(get_agent_deployer)
):
    """Get status of a deployed agent"""
    try:
        # Create minimal config for status check
        config = DeploymentConfig(
            environment=DeploymentEnvironment(environment),
            tenant_id=tenant_id,
            application_id=application_id,
            client_secret=client_secret,
            webhook_url="",  # Not needed for status check
            webhook_secret=""  # Not needed for status check
        )
        
        status = await deployer.get_agent_status(agent_id, config)
        
        return DeploymentStatusResponse(
            agent_id=status["agent_id"],
            status=status["status"],
            name=status.get("name"),
            description=status.get("description"),
            environment=status.get("environment", environment),
            created_at=status.get("created_at"),
            last_modified=status.get("last_modified"),
            webhook_configured=status.get("webhook_configured", False),
            agent_url=status.get("agent_url"),
            error=status.get("error")
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to get agent status",
                    agent_id=agent_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


@router.put("/agents/{agent_id}", response_model=DeploymentResultResponse)
async def update_agent(
    agent_id: str,
    update_request: AgentUpdateRequest = Body(...),
    environment: str = Query(..., description="Deployment environment"),
    tenant_id: str = Query(..., description="Azure tenant ID"),
    application_id: str = Query(..., description="Azure application ID"),
    client_secret: str = Query(..., description="Azure client secret"),
    deployer: CopilotStudioAgentDeployer = Depends(get_agent_deployer)
):
    """Update an existing agent"""
    correlation_id = set_correlation_id()
    
    try:
        # Create config with updated values
        config = DeploymentConfig(
            environment=DeploymentEnvironment(environment),
            tenant_id=tenant_id,
            application_id=application_id,
            client_secret=client_secret,
            webhook_url=update_request.webhook_url or "",
            webhook_secret=update_request.webhook_secret or "",
            agent_name=update_request.agent_name or "Screenshot to Code Assistant",
            agent_description=update_request.agent_description or "",
            supported_languages=update_request.supported_languages or ["en"]
        )
        
        # Update the agent
        result = await deployer.update_agent(agent_id, config)
        
        logger.info("Agent update completed",
                   success=result.success,
                   agent_id=agent_id,
                   correlation_id=correlation_id)
        
        return DeploymentResultResponse(
            success=result.success,
            agent_id=result.agent_id,
            agent_url=result.agent_url,
            error=result.error,
            warnings=result.warnings
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Agent update failed",
                    agent_id=agent_id, error=str(e),
                    correlation_id=correlation_id)
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")


@router.delete("/agents/{agent_id}")
async def delete_agent(
    agent_id: str,
    environment: str = Query(..., description="Deployment environment"),
    tenant_id: str = Query(..., description="Azure tenant ID"),
    application_id: str = Query(..., description="Azure application ID"),  
    client_secret: str = Query(..., description="Azure client secret"),
    deployer: CopilotStudioAgentDeployer = Depends(get_agent_deployer)
):
    """Delete an agent"""
    correlation_id = set_correlation_id()
    
    try:
        # Create minimal config for deletion
        config = DeploymentConfig(
            environment=DeploymentEnvironment(environment),
            tenant_id=tenant_id,
            application_id=application_id,
            client_secret=client_secret,
            webhook_url="",  # Not needed for deletion
            webhook_secret=""  # Not needed for deletion
        )
        
        success = await deployer.delete_agent(agent_id, config)
        
        if success:
            logger.info("Agent deleted successfully",
                       agent_id=agent_id,
                       correlation_id=correlation_id)
            return {"success": True, "message": f"Agent {agent_id} deleted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete agent")
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Agent deletion failed",
                    agent_id=agent_id, error=str(e),
                    correlation_id=correlation_id)
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")


@router.post("/agents/{agent_id}/test")
async def test_agent(
    agent_id: str,
    environment: str = Query(..., description="Deployment environment"),
    webhook_url: str = Query(..., description="Webhook URL to test"),
):
    """Test agent webhook connectivity"""
    correlation_id = set_correlation_id()
    
    try:
        import aiohttp
        
        # Create test payload
        test_payload = {
            "activities": [{
                "type": "event",
                "id": f"test-{correlation_id}",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "from": {"id": "test-user", "name": "Test User"},
                "conversation": {"id": "test-conversation"},
                "value": {"type": "deploymentTest"}
            }]
        }
        
        # Send test request
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=test_payload) as response:
                success = response.status in [200, 201]
                response_text = await response.text()
                
                result = {
                    "success": success,
                    "status_code": response.status,
                    "response": response_text[:500] if response_text else None,
                    "timestamp": datetime.utcnow().isoformat(),
                    "correlation_id": correlation_id
                }
                
                logger.info("Agent webhook test completed",
                           agent_id=agent_id,
                           success=success,
                           status_code=response.status,
                           correlation_id=correlation_id)
                
                return result
                
    except Exception as e:
        logger.error("Agent webhook test failed",
                    agent_id=agent_id, error=str(e),
                    correlation_id=correlation_id)
        
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
            "correlation_id": correlation_id
        }


@router.get("/environments")
async def get_supported_environments():
    """Get list of supported deployment environments"""
    return {
        "environments": [
            {
                "id": env.value,
                "name": env.value.title(),
                "description": f"{env.value.title()} environment"
            }
            for env in DeploymentEnvironment
        ]
    }


@router.get("/manifest")
async def get_agent_manifest(
    environment: str = Query("development", description="Environment to generate manifest for")
):
    """Get agent manifest template"""
    try:
        env = DeploymentEnvironment(environment)
        
        # Load and customize manifest
        manifest_path = "app/config/copilot_agent_manifest.json"
        try:
            import json
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
        except FileNotFoundError:
            manifest = {
                "name": "Screenshot to Code Assistant",
                "description": "AI-powered assistant that converts UI screenshots into clean, production-ready code",
                "version": "1.0.0"
            }
        
        # Environment-specific customizations
        if env == DeploymentEnvironment.DEVELOPMENT:
            manifest["name"] += " (Dev)"
        elif env == DeploymentEnvironment.STAGING:
            manifest["name"] += " (Test)"
        
        return manifest
        
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid environment: {environment}")


@router.get("/health")
async def get_agent_management_health():
    """Health check for agent management service"""
    return {
        "service": "agent-management",
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "supported_environments": [env.value for env in DeploymentEnvironment],
        "features": {
            "deployment": True,
            "status_monitoring": True,
            "updates": True,
            "deletion": True,
            "testing": True
        }
    }