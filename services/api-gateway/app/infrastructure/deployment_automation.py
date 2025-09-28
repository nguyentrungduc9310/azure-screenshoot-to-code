"""
Deployment Automation
Production deployment automation and CI/CD pipeline configuration
"""
import asyncio
import json
import os
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

try:
    from shared.monitoring.structured_logger import StructuredLogger
    from shared.monitoring.correlation import get_correlation_id
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger
    
    def get_correlation_id():
        import uuid
        return str(uuid.uuid4())[:8]


class DeploymentEnvironment(Enum):
    """Deployment environment types"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class DeploymentStrategy(Enum):
    """Deployment strategy types"""
    BLUE_GREEN = "blue_green"
    ROLLING = "rolling"
    CANARY = "canary"
    RECREATE = "recreate"


class PipelineStage(Enum):
    """CI/CD pipeline stages"""
    BUILD = "build"
    TEST = "test"
    SECURITY_SCAN = "security_scan"
    DEPLOY = "deploy"
    VALIDATE = "validate"
    ROLLBACK = "rollback"


@dataclass
class DeploymentConfig:
    """Deployment configuration"""
    environment: DeploymentEnvironment
    strategy: DeploymentStrategy = DeploymentStrategy.BLUE_GREEN
    auto_rollback: bool = True
    health_check_timeout: int = 300  # seconds
    deployment_timeout: int = 1800   # seconds
    pre_deployment_steps: List[str] = field(default_factory=list)
    post_deployment_steps: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.pre_deployment_steps:
            self.pre_deployment_steps = [
                "validate_environment",
                "backup_current_version", 
                "run_pre_deployment_tests"
            ]
        
        if not self.post_deployment_steps:
            self.post_deployment_steps = [
                "run_smoke_tests",
                "validate_deployment",
                "update_monitoring",
                "send_deployment_notification"
            ]


@dataclass
class BuildConfiguration:
    """Build configuration"""
    build_tool: str = "docker"
    dockerfile_path: str = "Dockerfile"
    build_context: str = "."
    build_args: Dict[str, str] = field(default_factory=dict)
    image_registry: str = "screenshottocode.azurecr.io"
    image_name: str = "api-gateway"
    cache_enabled: bool = True
    multi_stage_build: bool = True
    
    def get_image_tag(self, build_id: str, environment: str) -> str:
        """Generate image tag"""
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        return f"{self.image_name}:{environment}-{build_id}-{timestamp}"


@dataclass
class TestConfiguration:
    """Test configuration"""
    unit_tests_enabled: bool = True
    integration_tests_enabled: bool = True
    e2e_tests_enabled: bool = True
    performance_tests_enabled: bool = False
    security_tests_enabled: bool = True
    test_coverage_threshold: float = 80.0
    test_timeout: int = 1800  # seconds
    
    def get_test_stages(self) -> List[Dict[str, Any]]:
        """Get test stages configuration"""
        stages = []
        
        if self.unit_tests_enabled:
            stages.append({
                "name": "unit_tests",
                "command": "python -m pytest tests/unit --cov=app --cov-report=xml",
                "timeout": 300,
                "required": True
            })
        
        if self.integration_tests_enabled:
            stages.append({
                "name": "integration_tests", 
                "command": "python -m pytest tests/integration --cov=app --cov-append",
                "timeout": 600,
                "required": True
            })
        
        if self.e2e_tests_enabled:
            stages.append({
                "name": "e2e_tests",
                "command": "python -m pytest tests/e2e",
                "timeout": 900,
                "required": False
            })
        
        if self.performance_tests_enabled:
            stages.append({
                "name": "performance_tests",
                "command": "python -m pytest tests/performance",
                "timeout": 1200,
                "required": False
            })
        
        if self.security_tests_enabled:
            stages.append({
                "name": "security_tests",
                "command": "safety check && bandit -r app/",
                "timeout": 300,
                "required": True
            })
        
        return stages


class DeploymentAutomation:
    """Deployment automation and CI/CD pipeline manager"""
    
    def __init__(self, logger: Optional[StructuredLogger] = None):
        self.logger = logger or StructuredLogger()
        
        # Configuration
        self.deployment_configs: Dict[str, DeploymentConfig] = {}
        self.build_config = BuildConfiguration()
        self.test_config = TestConfiguration()
        
        # Pipeline state
        self.pipeline_runs: Dict[str, Dict[str, Any]] = {}
        self.deployment_history: List[Dict[str, Any]] = []
        
        # Initialize default configurations
        self._initialize_default_configs()
    
    def _initialize_default_configs(self):
        """Initialize default deployment configurations"""
        
        # Development environment
        self.deployment_configs["development"] = DeploymentConfig(
            environment=DeploymentEnvironment.DEVELOPMENT,
            strategy=DeploymentStrategy.RECREATE,
            auto_rollback=False,
            health_check_timeout=60,
            deployment_timeout=300
        )
        
        # Testing environment
        self.deployment_configs["testing"] = DeploymentConfig(
            environment=DeploymentEnvironment.TESTING,
            strategy=DeploymentStrategy.ROLLING,
            auto_rollback=True,
            health_check_timeout=120,
            deployment_timeout=600
        )
        
        # Staging environment
        self.deployment_configs["staging"] = DeploymentConfig(
            environment=DeploymentEnvironment.STAGING,
            strategy=DeploymentStrategy.BLUE_GREEN,
            auto_rollback=True,
            health_check_timeout=180,
            deployment_timeout=900
        )
        
        # Production environment
        self.deployment_configs["production"] = DeploymentConfig(
            environment=DeploymentEnvironment.PRODUCTION,
            strategy=DeploymentStrategy.CANARY,
            auto_rollback=True,
            health_check_timeout=300,
            deployment_timeout=1800
        )
    
    async def generate_github_actions_workflow(self) -> Dict[str, Any]:
        """Generate GitHub Actions workflow for CI/CD"""
        
        workflow = {
            "name": "Screenshot-to-Code CI/CD Pipeline",
            "on": {
                "push": {
                    "branches": ["main", "develop", "staging"]
                },
                "pull_request": {
                    "branches": ["main", "develop"]
                },
                "workflow_dispatch": {
                    "inputs": {
                        "environment": {
                            "description": "Deployment environment",
                            "required": True,
                            "default": "staging",
                            "type": "choice",
                            "options": ["development", "testing", "staging", "production"]
                        },
                        "skip_tests": {
                            "description": "Skip test execution",
                            "required": False,
                            "default": False,
                            "type": "boolean"
                        }
                    }
                }
            },
            "env": {
                "AZURE_WEBAPP_NAME": "sktc-${{ github.ref_name }}-api",
                "AZURE_WEBAPP_PACKAGE_PATH": ".",
                "PYTHON_VERSION": "3.11",
                "NODE_VERSION": "18"
            },
            "jobs": {}
        }
        
        # Build job
        workflow["jobs"]["build"] = {
            "runs-on": "ubuntu-latest",
            "outputs": {
                "image-tag": "${{ steps.build.outputs.image-tag }}",
                "build-id": "${{ steps.build.outputs.build-id }}"
            },
            "steps": [
                {
                    "name": "Checkout code",
                    "uses": "actions/checkout@v4"
                },
                {
                    "name": "Set up Python",
                    "uses": "actions/setup-python@v4",
                    "with": {
                        "python-version": "${{ env.PYTHON_VERSION }}"
                    }
                },
                {
                    "name": "Cache dependencies",
                    "uses": "actions/cache@v3",
                    "with": {
                        "path": "~/.cache/pip",
                        "key": "${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}",
                        "restore-keys": "${{ runner.os }}-pip-"
                    }
                },
                {
                    "name": "Install dependencies",
                    "run": "pip install -r requirements.txt"
                },
                {
                    "name": "Build application",
                    "id": "build",
                    "run": """
                        BUILD_ID="${{ github.run_number }}"
                        ENVIRONMENT="${{ github.ref_name }}"
                        IMAGE_TAG="${{ env.AZURE_WEBAPP_NAME }}:${ENVIRONMENT}-${BUILD_ID}-$(date +%Y%m%d-%H%M%S)"
                        
                        echo "build-id=${BUILD_ID}" >> $GITHUB_OUTPUT
                        echo "image-tag=${IMAGE_TAG}" >> $GITHUB_OUTPUT
                        
                        # Build application package
                        python setup.py build
                    """
                },
                {
                    "name": "Upload build artifacts",
                    "uses": "actions/upload-artifact@v3",
                    "with": {
                        "name": "build-artifacts-${{ steps.build.outputs.build-id }}",
                        "path": |
                            dist/
                            build/
                        "retention-days": 7
                    }
                }
            ]
        }
        
        # Test job
        workflow["jobs"]["test"] = {
            "runs-on": "ubuntu-latest",
            "needs": "build",
            "if": "${{ !inputs.skip_tests }}",
            "strategy": {
                "matrix": {
                    "test-type": ["unit", "integration", "security"]
                }
            },
            "steps": [
                {
                    "name": "Checkout code",
                    "uses": "actions/checkout@v4"
                },
                {
                    "name": "Set up Python",
                    "uses": "actions/setup-python@v4",
                    "with": {
                        "python-version": "${{ env.PYTHON_VERSION }}"
                    }
                },
                {
                    "name": "Download build artifacts",
                    "uses": "actions/download-artifact@v3",
                    "with": {
                        "name": "build-artifacts-${{ needs.build.outputs.build-id }}"
                    }
                },
                {
                    "name": "Install test dependencies",
                    "run": "pip install -r requirements-test.txt"
                },
                {
                    "name": "Run tests",
                    "run": """
                        case "${{ matrix.test-type }}" in
                          "unit")
                            python -m pytest tests/unit --cov=app --cov-report=xml --cov-report=html
                            ;;
                          "integration")
                            python -m pytest tests/integration --cov=app --cov-append
                            ;;
                          "security")
                            safety check
                            bandit -r app/ -f json -o bandit-report.json
                            ;;
                        esac
                    """
                },
                {
                    "name": "Upload test results",
                    "uses": "actions/upload-artifact@v3",
                    "if": "always()",
                    "with": {
                        "name": "test-results-${{ matrix.test-type }}-${{ needs.build.outputs.build-id }}",
                        "path": |
                            coverage.xml
                            htmlcov/
                            bandit-report.json
                            pytest-report.xml
                        "retention-days": 30
                    }
                }
            ]
        }
        
        # Security scan job
        workflow["jobs"]["security-scan"] = {
            "runs-on": "ubuntu-latest",
            "needs": "build",
            "steps": [
                {
                    "name": "Checkout code",
                    "uses": "actions/checkout@v4"
                },
                {
                    "name": "Run Trivy vulnerability scanner",
                    "uses": "aquasecurity/trivy-action@master",
                    "with": {
                        "scan-type": "fs",
                        "scan-ref": ".",
                        "format": "sarif",
                        "output": "trivy-results.sarif"
                    }
                },
                {
                    "name": "Upload Trivy scan results",
                    "uses": "github/codeql-action/upload-sarif@v2",
                    "if": "always()",
                    "with": {
                        "sarif_file": "trivy-results.sarif"
                    }
                }
            ]
        }
        
        # Deploy job
        workflow["jobs"]["deploy"] = {
            "runs-on": "ubuntu-latest",
            "needs": ["build", "test", "security-scan"],
            "if": "success() && (github.ref == 'refs/heads/main' || github.ref == 'refs/heads/staging' || github.event_name == 'workflow_dispatch')",
            "environment": {
                "name": "${{ inputs.environment || (github.ref_name == 'main' && 'production' || 'staging') }}",
                "url": "${{ steps.deploy.outputs.webapp-url }}"
            },
            "steps": [
                {
                    "name": "Download build artifacts",
                    "uses": "actions/download-artifact@v3",
                    "with": {
                        "name": "build-artifacts-${{ needs.build.outputs.build-id }}"
                    }
                },
                {
                    "name": "Azure Login",
                    "uses": "azure/login@v1",
                    "with": {
                        "creds": "${{ secrets.AZURE_CREDENTIALS }}"
                    }
                },
                {
                    "name": "Deploy to Azure Web App",
                    "id": "deploy",
                    "uses": "azure/webapps-deploy@v2",
                    "with": {
                        "app-name": "${{ env.AZURE_WEBAPP_NAME }}",
                        "package": "${{ env.AZURE_WEBAPP_PACKAGE_PATH }}",
                        "slot-name": "staging"
                    }
                },
                {
                    "name": "Run deployment validation",
                    "run": """
                        # Wait for deployment to be ready
                        sleep 30
                        
                        # Run health check
                        HEALTH_URL="${{ steps.deploy.outputs.webapp-url }}/health"
                        
                        for i in {1..10}; do
                          if curl -sf "$HEALTH_URL" > /dev/null; then
                            echo "Health check passed"
                            break
                          fi
                          echo "Health check failed, attempt $i/10"
                          sleep 30
                        done
                        
                        # Run smoke tests
                        python -m pytest tests/smoke --base-url="${{ steps.deploy.outputs.webapp-url }}"
                    """
                },
                {
                    "name": "Swap deployment slots",
                    "if": "success() && github.ref == 'refs/heads/main'",
                    "run": """
                        az webapp deployment slot swap \\
                          --resource-group "${{ secrets.AZURE_RESOURCE_GROUP }}" \\
                          --name "${{ env.AZURE_WEBAPP_NAME }}" \\
                          --slot staging \\
                          --target-slot production
                    """
                }
            ]
        }
        
        # Rollback job
        workflow["jobs"]["rollback"] = {
            "runs-on": "ubuntu-latest",
            "needs": "deploy",
            "if": "failure() && needs.deploy.result == 'failure'",
            "steps": [
                {
                    "name": "Azure Login",
                    "uses": "azure/login@v1",
                    "with": {
                        "creds": "${{ secrets.AZURE_CREDENTIALS }}"
                    }
                },
                {
                    "name": "Rollback deployment",
                    "run": """
                        echo "Deployment failed, initiating rollback..."
                        
                        # Get previous deployment
                        PREVIOUS_DEPLOYMENT=$(az webapp deployment list \\
                          --resource-group "${{ secrets.AZURE_RESOURCE_GROUP }}" \\
                          --name "${{ env.AZURE_WEBAPP_NAME }}" \\
                          --query "[1].id" -o tsv)
                        
                        if [ -n "$PREVIOUS_DEPLOYMENT" ]; then
                          # Rollback to previous deployment
                          az webapp deployment slot swap \\
                            --resource-group "${{ secrets.AZURE_RESOURCE_GROUP }}" \\
                            --name "${{ env.AZURE_WEBAPP_NAME }}" \\
                            --slot production \\
                            --target-slot staging
                          
                          echo "Rollback completed successfully"
                        else
                          echo "No previous deployment found for rollback"
                        fi
                    """
                }
            ]
        }
        
        return workflow
    
    async def generate_azure_devops_pipeline(self) -> Dict[str, Any]:
        """Generate Azure DevOps pipeline YAML"""
        
        pipeline = {
            "trigger": {
                "branches": {
                    "include": ["main", "develop", "staging"]
                },
                "paths": {
                    "exclude": ["docs/*", "*.md"]
                }
            },
            "pr": {
                "branches": {
                    "include": ["main", "develop"]
                }
            },
            "variables": [
                {
                    "group": "screenshot-to-code-variables"
                },
                {
                    "name": "pythonVersion",
                    "value": "3.11"
                },
                {
                    "name": "buildConfiguration",
                    "value": "Release"
                }
            ],
            "stages": []
        }
        
        # Build stage
        build_stage = {
            "stage": "Build",
            "displayName": "Build and Test",
            "jobs": [
                {
                    "job": "BuildJob",
                    "displayName": "Build Application",
                    "pool": {
                        "vmImage": "ubuntu-latest"
                    },
                    "steps": [
                        {
                            "task": "UsePythonVersion@0",
                            "inputs": {
                                "versionSpec": "$(pythonVersion)",
                                "addToPath": True,
                                "architecture": "x64"
                            },
                            "displayName": "Use Python $(pythonVersion)"
                        },
                        {
                            "script": """
                                python -m pip install --upgrade pip
                                pip install -r requirements.txt
                                """,
                            "displayName": "Install dependencies"
                        },
                        {
                            "script": """
                                python -m pytest tests/unit --cov=app --cov-report=xml --cov-report=html --junitxml=junit/test-results.xml
                                """,
                            "displayName": "Run unit tests"
                        },
                        {
                            "script": """
                                python -m pytest tests/integration --cov=app --cov-append --junitxml=junit/integration-results.xml
                                """,
                            "displayName": "Run integration tests"
                        },
                        {
                            "script": """
                                safety check
                                bandit -r app/ -f json -o bandit-report.json
                                """,
                            "displayName": "Run security tests"
                        },
                        {
                            "task": "PublishTestResults@2",
                            "condition": "succeededOrFailed()",
                            "inputs": {
                                "testResultsFiles": "**/test-*.xml",
                                "testRunTitle": "Python Tests"
                            }
                        },
                        {
                            "task": "PublishCodeCoverageResults@1",
                            "inputs": {
                                "codeCoverageTool": "Cobertura",
                                "summaryFileLocation": "$(System.DefaultWorkingDirectory)/**/coverage.xml"
                            }
                        },
                        {
                            "task": "ArchiveFiles@2",
                            "displayName": "Archive application",
                            "inputs": {
                                "rootFolderOrFile": "$(System.DefaultWorkingDirectory)",
                                "includeRootFolder": False,
                                "archiveType": "zip",
                                "archiveFile": "$(Build.ArtifactStagingDirectory)/$(Build.BuildId).zip",
                                "replaceExistingArchive": True
                            }
                        },
                        {
                            "task": "PublishBuildArtifacts@1",
                            "displayName": "Upload package",
                            "inputs": {
                                "artifactName": "drop"
                            }
                        }
                    ]
                }
            ]
        }
        pipeline["stages"].append(build_stage)
        
        # Deploy stages for different environments
        for env_name, config in self.deployment_configs.items():
            if env_name == "development":
                continue  # Skip development environment in main pipeline
                
            deploy_stage = {
                "stage": f"Deploy{env_name.title()}",
                "displayName": f"Deploy to {env_name.title()}",
                "dependsOn": "Build",
                "condition": self._get_deployment_condition(env_name),
                "jobs": [
                    {
                        "deployment": f"Deploy{env_name.title()}Job",
                        "displayName": f"Deploy to {env_name.title()}",
                        "pool": {
                            "vmImage": "ubuntu-latest"
                        },
                        "environment": {
                            "name": f"screenshot-to-code-{env_name}",
                            "resourceName": f"app-service-{env_name}"
                        },
                        "strategy": self._get_deployment_strategy(config),
                    }
                ]
            }
            pipeline["stages"].append(deploy_stage)
        
        return pipeline
    
    def _get_deployment_condition(self, environment: str) -> str:
        """Get deployment condition for environment"""
        conditions = {
            "testing": "and(succeeded(), eq(variables['Build.SourceBranch'], 'refs/heads/develop'))",
            "staging": "and(succeeded(), eq(variables['Build.SourceBranch'], 'refs/heads/staging'))",
            "production": "and(succeeded(), eq(variables['Build.SourceBranch'], 'refs/heads/main'))"
        }
        return conditions.get(environment, "succeeded()")
    
    def _get_deployment_strategy(self, config: DeploymentConfig) -> Dict[str, Any]:
        """Get deployment strategy configuration"""
        
        base_steps = [
            {
                "task": "DownloadBuildArtifacts@0",
                "displayName": "Download artifacts",
                "inputs": {
                    "artifactName": "drop"
                }
            },
            {
                "task": "AzureWebApp@1",
                "displayName": "Deploy Azure Web App",
                "inputs": {
                    "azureSubscription": "$(azureSubscription)",
                    "appName": "$(webAppName)",
                    "package": "$(System.ArtifactsDirectory)/drop/$(Build.BuildId).zip",
                    "deploymentMethod": "auto"
                }
            }
        ]
        
        if config.strategy == DeploymentStrategy.BLUE_GREEN:
            return {
                "runOnce": {
                    "deploy": {
                        "steps": [
                            {
                                "task": "AzureWebApp@1",
                                "displayName": "Deploy to staging slot",
                                "inputs": {
                                    "azureSubscription": "$(azureSubscription)",
                                    "appName": "$(webAppName)",
                                    "package": "$(System.ArtifactsDirectory)/drop/$(Build.BuildId).zip",
                                    "slotName": "staging"
                                }
                            },
                            {
                                "task": "AzureAppServiceManage@0",
                                "displayName": "Start staging slot",
                                "inputs": {
                                    "azureSubscription": "$(azureSubscription)",
                                    "WebAppName": "$(webAppName)",
                                    "ResourceGroupName": "$(resourceGroupName)",
                                    "SourceSlot": "staging",
                                    "Action": "Start Slot"
                                }
                            },
                            {
                                "script": """
                                    echo "Running health checks on staging slot..."
                                    # Add health check logic here
                                    """,
                                "displayName": "Health check staging slot"
                            },
                            {
                                "task": "AzureAppServiceManage@0",
                                "displayName": "Swap with production slot",
                                "inputs": {
                                    "azureSubscription": "$(azureSubscription)",
                                    "WebAppName": "$(webAppName)",
                                    "ResourceGroupName": "$(resourceGroupName)",
                                    "SourceSlot": "staging",
                                    "SwapWithProduction": True
                                }
                            }
                        ]
                    }
                }
            }
        elif config.strategy == DeploymentStrategy.CANARY:
            return {
                "canary": {
                    "increments": [25, 50, 100],
                    "deploy": {
                        "steps": base_steps
                    },
                    "promote": {
                        "steps": [
                            {
                                "script": """
                                    echo "Promoting canary deployment..."
                                    # Add promotion logic here
                                    """,
                                "displayName": "Promote canary deployment"
                            }
                        ]
                    }
                }
            }
        else:
            return {
                "runOnce": {
                    "deploy": {
                        "steps": base_steps
                    }
                }
            }
    
    async def generate_docker_files(self) -> Dict[str, str]:
        """Generate Docker configuration files"""
        
        files = {}
        
        # Main Dockerfile
        files["Dockerfile"] = """
