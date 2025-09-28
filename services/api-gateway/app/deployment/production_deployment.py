"""
Production Deployment Manager
Comprehensive production deployment orchestration and validation
"""
import asyncio
import json
import time
import subprocess
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


class DeploymentPhase(Enum):
    """Deployment phase stages"""
    PRE_DEPLOYMENT = "pre_deployment"
    INFRASTRUCTURE = "infrastructure"
    APPLICATION = "application"
    VALIDATION = "validation"
    GO_LIVE = "go_live"
    POST_DEPLOYMENT = "post_deployment"


class ValidationStatus(Enum):
    """Validation status types"""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"


class HealthCheckType(Enum):
    """Health check types"""
    BASIC = "basic"
    COMPREHENSIVE = "comprehensive"
    PERFORMANCE = "performance"
    SECURITY = "security"
    FUNCTIONAL = "functional"


@dataclass
class DeploymentStep:
    """Individual deployment step configuration"""
    name: str
    phase: DeploymentPhase
    description: str
    command: Optional[str] = None
    validation_command: Optional[str] = None
    timeout: int = 300  # seconds
    retry_count: int = 3
    required: bool = True
    dependencies: List[str] = field(default_factory=list)
    
    # Execution state
    status: ValidationStatus = ValidationStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    execution_time: Optional[float] = None
    error_message: Optional[str] = None
    retry_attempts: int = 0


@dataclass
class HealthCheck:
    """Health check configuration"""
    name: str
    type: HealthCheckType
    endpoint: str
    expected_status: int = 200
    expected_response: Optional[str] = None
    timeout: int = 30
    retry_count: int = 3
    critical: bool = True
    
    # Execution state
    status: ValidationStatus = ValidationStatus.PENDING
    response_time: Optional[float] = None
    actual_status: Optional[int] = None
    actual_response: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class PerformanceMetric:
    """Performance validation metric"""
    name: str
    metric_type: str  # response_time, throughput, cpu, memory
    endpoint: Optional[str] = None
    expected_threshold: float = 0.0
    critical_threshold: float = 0.0
    unit: str = "ms"
    
    # Measurement results
    current_value: Optional[float] = None
    status: ValidationStatus = ValidationStatus.PENDING
    measurements: List[float] = field(default_factory=list)


