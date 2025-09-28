"""
Test cases for Agent Management functionality
"""
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch, mock_open
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.routes.agent_management import router
from app.copilot.agent_deployer import (
    CopilotStudioAgentDeployer, DeploymentConfig, DeploymentEnvironment,
    DeploymentResult, AgentStatus
)


# Test fixtures
@pytest.fixture
def test_app():
    """Create test FastAPI app"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(test_app):
    """Create test client"""
    return TestClient(test_app)


@pytest.fixture
def sample_deployment_config():
    """Sample deployment configuration"""
    return {
        "environment": "development",
        "tenant_id": "test-tenant-123",
        "application_id": "test-app-456",
        "client_secret": "test-secret-789",
        "webhook_url": "https://test.example.com/webhook",
        "webhook_secret": "webhook-secret-123",
        "agent_name": "Test Screenshot Agent",
        "agent_description": "Test agent for screenshot conversion",
        "supported_languages": ["en", "vi"]
    }


@pytest.fixture
def mock_deployer():
    """Mock agent deployer"""
    deployer = AsyncMock(spec=CopilotStudioAgentDeployer)
    
    # Mock successful deployment
    deployer.deploy_agent.return_value = DeploymentResult(
        success=True,
        agent_id="agent-123",
        agent_url="https://copilotstudio.microsoft.com/agents/agent-123",
        deployment_id="deploy-456",
        warnings=[]
    )
    
    # Mock status check
    deployer.get_agent_status.return_value = {
        "agent_id": "agent-123",
        "status": AgentStatus.DEPLOYED.value,
        "name": "Test Screenshot Agent",
        "description": "Test agent for screenshot conversion",
        "environment": "development",
        "created_at": "2024-01-01T12:00:00Z",
        "last_modified": "2024-01-01T12:00:00Z",
        "webhook_configured": True,
        "agent_url": "https://copilotstudio.microsoft.com/agents/agent-123"
    }
    
    # Mock update
    deployer.update_agent.return_value = DeploymentResult(
        success=True,
        agent_id="agent-123",
        agent_url="https://copilotstudio.microsoft.com/agents/agent-123"
    )
    
    # Mock deletion
    deployer.delete_agent.return_value = True
    
    return deployer


class TestAgentDeploymentEndpoints:
    """Test agent deployment API endpoints"""
    
    @pytest.mark.asyncio
    async def test_deploy_agent_success(self, client, sample_deployment_config, mock_deployer):
        """Test successful agent deployment"""
        with patch("app.routes.agent_management.get_agent_deployer", return_value=mock_deployer):
            response = client.post("/agent-management/deploy", json=sample_deployment_config)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["agent_id"] == "agent-123"
        assert data["agent_url"] == "https://copilotstudio.microsoft.com/agents/agent-123"
        assert data["deployment_id"] == "deploy-456"
        assert "timestamp" in data
        
        # Verify deployer was called with correct config
        mock_deployer.deploy_agent.assert_called_once()
        call_args = mock_deployer.deploy_agent.call_args[0][0]
        assert call_args.environment == DeploymentEnvironment.DEVELOPMENT
        assert call_args.tenant_id == "test-tenant-123"
        assert call_args.agent_name == "Test Screenshot Agent"
    
    def test_deploy_agent_invalid_environment(self, client, sample_deployment_config):
        """Test deployment with invalid environment"""
        sample_deployment_config["environment"] = "invalid"
        
        response = client.post("/agent-management/deploy", json=sample_deployment_config)
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_deploy_agent_failure(self, client, sample_deployment_config):
        """Test failed agent deployment"""
        mock_deployer = AsyncMock()
        mock_deployer.deploy_agent.return_value = DeploymentResult(
            success=False,
            error="Deployment failed: Invalid credentials"
        )
        
        with patch("app.routes.agent_management.get_agent_deployer", return_value=mock_deployer):
            response = client.post("/agent-management/deploy", json=sample_deployment_config)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is False
        assert data["error"] == "Deployment failed: Invalid credentials"
        assert data["agent_id"] is None
    
    def test_deploy_agent_missing_fields(self, client):
        """Test deployment with missing required fields"""
        incomplete_config = {
            "environment": "development",
            "tenant_id": "test-tenant"
            # Missing other required fields
        }
        
        response = client.post("/agent-management/deploy", json=incomplete_config)
        
        assert response.status_code == 422  # Validation error


class TestAgentStatusEndpoints:
    """Test agent status API endpoints"""
    
    @pytest.mark.asyncio
    async def test_get_agent_status_success(self, client, mock_deployer):
        """Test successful agent status retrieval"""
        with patch("app.routes.agent_management.get_agent_deployer", return_value=mock_deployer):
            response = client.get(
                "/agent-management/agents/agent-123/status",
                params={
                    "environment": "development",
                    "tenant_id": "test-tenant-123",
                    "application_id": "test-app-456",
                    "client_secret": "test-secret-789"
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["agent_id"] == "agent-123"
        assert data["status"] == "deployed"
        assert data["name"] == "Test Screenshot Agent"
        assert data["environment"] == "development"
        assert data["webhook_configured"] is True
    
    def test_get_agent_status_missing_params(self, client):
        """Test status check with missing parameters"""
        response = client.get("/agent-management/agents/agent-123/status")
        
        assert response.status_code == 422  # Missing required query parameters


class TestAgentUpdateEndpoints:
    """Test agent update API endpoints"""
    
    @pytest.mark.asyncio
    async def test_update_agent_success(self, client, mock_deployer):
        """Test successful agent update"""
        update_data = {
            "agent_name": "Updated Agent Name",
            "agent_description": "Updated description",
            "supported_languages": ["en", "fr", "de"]
        }
        
        with patch("app.routes.agent_management.get_agent_deployer", return_value=mock_deployer):
            response = client.put(
                "/agent-management/agents/agent-123",
                json=update_data,
                params={
                    "environment": "development",
                    "tenant_id": "test-tenant-123",
                    "application_id": "test-app-456",
                    "client_secret": "test-secret-789"
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["agent_id"] == "agent-123"
        
        # Verify update was called
        mock_deployer.update_agent.assert_called_once()


class TestAgentDeletionEndpoints:
    """Test agent deletion API endpoints"""
    
    @pytest.mark.asyncio
    async def test_delete_agent_success(self, client, mock_deployer):
        """Test successful agent deletion"""
        with patch("app.routes.agent_management.get_agent_deployer", return_value=mock_deployer):
            response = client.delete(
                "/agent-management/agents/agent-123",
                params={
                    "environment": "development",
                    "tenant_id": "test-tenant-123",
                    "application_id": "test-app-456",
                    "client_secret": "test-secret-789"
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "deleted successfully" in data["message"]
        
        # Verify deletion was called
        mock_deployer.delete_agent.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_agent_failure(self, client):
        """Test failed agent deletion"""
        mock_deployer = AsyncMock()
        mock_deployer.delete_agent.return_value = False
        
        with patch("app.routes.agent_management.get_agent_deployer", return_value=mock_deployer):
            response = client.delete(
                "/agent-management/agents/agent-123",
                params={
                    "environment": "development",
                    "tenant_id": "test-tenant-123",
                    "application_id": "test-app-456",
                    "client_secret": "test-secret-789"
                }
            )
        
        assert response.status_code == 500


class TestAgentTestingEndpoints:
    """Test agent testing API endpoints"""
    
    @patch('aiohttp.ClientSession.post')
    @pytest.mark.asyncio
    async def test_test_agent_webhook_success(self, mock_post, client):
        """Test successful webhook testing"""
        # Mock successful HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text.return_value = '{"success": true}'
        mock_post.return_value.__aenter__.return_value = mock_response
        
        response = client.post(
            "/agent-management/agents/agent-123/test",
            params={
                "environment": "development",
                "webhook_url": "https://test.example.com/webhook"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["status_code"] == 200
        assert "correlation_id" in data
    
    @patch('aiohttp.ClientSession.post')
    @pytest.mark.asyncio
    async def test_test_agent_webhook_failure(self, mock_post, client):
        """Test failed webhook testing"""
        # Mock failed HTTP response
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text.return_value = 'Internal Server Error'
        mock_post.return_value.__aenter__.return_value = mock_response
        
        response = client.post(
            "/agent-management/agents/agent-123/test",
            params={
                "environment": "development",
                "webhook_url": "https://test.example.com/webhook"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is False
        assert data["status_code"] == 500


class TestUtilityEndpoints:
    """Test utility API endpoints"""
    
    def test_get_supported_environments(self, client):
        """Test getting supported environments"""
        response = client.get("/agent-management/environments")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "environments" in data
        assert len(data["environments"]) == 3  # development, staging, production
        
        env_ids = [env["id"] for env in data["environments"]]
        assert "development" in env_ids
        assert "staging" in env_ids
        assert "production" in env_ids
    
    def test_get_agent_manifest(self, client):
        """Test getting agent manifest"""
        # Mock manifest file
        manifest_content = {
            "name": "Test Agent",
            "description": "Test description",
            "version": "1.0.0"
        }
        
        with patch("builtins.open", mock_open(read_data=json.dumps(manifest_content))):
            response = client.get(
                "/agent-management/manifest",
                params={"environment": "development"}
            )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "name" in data
        assert "(Dev)" in data["name"]  # Development environment suffix
    
    def test_get_agent_manifest_invalid_environment(self, client):
        """Test getting manifest with invalid environment"""
        response = client.get(
            "/agent-management/manifest",
            params={"environment": "invalid"}
        )
        
        assert response.status_code == 400
    
    def test_get_health(self, client):
        """Test health endpoint"""
        response = client.get("/agent-management/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["service"] == "agent-management"
        assert data["status"] == "healthy"
        assert "supported_environments" in data
        assert "features" in data


class TestCopilotStudioAgentDeployer:
    """Test agent deployer functionality"""
    
    @pytest.fixture
    def deployer(self):
        """Create agent deployer instance"""
        return CopilotStudioAgentDeployer()
    
    @pytest.fixture
    def deployment_config(self):
        """Create deployment configuration"""
        return DeploymentConfig(
            environment=DeploymentEnvironment.DEVELOPMENT,
            tenant_id="test-tenant-123",
            application_id="test-app-456",
            client_secret="test-secret-789",
            webhook_url="https://test.example.com/webhook",
            webhook_secret="webhook-secret-123"
        )
    
    @pytest.mark.asyncio
    async def test_load_agent_manifest(self, deployer, deployment_config):
        """Test loading and customizing agent manifest"""
        # Mock manifest file
        manifest_content = {
            "name": "Base Agent",
            "description": "Base description",
            "version": "1.0.0"
        }
        
        with patch("builtins.open", mock_open(read_data=json.dumps(manifest_content))):
            manifest = await deployer._load_agent_manifest(deployment_config)
        
        assert manifest["name"] == "Screenshot to Code Assistant"
        assert manifest["description"] == "AI-powered assistant that converts UI screenshots into clean, production-ready code"
        assert "endpoints" in manifest
        assert manifest["endpoints"]["webhook"]["url"] == deployment_config.webhook_url
    
    @pytest.mark.asyncio
    async def test_validate_webhook_endpoint_success(self, deployer):
        """Test successful webhook validation"""
        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {"status": "healthy"}
            mock_get.return_value.__aenter__.return_value = mock_response
            
            await deployer.start()
            try:
                result = await deployer._validate_webhook_endpoint("https://test.com/webhook")
                assert result is True
            finally:
                await deployer.stop()
    
    @pytest.mark.asyncio
    async def test_validate_webhook_endpoint_failure(self, deployer):
        """Test failed webhook validation"""
        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_get.return_value.__aenter__.return_value = mock_response
            
            await deployer.start()
            try:
                result = await deployer._validate_webhook_endpoint("https://test.com/webhook")
                assert result is False
            finally:
                await deployer.stop()
    
    def test_generate_agent_url(self, deployer, deployment_config):
        """Test agent URL generation"""
        agent_id = "test-agent-123"
        
        # Development environment
        url = deployer._generate_agent_url(agent_id, deployment_config)
        assert "development" in url
        assert agent_id in url
        
        # Production environment
        deployment_config.environment = DeploymentEnvironment.PRODUCTION
        url = deployer._generate_agent_url(agent_id, deployment_config)
        assert "development" not in url
        assert agent_id in url


if __name__ == "__main__":
    pytest.main([__file__])