# Multi-stage build for production optimization
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    build-essential \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \\
    curl \\
    && rm -rf /var/lib/apt/lists/* \\
    && apt-get clean

# Copy Python packages from builder stage
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY . .

# Set ownership and permissions
RUN chown -R appuser:appuser /app
USER appuser

# Add local packages to PATH
ENV PATH=/home/appuser/.local/bin:$PATH

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PERFORMANCE_OPTIMIZATION_LEVEL=aggressive
ENV CACHE_ENABLED=true
ENV REDIS_ENABLED=true

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
"""
        
        # Docker Compose for local development
        files["docker-compose.yml"] = """
version: '3.8'

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=development
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=mongodb://mongodb:27017/screenshot_to_code
    depends_on:
      - redis
      - mongodb
    volumes:
      - .:/app
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
  
  mongodb:
    image: mongo:7
    ports:
      - "27017:27017"
    environment:
      - MONGO_INITDB_ROOT_USERNAME=admin
      - MONGO_INITDB_ROOT_PASSWORD=password
    volumes:
      - mongodb_data:/data/db

volumes:
  redis_data:
  mongodb_data:
"""
        
        # Docker Compose for production
        files["docker-compose.prod.yml"] = """
version: '3.8'

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        BUILD_ENV: production
    ports:
      - "80:8000"
      - "443:8000"
    environment:
      - ENVIRONMENT=production
      - PERFORMANCE_OPTIMIZATION_LEVEL=aggressive
      - CACHE_ENABLED=true
      - REDIS_ENABLED=true
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
"""
        
        # .dockerignore
        files[".dockerignore"] = """
# Git
.git
.gitignore

# Documentation
README.md
docs/
*.md

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/
.cache
nosetests.xml
coverage.xml
*.cover
.hypothesis/

# Environment
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Logs
logs/
*.log

# Temporary files
tmp/
temp/

# Node modules (if any)
node_modules/
npm-debug.log*

# Docker
.dockerignore
Dockerfile*
docker-compose*
"""
        
        return files
    
    async def generate_kubernetes_manifests(self) -> Dict[str, str]:
        """Generate Kubernetes deployment manifests"""
        
        manifests = {}
        
        # Deployment manifest
        manifests["deployment.yaml"] = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: screenshot-to-code-api
  labels:
    app: screenshot-to-code-api
    tier: backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: screenshot-to-code-api
  template:
    metadata:
      labels:
        app: screenshot-to-code-api
        tier: backend
    spec:
      containers:
      - name: api
        image: screenshottocode.azurecr.io/api-gateway:latest
        ports:
        - containerPort: 8000
        env:
        - name: ENVIRONMENT
          value: "production"
        - name: PERFORMANCE_OPTIMIZATION_LEVEL
          value: "aggressive"
        - name: CACHE_ENABLED
          value: "true"
        - name: REDIS_ENABLED
          value: "true"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        volumeMounts:
        - name: config
          mountPath: /app/config
          readOnly: true
      volumes:
      - name: config
        configMap:
          name: screenshot-to-code-config
---
apiVersion: v1
kind: Service
metadata:
  name: screenshot-to-code-api-service
  labels:
    app: screenshot-to-code-api
spec:
  selector:
    app: screenshot-to-code-api
  ports:
  - port: 80
    targetPort: 8000
    protocol: TCP
  type: ClusterIP
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: screenshot-to-code-api-ingress
  annotations:
    kubernetes.io/ingress.class: azure/application-gateway
    appgw.ingress.kubernetes.io/ssl-redirect: "true"
    appgw.ingress.kubernetes.io/health-probe-path: "/health"
spec:
  tls:
  - hosts:
    - api.screenshot-to-code.com
    secretName: tls-secret
  rules:
  - host: api.screenshot-to-code.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: screenshot-to-code-api-service
            port:
              number: 80
"""
        
        # ConfigMap
        manifests["configmap.yaml"] = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: screenshot-to-code-config
data:
  config.yaml: |
    app:
      name: "Screenshot-to-Code API"
      version: "1.0.0"
      environment: "production"
    
    performance:
      optimization_level: "aggressive"
      cache_enabled: true
      redis_enabled: true
      monitoring_enabled: true
    
    logging:
      level: "INFO"
      format: "json"
      correlation_id_enabled: true
    
    security:
      cors_enabled: true
      rate_limiting_enabled: true
      security_headers_enabled: true
"""
        
        # HorizontalPodAutoscaler
        manifests["hpa.yaml"] = """
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: screenshot-to-code-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: screenshot-to-code-api
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
"""
        
        return manifests
    
    async def generate_deployment_scripts(self) -> Dict[str, str]:
        """Generate deployment automation scripts"""
        
        scripts = {}
        
        # Main deployment script
        scripts["deploy.sh"] = """#!/bin/bash
set -e

# Screenshot-to-Code Deployment Script
# Usage: ./deploy.sh [environment] [version]

ENVIRONMENT=${1:-staging}
VERSION=${2:-latest}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validate environment
validate_environment() {
    case $ENVIRONMENT in
        development|testing|staging|production)
            log_info "Deploying to $ENVIRONMENT environment"
            ;;
        *)
            log_error "Invalid environment: $ENVIRONMENT"
            log_error "Valid environments: development, testing, staging, production"
            exit 1
            ;;
    esac
}

# Pre-deployment checks
pre_deployment_checks() {
    log_info "Running pre-deployment checks..."
    
    # Check if required tools are installed
    command -v az >/dev/null 2>&1 || { log_error "Azure CLI is not installed"; exit 1; }
    command -v docker >/dev/null 2>&1 || { log_error "Docker is not installed"; exit 1; }
    
    # Check Azure authentication
    if ! az account show >/dev/null 2>&1; then
        log_error "Not authenticated with Azure CLI"
        log_info "Please run: az login"
        exit 1
    fi
    
    # Check environment configuration
    if [ ! -f "$PROJECT_ROOT/config/$ENVIRONMENT.json" ]; then
        log_error "Environment configuration not found: config/$ENVIRONMENT.json"
        exit 1
    fi
    
    log_info "Pre-deployment checks passed"
}

# Build application
build_application() {
    log_info "Building application..."
    
    cd "$PROJECT_ROOT"
    
    # Build Docker image
    IMAGE_TAG="screenshottocode.azurecr.io/api-gateway:$ENVIRONMENT-$VERSION"
    docker build -t "$IMAGE_TAG" .
    
    # Push to registry
    docker push "$IMAGE_TAG"
    
    log_info "Application built and pushed: $IMAGE_TAG"
}

# Deploy infrastructure
deploy_infrastructure() {
    log_info "Deploying infrastructure..."
    
    RESOURCE_GROUP="sktc-$ENVIRONMENT-rg"
    TEMPLATE_FILE="$PROJECT_ROOT/infrastructure/azure-resources.json"
    PARAMETERS_FILE="$PROJECT_ROOT/infrastructure/parameters/$ENVIRONMENT.json"
    
    # Create resource group if it doesn't exist
    if ! az group show --name "$RESOURCE_GROUP" >/dev/null 2>&1; then
        log_info "Creating resource group: $RESOURCE_GROUP"
        az group create --name "$RESOURCE_GROUP" --location "East US"
    fi
    
    # Deploy ARM template
    DEPLOYMENT_NAME="deployment-$(date +%Y%m%d-%H%M%S)"
    az deployment group create \\
        --resource-group "$RESOURCE_GROUP" \\
        --template-file "$TEMPLATE_FILE" \\
        --parameters "@$PARAMETERS_FILE" \\
        --name "$DEPLOYMENT_NAME"
    
    log_info "Infrastructure deployment completed"
}

# Deploy application
deploy_application() {
    log_info "Deploying application..."
    
    APP_NAME="sktc-$ENVIRONMENT-api"
    IMAGE_TAG="screenshottocode.azurecr.io/api-gateway:$ENVIRONMENT-$VERSION"
    
    # Deploy to App Service
    az webapp config container set \\
        --name "$APP_NAME" \\
        --resource-group "sktc-$ENVIRONMENT-rg" \\
        --docker-custom-image-name "$IMAGE_TAG"
    
    # Restart the app service
    az webapp restart \\
        --name "$APP_NAME" \\
        --resource-group "sktc-$ENVIRONMENT-rg"
    
    log_info "Application deployment completed"
}

# Post-deployment validation
post_deployment_validation() {
    log_info "Running post-deployment validation..."
    
    APP_URL="https://sktc-$ENVIRONMENT-api.azurewebsites.net"
    
    # Wait for application to start
    log_info "Waiting for application to start..."
    sleep 30
    
    # Health check
    if curl -sf "$APP_URL/health" >/dev/null; then
        log_info "Health check passed"
    else
        log_error "Health check failed"
        exit 1
    fi
    
    # Run smoke tests
    if [ -f "$PROJECT_ROOT/tests/smoke_test.sh" ]; then
        log_info "Running smoke tests..."
        bash "$PROJECT_ROOT/tests/smoke_test.sh" "$APP_URL"
    fi
    
    log_info "Post-deployment validation completed"
}

# Cleanup old deployments
cleanup_old_deployments() {
    log_info "Cleaning up old deployments..."
    
    # Keep only the last 5 container images
    az acr repository show-tags \\
        --name screenshottocode \\
        --repository api-gateway \\
        --query "[?contains(name, '$ENVIRONMENT')].name" \\
        --output tsv | \\
    sort -rV | \\
    tail -n +6 | \\
    xargs -I {} az acr repository delete \\
        --name screenshottocode \\
        --image api-gateway:{} \\
        --yes
    
    log_info "Cleanup completed"
}

# Main deployment flow
main() {
    log_info "Starting deployment process..."
    log_info "Environment: $ENVIRONMENT"
    log_info "Version: $VERSION"
    
    validate_environment
    pre_deployment_checks
    build_application
    deploy_infrastructure
    deploy_application
    post_deployment_validation
    cleanup_old_deployments
    
    log_info "Deployment completed successfully!"
    log_info "Application URL: https://sktc-$ENVIRONMENT-api.azurewebsites.net"
}

# Handle script interruption
trap 'log_error "Deployment interrupted"; exit 1' INT TERM

# Run main function
main "$@"
"""
        
        # Rollback script
        scripts["rollback.sh"] = """#!/bin/bash
set -e

# Screenshot-to-Code Rollback Script
# Usage: ./rollback.sh [environment] [target_version]

ENVIRONMENT=${1:-staging}
TARGET_VERSION=${2}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validate inputs
validate_inputs() {
    case $ENVIRONMENT in
        development|testing|staging|production)
            log_info "Rolling back $ENVIRONMENT environment"
            ;;
        *)
            log_error "Invalid environment: $ENVIRONMENT"
            exit 1
            ;;
    esac
    
    if [ -z "$TARGET_VERSION" ]; then
        log_error "Target version not specified"
        log_info "Usage: ./rollback.sh [environment] [target_version]"
        exit 1
    fi
}

# Get current deployment
get_current_deployment() {
    APP_NAME="sktc-$ENVIRONMENT-api"
    RESOURCE_GROUP="sktc-$ENVIRONMENT-rg"
    
    CURRENT_IMAGE=$(az webapp config show \\
        --name "$APP_NAME" \\
        --resource-group "$RESOURCE_GROUP" \\
        --query "linuxFxVersion" \\
        --output tsv | cut -d'|' -f2)
    
    log_info "Current deployment: $CURRENT_IMAGE"
}

# Perform rollback
perform_rollback() {
    log_info "Rolling back to version: $TARGET_VERSION"
    
    APP_NAME="sktc-$ENVIRONMENT-api"
    RESOURCE_GROUP="sktc-$ENVIRONMENT-rg"
    TARGET_IMAGE="screenshottocode.azurecr.io/api-gateway:$ENVIRONMENT-$TARGET_VERSION"
    
    # Update container image
    az webapp config container set \\
        --name "$APP_NAME" \\
        --resource-group "$RESOURCE_GROUP" \\
        --docker-custom-image-name "$TARGET_IMAGE"
    
    # Restart the app service
    az webapp restart \\
        --name "$APP_NAME" \\
        --resource-group "$RESOURCE_GROUP"
    
    log_info "Rollback initiated"
}

# Validate rollback
validate_rollback() {
    log_info "Validating rollback..."
    
    APP_URL="https://sktc-$ENVIRONMENT-api.azurewebsites.net"
    
    # Wait for application to start
    sleep 30
    
    # Health check
    for i in {1..10}; do
        if curl -sf "$APP_URL/health" >/dev/null; then
            log_info "Rollback validation successful"
            return 0
        fi
        log_warn "Health check failed, attempt $i/10"
        sleep 30
    done
    
    log_error "Rollback validation failed"
    exit 1
}

# Main rollback flow
main() {
    log_info "Starting rollback process..."
    
    validate_inputs
    get_current_deployment
    perform_rollback
    validate_rollback
    
    log_info "Rollback completed successfully!"
    log_info "Application URL: https://sktc-$ENVIRONMENT-api.azurewebsites.net"
}

# Handle script interruption
trap 'log_error "Rollback interrupted"; exit 1' INT TERM

# Run main function
main "$@"
"""
        
        return scripts
    
    def get_deployment_summary(self) -> Dict[str, Any]:
        """Get deployment automation summary"""
        
        return {
            "environments": list(self.deployment_configs.keys()),
            "strategies": {
                env: config.strategy.value 
                for env, config in self.deployment_configs.items()
            },
            "build_configuration": {
                "tool": self.build_config.build_tool,
                "registry": self.build_config.image_registry,
                "cache_enabled": self.build_config.cache_enabled,
                "multi_stage": self.build_config.multi_stage_build
            },
            "test_configuration": {
                "unit_tests": self.test_config.unit_tests_enabled,
                "integration_tests": self.test_config.integration_tests_enabled,
                "e2e_tests": self.test_config.e2e_tests_enabled,
                "security_tests": self.test_config.security_tests_enabled,
                "coverage_threshold": self.test_config.test_coverage_threshold
            },
            "pipeline_features": [
                "Automated build and test",
                "Multi-environment deployment",
                "Blue-green deployment for production",
                "Automatic rollback on failure",
                "Security scanning",
                "Container orchestration",
                "Infrastructure as Code"
            ]
        }