class ProductionDeploymentManager:
    """Comprehensive production deployment orchestrator"""
    
    def __init__(self, 
                 environment: str = "production",
                 resource_group: str = None,
                 subscription_id: str = None,
                 logger: Optional[StructuredLogger] = None):
        
        self.environment = environment
        self.resource_group = resource_group or f"sktc-{environment}-rg"
        self.subscription_id = subscription_id
        self.logger = logger or StructuredLogger()
        
        # Deployment configuration
        self.deployment_steps: List[DeploymentStep] = []
        self.health_checks: List[HealthCheck] = []
        self.performance_metrics: List[PerformanceMetric] = []
        
        # Deployment state
        self.deployment_id = f"deploy-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        self.deployment_start_time: Optional[datetime] = None
        self.deployment_end_time: Optional[datetime] = None
        self.current_phase: Optional[DeploymentPhase] = None
        self.deployment_status = ValidationStatus.PENDING
        
        # Configuration
        self.app_service_name = f"sktc-{environment}-api"
        self.app_service_url = f"https://{self.app_service_name}.azurewebsites.net"
        self.staging_slot_url = f"https://{self.app_service_name}-staging.azurewebsites.net"
        
        # Initialize default configuration
        self._initialize_deployment_steps()
        self._initialize_health_checks()
        self._initialize_performance_metrics()
    
    def _initialize_deployment_steps(self):
        """Initialize default deployment steps"""
        
        # Pre-deployment phase
        self.deployment_steps.extend([
            DeploymentStep(
                name="validate_prerequisites",
                phase=DeploymentPhase.PRE_DEPLOYMENT,
                description="Validate deployment prerequisites and environment readiness",
                validation_command="az account show && az group exists --name {resource_group}",
                timeout=60
            ),
            DeploymentStep(
                name="backup_current_production",
                phase=DeploymentPhase.PRE_DEPLOYMENT,
                description="Create backup of current production environment",
                command="az webapp deployment slot create --name {app_service} --resource-group {resource_group} --slot backup-{timestamp}",
                timeout=300
            ),
            DeploymentStep(
                name="validate_infrastructure",
                phase=DeploymentPhase.PRE_DEPLOYMENT,
                description="Validate infrastructure template and configuration",
                validation_command="az deployment group validate --resource-group {resource_group} --template-file infrastructure.json",
                timeout=120
            )
        ])
        
        # Infrastructure phase
        self.deployment_steps.extend([
            DeploymentStep(
                name="deploy_infrastructure",
                phase=DeploymentPhase.INFRASTRUCTURE,
                description="Deploy infrastructure using ARM template",
                command="az deployment group create --resource-group {resource_group} --template-file infrastructure.json --parameters @parameters.json",
                timeout=1800,  # 30 minutes
                dependencies=["validate_infrastructure"]
            ),
            DeploymentStep(
                name="configure_networking",
                phase=DeploymentPhase.INFRASTRUCTURE,
                description="Configure network security groups and firewall rules",
                command="az network nsg rule create --resource-group {resource_group} --nsg-name web-tier-nsg --name AllowHTTPS --priority 100",
                timeout=300,
                dependencies=["deploy_infrastructure"]
            ),
            DeploymentStep(
                name="setup_monitoring",
                phase=DeploymentPhase.INFRASTRUCTURE,
                description="Configure Application Insights and monitoring",
                command="az monitor app-insights component create --app {app_service}-insights --location eastus --resource-group {resource_group}",
                timeout=300,
                dependencies=["deploy_infrastructure"]
            )
        ])
        
        # Application phase
        self.deployment_steps.extend([
            DeploymentStep(
                name="build_application",
                phase=DeploymentPhase.APPLICATION,
                description="Build application with production configuration",
                command="docker build -t screenshottocode.azurecr.io/api-gateway:production-{build_id} .",
                timeout=600,
                dependencies=["deploy_infrastructure"]
            ),
            DeploymentStep(
                name="push_container_image",
                phase=DeploymentPhase.APPLICATION,
                description="Push container image to Azure Container Registry",
                command="docker push screenshottocode.azurecr.io/api-gateway:production-{build_id}",
                timeout=600,
                dependencies=["build_application"]
            ),
            DeploymentStep(
                name="deploy_to_staging_slot",
                phase=DeploymentPhase.APPLICATION,
                description="Deploy application to staging slot",
                command="az webapp config container set --name {app_service} --resource-group {resource_group} --slot staging --docker-custom-image-name screenshottocode.azurecr.io/api-gateway:production-{build_id}",
                timeout=600,
                dependencies=["push_container_image"]
            ),
            DeploymentStep(
                name="warm_up_staging",
                phase=DeploymentPhase.APPLICATION,
                description="Warm up staging slot and validate deployment",
                command="curl -f {staging_url}/health && sleep 60",
                timeout=120,
                dependencies=["deploy_to_staging_slot"]
            )
        ])
        
        # Validation phase
        self.deployment_steps.extend([
            DeploymentStep(
                name="run_smoke_tests",
                phase=DeploymentPhase.VALIDATION,
                description="Execute smoke tests against staging environment",
                command="python -m pytest tests/smoke --base-url {staging_url} --junitxml=smoke-results.xml",
                timeout=600,
                dependencies=["warm_up_staging"]
            ),
            DeploymentStep(
                name="run_integration_tests",
                phase=DeploymentPhase.VALIDATION,
                description="Execute integration tests",
                command="python -m pytest tests/integration --base-url {staging_url} --junitxml=integration-results.xml",
                timeout=900,
                dependencies=["run_smoke_tests"]
            ),
            DeploymentStep(
                name="performance_validation",
                phase=DeploymentPhase.VALIDATION,
                description="Validate performance requirements",
                command="python scripts/performance_test.py --base-url {staging_url} --duration 300",
                timeout=600,
                dependencies=["run_integration_tests"]
            ),
            DeploymentStep(
                name="security_validation",
                phase=DeploymentPhase.VALIDATION,
                description="Execute security validation tests",
                command="python scripts/security_scan.py --base-url {staging_url}",
                timeout=600,
                dependencies=["performance_validation"]
            )
        ])
        
        # Go-live phase
        self.deployment_steps.extend([
            DeploymentStep(
                name="swap_to_production",
                phase=DeploymentPhase.GO_LIVE,
                description="Swap staging slot to production",
                command="az webapp deployment slot swap --name {app_service} --resource-group {resource_group} --slot staging --target-slot production",
                timeout=300,
                dependencies=["security_validation"]
            ),
            DeploymentStep(
                name="validate_production_health",
                phase=DeploymentPhase.GO_LIVE,
                description="Validate production environment health",
                validation_command="curl -f {production_url}/health",
                timeout=120,
                dependencies=["swap_to_production"]
            ),
            DeploymentStep(
                name="update_dns_records",
                phase=DeploymentPhase.GO_LIVE,
                description="Update DNS records and CDN configuration",
                command="az network dns record-set cname set-record --resource-group {dns_resource_group} --zone-name screenshot-to-code.com --record-set-name api --cname {app_service}.azurewebsites.net",
                timeout=300,
                required=False,
                dependencies=["validate_production_health"]
            )
        ])
        
        # Post-deployment phase
        self.deployment_steps.extend([
            DeploymentStep(
                name="cleanup_old_deployments",
                phase=DeploymentPhase.POST_DEPLOYMENT,
                description="Clean up old container images and deployment artifacts",
                command="az acr repository show-tags --name screenshottocode --repository api-gateway --query '[?contains(name, \"production\")].name' --output tsv | sort -rV | tail -n +6",
                timeout=300,
                required=False,
                dependencies=["validate_production_health"]
            ),
            DeploymentStep(
                name="send_deployment_notification",
                phase=DeploymentPhase.POST_DEPLOYMENT,
                description="Send deployment completion notification",
                command="python scripts/send_notification.py --deployment-id {deployment_id} --status success",
                timeout=60,
                required=False,
                dependencies=["validate_production_health"]
            ),
            DeploymentStep(
                name="update_documentation",
                phase=DeploymentPhase.POST_DEPLOYMENT,
                description="Update deployment documentation and runbooks",
                command="python scripts/update_docs.py --deployment-id {deployment_id} --version production-{build_id}",
                timeout=120,
                required=False,
                dependencies=["validate_production_health"]
            )
        ])
    
    def _initialize_health_checks(self):
        """Initialize health check configurations"""
        
        # Basic health checks
        self.health_checks.extend([
            HealthCheck(
                name="application_health",
                type=HealthCheckType.BASIC,
                endpoint="/health",
                expected_status=200,
                expected_response="healthy",
                timeout=30,
                critical=True
            ),
            HealthCheck(
                name="application_ready",
                type=HealthCheckType.BASIC,
                endpoint="/ready",
                expected_status=200,
                timeout=30,
                critical=True
            ),
            HealthCheck(
                name="api_documentation",
                type=HealthCheckType.BASIC,
                endpoint="/docs",
                expected_status=200,
                timeout=30,
                critical=False
            )
        ])
        
        # Comprehensive health checks
        self.health_checks.extend([
            HealthCheck(
                name="database_connectivity",
                type=HealthCheckType.COMPREHENSIVE,
                endpoint="/health/database",
                expected_status=200,
                timeout=60,
                critical=True
            ),
            HealthCheck(
                name="cache_connectivity",
                type=HealthCheckType.COMPREHENSIVE,
                endpoint="/health/cache",
                expected_status=200,
                timeout=30,
                critical=True
            ),
            HealthCheck(
                name="external_apis",
                type=HealthCheckType.COMPREHENSIVE,
                endpoint="/health/external",
                expected_status=200,
                timeout=60,
                critical=False
            ),
            HealthCheck(
                name="storage_connectivity",
                type=HealthCheckType.COMPREHENSIVE,
                endpoint="/health/storage",
                expected_status=200,
                timeout=30,
                critical=True
            )
        ])
        
        # Performance health checks
        self.health_checks.extend([
            HealthCheck(
                name="response_time_check",
                type=HealthCheckType.PERFORMANCE,
                endpoint="/api/generate-code",
                expected_status=200,
                timeout=5000,  # 5 seconds
                critical=True
            ),
            HealthCheck(
                name="concurrent_requests",
                type=HealthCheckType.PERFORMANCE,
                endpoint="/health",
                expected_status=200,
                timeout=30,
                critical=False
            )
        ])
        
        # Security health checks
        self.health_checks.extend([
            HealthCheck(
                name="https_redirect",
                type=HealthCheckType.SECURITY,
                endpoint="http://{domain}/health",  # HTTP should redirect to HTTPS
                expected_status=301,
                timeout=30,
                critical=True
            ),
            HealthCheck(
                name="security_headers",
                type=HealthCheckType.SECURITY,
                endpoint="/health",
                expected_status=200,
                timeout=30,
                critical=True
            )
        ])
        
        # Functional health checks
        self.health_checks.extend([
            HealthCheck(
                name="code_generation_api",
                type=HealthCheckType.FUNCTIONAL,
                endpoint="/api/generate-code",
                expected_status=200,
                timeout=10000,  # 10 seconds
                critical=True
            ),
            HealthCheck(
                name="user_management_api",
                type=HealthCheckType.FUNCTIONAL,
                endpoint="/api/users/me",
                expected_status=401,  # Should require authentication
                timeout=30,
                critical=True
            )
        ])
    
    def _initialize_performance_metrics(self):
        """Initialize performance validation metrics"""
        
        # Response time metrics
        self.performance_metrics.extend([
            PerformanceMetric(
                name="api_response_time",
                metric_type="response_time",
                endpoint="/api/generate-code",
                expected_threshold=5000.0,  # 5 seconds
                critical_threshold=10000.0,  # 10 seconds
                unit="ms"
            ),
            PerformanceMetric(
                name="health_check_response_time",
                metric_type="response_time",
                endpoint="/health",
                expected_threshold=100.0,  # 100ms
                critical_threshold=1000.0,  # 1 second
                unit="ms"
            ),
            PerformanceMetric(
                name="static_content_response_time",
                metric_type="response_time",
                endpoint="/docs",
                expected_threshold=500.0,  # 500ms
                critical_threshold=2000.0,  # 2 seconds
                unit="ms"
            )
        ])
        
        # Throughput metrics
        self.performance_metrics.extend([
            PerformanceMetric(
                name="requests_per_second",
                metric_type="throughput",
                endpoint="/health",
                expected_threshold=100.0,  # 100 RPS
                critical_threshold=50.0,   # 50 RPS minimum
                unit="rps"
            ),
            PerformanceMetric(
                name="concurrent_users",
                metric_type="throughput",
                endpoint="/api/generate-code",
                expected_threshold=50.0,   # 50 concurrent users
                critical_threshold=25.0,  # 25 concurrent minimum
                unit="users"
            )
        ])
        
        # Resource utilization metrics
        self.performance_metrics.extend([
            PerformanceMetric(
                name="cpu_utilization",
                metric_type="cpu",
                expected_threshold=70.0,   # 70% CPU
                critical_threshold=90.0,  # 90% CPU critical
                unit="%"
            ),
            PerformanceMetric(
                name="memory_utilization",
                metric_type="memory",
                expected_threshold=80.0,   # 80% memory
                critical_threshold=95.0,  # 95% memory critical
                unit="%"
            ),
            PerformanceMetric(
                name="database_response_time",
                metric_type="response_time",
                endpoint="/health/database",
                expected_threshold=100.0,  # 100ms
                critical_threshold=1000.0, # 1 second
                unit="ms"
            ),
            PerformanceMetric(
                name="cache_hit_rate",
                metric_type="cache",
                expected_threshold=80.0,   # 80% hit rate
                critical_threshold=50.0,  # 50% minimum
                unit="%"
            )
        ])
    
    async def execute_deployment(self) -> Dict[str, Any]:
        """Execute complete production deployment"""
        
        self.deployment_start_time = datetime.utcnow()
        self.deployment_status = ValidationStatus.RUNNING
        correlation_id = get_correlation_id()
        
        self.logger.info(
            "Starting production deployment",
            deployment_id=self.deployment_id,
            environment=self.environment,
            correlation_id=correlation_id
        )
        
        deployment_results = {
            "deployment_id": self.deployment_id,
            "environment": self.environment,
            "start_time": self.deployment_start_time.isoformat(),
            "phases": {},
            "overall_status": ValidationStatus.RUNNING.value,
            "correlation_id": correlation_id
        }
        
        try:
            # Execute deployment phases
            for phase in DeploymentPhase:
                self.current_phase = phase
                phase_result = await self._execute_phase(phase)
                deployment_results["phases"][phase.value] = phase_result
                
                # Stop deployment if critical phase fails
                if phase_result["status"] == ValidationStatus.FAILED.value and phase in [
                    DeploymentPhase.INFRASTRUCTURE, 
                    DeploymentPhase.APPLICATION,
                    DeploymentPhase.VALIDATION
                ]:
                    self.deployment_status = ValidationStatus.FAILED
                    break
            
            # Final status determination
            if self.deployment_status == ValidationStatus.RUNNING:
                failed_critical_steps = [
                    step for step in self.deployment_steps 
                    if step.status == ValidationStatus.FAILED and step.required
                ]
                
                if failed_critical_steps:
                    self.deployment_status = ValidationStatus.FAILED
                else:
                    self.deployment_status = ValidationStatus.PASSED
            
            self.deployment_end_time = datetime.utcnow()
            deployment_time = (self.deployment_end_time - self.deployment_start_time).total_seconds()
            
            deployment_results.update({
                "end_time": self.deployment_end_time.isoformat(),
                "deployment_time_seconds": deployment_time,
                "overall_status": self.deployment_status.value,
                "summary": self._generate_deployment_summary()
            })
            
            self.logger.info(
                "Production deployment completed",
                deployment_id=self.deployment_id,
                status=self.deployment_status.value,
                deployment_time=deployment_time,
                correlation_id=correlation_id
            )
            
        except Exception as e:
            self.deployment_status = ValidationStatus.FAILED
            self.deployment_end_time = datetime.utcnow()
            
            deployment_results.update({
                "end_time": self.deployment_end_time.isoformat(),
                "overall_status": ValidationStatus.FAILED.value,
                "error": str(e),
                "summary": self._generate_deployment_summary()
            })
            
            self.logger.error(
                "Production deployment failed",
                deployment_id=self.deployment_id,
                error=str(e),
                correlation_id=correlation_id
            )
        
        return deployment_results
    
    async def _execute_phase(self, phase: DeploymentPhase) -> Dict[str, Any]:
        """Execute specific deployment phase"""
        
        phase_steps = [step for step in self.deployment_steps if step.phase == phase]
        phase_start_time = datetime.utcnow()
        
        self.logger.info(
            f"Starting deployment phase: {phase.value}",
            phase=phase.value,
            step_count=len(phase_steps),
            deployment_id=self.deployment_id
        )
        
        phase_result = {
            "phase": phase.value,
            "start_time": phase_start_time.isoformat(),
            "steps": {},
            "status": ValidationStatus.RUNNING.value
        }
        
        # Execute steps in dependency order
        executed_steps = set()
        
        while len(executed_steps) < len(phase_steps):
            ready_steps = [
                step for step in phase_steps
                if step.name not in executed_steps and
                all(dep in executed_steps for dep in step.dependencies)
            ]
            
            if not ready_steps:
                # Check for circular dependencies or missing dependencies
                remaining_steps = [step for step in phase_steps if step.name not in executed_steps]
                self.logger.error(
                    "Deployment phase has unresolvable dependencies",
                    phase=phase.value,
                    remaining_steps=[s.name for s in remaining_steps]
                )
                break
            
            # Execute ready steps
            for step in ready_steps:
                step_result = await self._execute_step(step)
                phase_result["steps"][step.name] = step_result
                executed_steps.add(step.name)
                
                # Stop phase if critical step fails
                if step.status == ValidationStatus.FAILED and step.required:
                    phase_result["status"] = ValidationStatus.FAILED.value
                    break
        
        # Determine phase status
        if phase_result["status"] == ValidationStatus.RUNNING.value:
            failed_required_steps = [
                step for step in phase_steps
                if step.status == ValidationStatus.FAILED and step.required
            ]
            
            if failed_required_steps:
                phase_result["status"] = ValidationStatus.FAILED.value
            else:
                phase_result["status"] = ValidationStatus.PASSED.value
        
        phase_end_time = datetime.utcnow()
        phase_duration = (phase_end_time - phase_start_time).total_seconds()
        
        phase_result.update({
            "end_time": phase_end_time.isoformat(),
            "duration_seconds": phase_duration
        })
        
        self.logger.info(
            f"Deployment phase completed: {phase.value}",
            phase=phase.value,
            status=phase_result["status"],
            duration=phase_duration,
            deployment_id=self.deployment_id
        )
        
        return phase_result
    
    async def _execute_step(self, step: DeploymentStep) -> Dict[str, Any]:
        """Execute individual deployment step"""
        
        step.start_time = datetime.utcnow()
        step.status = ValidationStatus.RUNNING
        
        self.logger.info(
            f"Executing deployment step: {step.name}",
            step=step.name,
            phase=step.phase.value,
            deployment_id=self.deployment_id
        )
        
        step_result = {
            "name": step.name,
            "description": step.description,
            "start_time": step.start_time.isoformat(),
            "status": ValidationStatus.RUNNING.value
        }
        
        # Execute step with retries
        for attempt in range(step.retry_count + 1):
            try:
                if step.command:
                    # Format command with current context
                    formatted_command = self._format_command(step.command)
                    
                    # Execute command
                    process = await asyncio.create_subprocess_shell(
                        formatted_command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    try:
                        stdout, stderr = await asyncio.wait_for(
                            process.communicate(),
                            timeout=step.timeout
                        )
                        
                        if process.returncode == 0:
                            step.status = ValidationStatus.PASSED
                            step_result["stdout"] = stdout.decode('utf-8')
                        else:
                            raise RuntimeError(f"Command failed: {stderr.decode('utf-8')}")
                            
                    except asyncio.TimeoutError:
                        process.kill()
                        raise RuntimeError(f"Command timed out after {step.timeout} seconds")
                
                elif step.validation_command:
                    # Execute validation command
                    formatted_command = self._format_command(step.validation_command)
                    
                    process = await asyncio.create_subprocess_shell(
                        formatted_command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    try:
                        stdout, stderr = await asyncio.wait_for(
                            process.communicate(),
                            timeout=step.timeout
                        )
                        
                        if process.returncode == 0:
                            step.status = ValidationStatus.PASSED
                            step_result["validation_output"] = stdout.decode('utf-8')
                        else:
                            raise RuntimeError(f"Validation failed: {stderr.decode('utf-8')}")
                            
                    except asyncio.TimeoutError:
                        process.kill()
                        raise RuntimeError(f"Validation timed out after {step.timeout} seconds")
                
                else:
                    # Manual step - mark as passed
                    step.status = ValidationStatus.PASSED
                
                # Break retry loop on success
                break
                
            except Exception as e:
                step.retry_attempts = attempt + 1
                step.error_message = str(e)
                
                if attempt < step.retry_count:
                    self.logger.warning(
                        f"Step {step.name} failed, retrying",
                        step=step.name,
                        attempt=attempt + 1,
                        max_attempts=step.retry_count + 1,
                        error=str(e)
                    )
                    await asyncio.sleep(min(2 ** attempt, 30))  # Exponential backoff
                else:
                    step.status = ValidationStatus.FAILED
                    self.logger.error(
                        f"Step {step.name} failed after all retries",
                        step=step.name,
                        error=str(e),
                        retry_attempts=step.retry_attempts
                    )
        
        step.end_time = datetime.utcnow()
        step.execution_time = (step.end_time - step.start_time).total_seconds()
        
        step_result.update({
            "end_time": step.end_time.isoformat(),
            "execution_time_seconds": step.execution_time,
            "status": step.status.value,
            "retry_attempts": step.retry_attempts
        })
        
        if step.error_message:
            step_result["error"] = step.error_message
        
        return step_result
    
    def _format_command(self, command: str) -> str:
        """Format command with current deployment context"""
        
        build_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        
        format_vars = {
            "resource_group": self.resource_group,
            "app_service": self.app_service_name,
            "production_url": self.app_service_url,
            "staging_url": self.staging_slot_url,
            "build_id": build_id,
            "timestamp": timestamp,
            "deployment_id": self.deployment_id,
            "environment": self.environment,
            "subscription_id": self.subscription_id or "default",
            "dns_resource_group": f"{self.resource_group}-dns",
            "domain": "screenshot-to-code.com"
        }
        
        return command.format(**format_vars)
    
    def _generate_deployment_summary(self) -> Dict[str, Any]:
        """Generate comprehensive deployment summary"""
        
        total_steps = len(self.deployment_steps)
        passed_steps = len([s for s in self.deployment_steps if s.status == ValidationStatus.PASSED])
        failed_steps = len([s for s in self.deployment_steps if s.status == ValidationStatus.FAILED])
        required_failed_steps = len([s for s in self.deployment_steps if s.status == ValidationStatus.FAILED and s.required])
        
        summary = {
            "deployment_statistics": {
                "total_steps": total_steps,
                "passed_steps": passed_steps,
                "failed_steps": failed_steps,
                "required_failed_steps": required_failed_steps,
                "success_rate": (passed_steps / total_steps * 100) if total_steps > 0 else 0
            },
            "phase_summary": {},
            "critical_issues": [],
            "warnings": [],
            "recommendations": []
        }
        
        # Phase-level summary
        for phase in DeploymentPhase:
            phase_steps = [s for s in self.deployment_steps if s.phase == phase]
            if phase_steps:
                phase_passed = len([s for s in phase_steps if s.status == ValidationStatus.PASSED])
                phase_total = len(phase_steps)
                
                summary["phase_summary"][phase.value] = {
                    "total_steps": phase_total,
                    "passed_steps": phase_passed,
                    "success_rate": (phase_passed / phase_total * 100) if phase_total > 0 else 0
                }
        
        # Identify critical issues
        for step in self.deployment_steps:
            if step.status == ValidationStatus.FAILED and step.required:
                summary["critical_issues"].append({
                    "step": step.name,
                    "phase": step.phase.value,
                    "error": step.error_message,
                    "retry_attempts": step.retry_attempts
                })
        
        # Identify warnings
        for step in self.deployment_steps:
            if step.status == ValidationStatus.FAILED and not step.required:
                summary["warnings"].append({
                    "step": step.name,
                    "phase": step.phase.value,
                    "error": step.error_message
                })
        
        # Generate recommendations
        if summary["deployment_statistics"]["success_rate"] < 100:
            if required_failed_steps > 0:
                summary["recommendations"].append("Address critical deployment failures before proceeding")
            if failed_steps > required_failed_steps:
                summary["recommendations"].append("Review optional step failures for potential improvements")
        
        if self.deployment_status == ValidationStatus.PASSED:
            summary["recommendations"].append("Deployment successful - monitor production environment")
        
        return summary