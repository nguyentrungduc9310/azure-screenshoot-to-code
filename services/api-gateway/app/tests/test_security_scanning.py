"""
Security Scanning Integration Tests
Comprehensive tests for vulnerability scanner, CI/CD pipeline integration, and security scanning workflows
"""
import pytest
import asyncio
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from app.security.vulnerability_scanner import (
    AdvancedVulnerabilityScanner, ScanConfiguration, ScanType, 
    VulnerabilitySeverity, SecurityVulnerability, ScanResult
)
from app.cicd.security_pipeline import (
    SecurityPipelineIntegration, PipelineConfiguration, PipelineContext,
    DeploymentEnvironment, SecurityGate, PipelineStage, PipelineResult
)
from app.cicd.pipeline_configs import (
    PipelineConfigGenerator, PipelineConfig, PipelinePlatform, SecurityScanTool
)
from shared.monitoring.structured_logger import StructuredLogger


class TestAdvancedVulnerabilityScanner:
    """Test cases for advanced vulnerability scanner"""
    
    @pytest.fixture
    def logger(self):
        return Mock(spec=StructuredLogger)
    
    @pytest.fixture
    def scan_config(self):
        return ScanConfiguration(
            enabled_scan_types={ScanType.SAST, ScanType.SECRETS, ScanType.SCA},
            max_scan_duration_minutes=30,
            parallel_scans=True,
            fail_on_critical=True,
            fail_on_high=False
        )
    
    @pytest.fixture
    def scanner(self, logger, scan_config):
        return AdvancedVulnerabilityScanner(logger, scan_config)
    
    @pytest.fixture
    def temp_project(self):
        """Create temporary project with test files"""
        temp_dir = tempfile.mkdtemp()
        project_path = Path(temp_dir)
        
        # Create test Python file with vulnerabilities
        python_file = project_path / "test_app.py"
        python_file.write_text("""
import os
import subprocess

# Hardcoded secret (should be detected)
API_KEY = "sk-1234567890abcdef"
PASSWORD = "super_secret_password"

def vulnerable_function(user_input):
    # SQL injection vulnerability
    query = f"SELECT * FROM users WHERE name = '{user_input}'"
    
    # Command injection vulnerability
    subprocess.run(f"ls {user_input}", shell=True)
    
    # Weak cryptographic hash
    import hashlib
    return hashlib.md5(user_input.encode()).hexdigest()

def debug_enabled():
    # Debug mode should not be enabled in production
    debug = True
    return debug
""")
        
        # Create requirements.txt with vulnerable dependencies
        requirements_file = project_path / "requirements.txt"
        requirements_file.write_text("""
requests==2.19.0
flask==0.12.0
django==2.0.0
""")
        
        # Create Dockerfile with security issues
        dockerfile = project_path / "Dockerfile"
        dockerfile.write_text("""
FROM python:3.9
USER root
RUN apt-get update && apt-get install -y sudo
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
CMD ["python", "app.py"]
""")
        
        # Create docker-compose with privileged container
        compose_file = project_path / "docker-compose.yml"
        compose_file.write_text("""
version: '3.8'
services:
  app:
    build: .
    privileged: true
    volumes:
      - /:/host
""")
        
        yield project_path
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    def test_scanner_initialization(self, scanner, scan_config):
        """Test scanner initialization"""
        assert scanner.config == scan_config
        assert len(scanner.scan_engines) == 6
        assert ScanType.SAST in scanner.scan_engines
        assert ScanType.SECRETS in scanner.scan_engines
        assert len(scanner.vulnerability_patterns) > 0
    
    @pytest.mark.asyncio
    async def test_sast_scan(self, scanner, temp_project):
        """Test static application security testing"""
        vulnerabilities = await scanner._sast_scan(str(temp_project))
        
        assert len(vulnerabilities) > 0
        
        # Check for expected vulnerability types
        vulnerability_titles = [v.title for v in vulnerabilities]
        assert any("SQL Injection" in title for title in vulnerability_titles)
        assert any("Command Injection" in title for title in vulnerability_titles)
        assert any("Hardcoded Secret" in title for title in vulnerability_titles)
        assert any("Debug Mode" in title for title in vulnerability_titles)
        assert any("Weak Cryptographic Hash" in title for title in vulnerability_titles)
        
        # Verify vulnerability details
        sql_injection_vuln = next(
            (v for v in vulnerabilities if "SQL Injection" in v.title), None
        )
        assert sql_injection_vuln is not None
        assert sql_injection_vuln.severity == VulnerabilitySeverity.HIGH
        assert sql_injection_vuln.scan_type == ScanType.SAST
        assert sql_injection_vuln.file_path is not None
        assert sql_injection_vuln.line_number is not None
    
    @pytest.mark.asyncio
    async def test_secrets_scan(self, scanner, temp_project):
        """Test secrets detection scan"""
        vulnerabilities = await scanner._secrets_scan(str(temp_project))
        
        assert len(vulnerabilities) > 0
        
        # Check for expected secret types
        secret_types = [v.metadata.get("secret_type") for v in vulnerabilities if v.metadata.get("secret_type")]
        assert "generic_api_key" in secret_types or "password_field" in secret_types
        
        # Verify secret vulnerability details
        api_key_vuln = next(
            (v for v in vulnerabilities if v.metadata.get("secret_type") == "generic_api_key"), None
        )
        if api_key_vuln:
            assert api_key_vuln.severity == VulnerabilitySeverity.HIGH
            assert api_key_vuln.scan_type == ScanType.SECRETS
    
    @pytest.mark.asyncio
    async def test_sca_scan(self, scanner, temp_project):
        """Test software composition analysis"""
        vulnerabilities = await scanner._sca_scan(str(temp_project))
        
        # Should find vulnerable dependencies
        vulnerable_packages = [v.metadata.get("package") for v in vulnerabilities if v.metadata.get("package")]
        expected_packages = ["requests", "flask"]
        
        # At least one vulnerable package should be detected
        assert any(pkg in vulnerable_packages for pkg in expected_packages)
        
        if vulnerabilities:
            vuln = vulnerabilities[0]
            assert vuln.scan_type == ScanType.SCA
            assert vuln.cve_id is not None
            assert vuln.metadata.get("package") is not None
            assert vuln.metadata.get("version") is not None
    
    @pytest.mark.asyncio
    async def test_container_scan(self, scanner, temp_project):
        """Test container security scan"""
        vulnerabilities = await scanner._container_scan(str(temp_project))
        
        assert len(vulnerabilities) > 0
        
        # Check for expected container security issues
        vulnerability_titles = [v.title for v in vulnerabilities]
        assert any("Container Running as Root" in title for title in vulnerability_titles)
        assert any("Sudo Installed" in title for title in vulnerability_titles)
        
        # Verify container vulnerability details
        root_vuln = next(
            (v for v in vulnerabilities if "Container Running as Root" in v.title), None
        )
        if root_vuln:
            assert root_vuln.severity == VulnerabilitySeverity.MEDIUM
            assert root_vuln.scan_type == ScanType.CONTAINER
    
    @pytest.mark.asyncio
    async def test_infrastructure_scan(self, scanner, temp_project):
        """Test infrastructure as code scan"""
        vulnerabilities = await scanner._infrastructure_scan(str(temp_project))
        
        # Should detect privileged container in docker-compose
        privileged_vulns = [v for v in vulnerabilities if "Privileged Container" in v.title]
        assert len(privileged_vulns) > 0
        
        if privileged_vulns:
            vuln = privileged_vulns[0]
            assert vuln.severity == VulnerabilitySeverity.HIGH
            assert vuln.scan_type == ScanType.INFRASTRUCTURE
    
    @pytest.mark.asyncio
    async def test_compliance_scan(self, scanner, temp_project):
        """Test compliance framework checking"""
        vulnerabilities = await scanner._compliance_scan(str(temp_project))
        
        # Should find OWASP compliance issues
        owasp_vulns = [v for v in vulnerabilities if v.metadata.get("framework") == "OWASP"]
        
        # May or may not find issues depending on content
        for vuln in owasp_vulns:
            assert vuln.scan_type == ScanType.COMPLIANCE
            assert vuln.metadata.get("owasp_category") is not None
    
    @pytest.mark.asyncio
    async def test_comprehensive_scan(self, scanner, temp_project):
        """Test comprehensive application scan"""
        scan_results = await scanner.scan_application(
            str(temp_project),
            {ScanType.SAST, ScanType.SECRETS, ScanType.SCA, ScanType.CONTAINER, ScanType.INFRASTRUCTURE}
        )
        
        # Should have results for all requested scan types
        assert len(scan_results) == 5
        assert ScanType.SAST in scan_results
        assert ScanType.SECRETS in scan_results
        assert ScanType.SCA in scan_results
        assert ScanType.CONTAINER in scan_results
        assert ScanType.INFRASTRUCTURE in scan_results
        
        # All scans should have completed successfully
        for scan_type, result in scan_results.items():
            assert result.status == "completed"
            assert result.duration_seconds > 0
            assert len(result.vulnerabilities) >= 0  # May be 0 for some scan types
    
    def test_scan_report_generation(self, scanner, temp_project):
        """Test scan report generation"""
        # Create mock scan results
        vulnerabilities = [
            SecurityVulnerability(
                id="test_1",
                title="Test Critical Vulnerability",
                description="Test critical issue",
                severity=VulnerabilitySeverity.CRITICAL,
                scan_type=ScanType.SAST,
                file_path="test.py",
                line_number=10,
                remediation="Fix the issue"
            ),
            SecurityVulnerability(
                id="test_2",
                title="Test High Vulnerability",
                description="Test high issue",
                severity=VulnerabilitySeverity.HIGH,
                scan_type=ScanType.SECRETS,
                file_path="config.py",
                line_number=20,
                remediation="Remove secret"
            )
        ]
        
        scan_results = {
            ScanType.SAST: ScanResult(
                scan_id="test_sast",
                scan_type=ScanType.SAST,
                target=str(temp_project),
                start_time=datetime.utcnow(),
                end_time=datetime.utcnow(),
                status="completed",
                vulnerabilities=[vulnerabilities[0]],
                summary={"total": 1, "critical": 1, "high": 0, "medium": 0, "low": 0, "info": 0}
            ),
            ScanType.SECRETS: ScanResult(
                scan_id="test_secrets",
                scan_type=ScanType.SECRETS,
                target=str(temp_project),
                start_time=datetime.utcnow(),
                end_time=datetime.utcnow(),
                status="completed",
                vulnerabilities=[vulnerabilities[1]],
                summary={"total": 1, "critical": 0, "high": 1, "medium": 0, "low": 0, "info": 0}
            )
        }
        
        report = scanner.generate_scan_report(scan_results)
        
        # Verify report structure
        assert "scan_metadata" in report
        assert "summary" in report
        assert "risk_assessment" in report
        assert "vulnerabilities" in report
        assert "remediation_priorities" in report
        assert "compliance_status" in report
        assert "scan_details" in report
        
        # Verify summary
        assert report["summary"]["total_vulnerabilities"] == 2
        assert report["summary"]["critical"] == 1
        assert report["summary"]["high"] == 1
        
        # Verify risk assessment
        assert report["risk_assessment"]["overall_risk_score"] > 0
        assert report["risk_assessment"]["risk_level"] in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "MINIMAL"]
        assert report["risk_assessment"]["pass_fail_status"] == "FAIL"  # Has critical vulnerability
        
        # Verify vulnerabilities
        assert len(report["vulnerabilities"]) == 2
        assert report["vulnerabilities"][0]["severity"] == "critical"
        assert report["vulnerabilities"][1]["severity"] == "high"


class TestSecurityPipelineIntegration:
    """Test cases for security pipeline integration"""
    
    @pytest.fixture
    def logger(self):
        return Mock(spec=StructuredLogger)
    
    @pytest.fixture
    def pipeline_config(self):
        return PipelineConfiguration(
            enabled_stages=[PipelineStage.BUILD, PipelineStage.SECURITY_SCAN],
            fail_pipeline_on_critical=True,
            fail_pipeline_on_high=False,
            generate_reports=True
        )
    
    @pytest.fixture
    def pipeline_context(self):
        return PipelineContext(
            pipeline_id="test-pipeline-123",
            commit_sha="abc123def456",
            branch_name="feature/test",
            repository_url="https://github.com/test/repo",
            environment=DeploymentEnvironment.DEVELOPMENT,
            triggered_by="ci-cd",
            timestamp=datetime.utcnow()
        )
    
    @pytest.fixture
    def pipeline_integration(self, logger, pipeline_config):
        return SecurityPipelineIntegration(logger, pipeline_config)
    
    @pytest.fixture
    def temp_project(self):
        """Create temporary project for testing"""
        temp_dir = tempfile.mkdtemp()
        project_path = Path(temp_dir)
        
        # Create simple Python file
        python_file = project_path / "app.py"
        python_file.write_text("""
def hello_world():
    return "Hello, World!"
""")
        
        yield project_path
        shutil.rmtree(temp_dir)
    
    def test_pipeline_initialization(self, pipeline_integration, pipeline_config):
        """Test pipeline integration initialization"""
        assert pipeline_integration.config == pipeline_config
        assert isinstance(pipeline_integration.scanner, AdvancedVulnerabilityScanner)
        assert len(pipeline_integration.security_gates) > 0
    
    def test_security_gates_initialization(self, pipeline_integration):
        """Test security gates are properly initialized"""
        gates = pipeline_integration.security_gates
        
        # Should have default gates
        gate_names = [gate.name for gate in gates]
        assert "build_security_scan" in gate_names
        assert "dependency_security_scan" in gate_names
        assert "container_security_scan" in gate_names
        assert "compliance_check" in gate_names
        
        # Check gate configurations
        build_gate = next(gate for gate in gates if gate.name == "build_security_scan")
        assert build_gate.stage == PipelineStage.BUILD
        assert build_gate.max_critical == 0
        assert build_gate.blocking is True
        assert ScanType.SAST in build_gate.scan_types
        assert ScanType.SECRETS in build_gate.scan_types
    
    @pytest.mark.asyncio
    async def test_security_gate_execution(self, pipeline_integration, temp_project, pipeline_context):
        """Test individual security gate execution"""
        
        # Get build security gate
        build_gate = next(
            gate for gate in pipeline_integration.security_gates 
            if gate.name == "build_security_scan"
        )
        
        # Create mock pipeline result
        pipeline_result = PipelineResult(
            pipeline_id=pipeline_context.pipeline_id,
            context=pipeline_context,
            security_gates=pipeline_integration.security_gates,
            scan_results={},
            gate_results={},
            overall_status="RUNNING",
            risk_assessment={},
            remediation_report={}
        )
        
        # Execute gate
        gate_result = await pipeline_integration._execute_security_gate(
            build_gate, str(temp_project), pipeline_context, pipeline_result
        )
        
        # Gate should pass for clean project
        assert gate_result is True
        
        # Should have scan results
        expected_scan_keys = [f"build_security_scan_{scan_type.value}" for scan_type in build_gate.scan_types]
        for key in expected_scan_keys:
            assert key in pipeline_result.scan_results
    
    def test_gate_criteria_evaluation(self, pipeline_integration):
        """Test security gate criteria evaluation"""
        
        # Create test gate
        test_gate = SecurityGate(
            name="test_gate",
            stage=PipelineStage.BUILD,
            scan_types=[ScanType.SAST],
            max_critical=0,
            max_high=2,
            max_medium=10
        )
        
        # Create scan results with vulnerabilities
        vulnerabilities = [
            SecurityVulnerability(
                id="v1", title="Critical Issue", description="Test",
                severity=VulnerabilitySeverity.CRITICAL, scan_type=ScanType.SAST
            ),
            SecurityVulnerability(
                id="v2", title="High Issue", description="Test",
                severity=VulnerabilitySeverity.HIGH, scan_type=ScanType.SAST
            ),
            SecurityVulnerability(
                id="v3", title="Medium Issue", description="Test",
                severity=VulnerabilitySeverity.MEDIUM, scan_type=ScanType.SAST
            )
        ]
        
        scan_results = {
            ScanType.SAST: ScanResult(
                scan_id="test",
                scan_type=ScanType.SAST,
                target="test",
                start_time=datetime.utcnow(),
                end_time=datetime.utcnow(),
                status="completed",
                vulnerabilities=vulnerabilities,
                summary={"critical": 1, "high": 1, "medium": 1}
            )
        }
        
        # Should fail due to critical vulnerability
        result = pipeline_integration._evaluate_gate_criteria(test_gate, scan_results)
        assert result is False
        
        # Remove critical vulnerability - should still fail due to high limit
        test_gate.max_critical = 1
        result = pipeline_integration._evaluate_gate_criteria(test_gate, scan_results)
        assert result is True  # Now should pass
    
    @pytest.mark.asyncio
    async def test_full_pipeline_execution(self, pipeline_integration, temp_project, pipeline_context):
        """Test full pipeline execution"""
        
        # Execute pipeline
        pipeline_result = await pipeline_integration.execute_security_pipeline(
            str(temp_project), pipeline_context
        )
        
        # Verify pipeline result
        assert pipeline_result.pipeline_id == pipeline_context.pipeline_id
        assert pipeline_result.context == pipeline_context
        assert pipeline_result.overall_status in ["PASSED", "FAILED", "ERROR"]
        assert pipeline_result.duration_seconds > 0
        
        # Should have gate results
        assert len(pipeline_result.gate_results) > 0
        
        # Should have risk assessment
        assert "risk_level" in pipeline_result.risk_assessment
        assert "risk_score" in pipeline_result.risk_assessment
        
        # Should have remediation report
        assert "total_items" in pipeline_result.remediation_report
    
    def test_risk_assessment(self, pipeline_integration):
        """Test pipeline risk assessment"""
        
        # Create mock pipeline result with vulnerabilities
        vulnerabilities = [
            SecurityVulnerability(
                id="v1", title="Critical", description="Test",
                severity=VulnerabilitySeverity.CRITICAL, scan_type=ScanType.SAST
            ),
            SecurityVulnerability(
                id="v2", title="High", description="Test", 
                severity=VulnerabilitySeverity.HIGH, scan_type=ScanType.SAST
            )
        ]
        
        scan_result = ScanResult(
            scan_id="test",
            scan_type=ScanType.SAST,
            target="test",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            status="completed",
            vulnerabilities=vulnerabilities,
            summary={"critical": 1, "high": 1}
        )
        
        pipeline_result = PipelineResult(
            pipeline_id="test",
            context=Mock(),
            security_gates=[],
            scan_results={"test": scan_result},
            gate_results={"gate1": True, "gate2": False},
            overall_status="FAILED",
            risk_assessment={},
            remediation_report={}
        )
        
        # Assess risk
        risk_assessment = pipeline_integration._assess_pipeline_risk(pipeline_result)
        
        # Verify assessment
        assert risk_assessment["risk_score"] > 0
        assert risk_assessment["risk_level"] in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "MINIMAL"]
        assert risk_assessment["total_vulnerabilities"] == 2
        assert risk_assessment["severity_breakdown"]["critical"] == 1
        assert risk_assessment["severity_breakdown"]["high"] == 1
        assert risk_assessment["deployment_recommendation"] in ["ALLOW", "BLOCK"]
        assert risk_assessment["gates_status"]["total"] == 2
        assert risk_assessment["gates_status"]["passed"] == 1
        assert risk_assessment["gates_status"]["failed"] == 1
    
    def test_remediation_report_generation(self, pipeline_integration):
        """Test remediation report generation"""
        
        # Create pipeline result with various vulnerabilities
        vulnerabilities = [
            SecurityVulnerability(
                id="v1", title="SQL Injection", description="SQL injection vulnerability",
                severity=VulnerabilitySeverity.HIGH, scan_type=ScanType.SAST,
                file_path="app.py", remediation="Use parameterized queries"
            ),
            SecurityVulnerability(
                id="v2", title="SQL Injection", description="Another SQL injection",
                severity=VulnerabilitySeverity.HIGH, scan_type=ScanType.SAST,
                file_path="models.py", remediation="Use parameterized queries"
            ),
            SecurityVulnerability(
                id="v3", title="Hardcoded Secret", description="API key in code",
                severity=VulnerabilitySeverity.CRITICAL, scan_type=ScanType.SECRETS,
                file_path="config.py", remediation="Use environment variables"
            )
        ]
        
        scan_result = ScanResult(
            scan_id="test",
            scan_type=ScanType.SAST,
            target="test",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            status="completed",
            vulnerabilities=vulnerabilities,
            summary={}
        )
        
        pipeline_result = PipelineResult(
            pipeline_id="test",
            context=Mock(),
            security_gates=[],
            scan_results={"test": scan_result},
            gate_results={},
            overall_status="FAILED",
            risk_assessment={},
            remediation_report={}
        )
        
        # Generate remediation report
        remediation_report = pipeline_integration._generate_remediation_report(pipeline_result)
        
        # Verify report
        assert remediation_report["total_items"] == 2  # Two distinct vulnerability types
        assert remediation_report["high_priority_items"] >= 1
        assert len(remediation_report["remediation_items"]) <= 20
        assert remediation_report["estimated_effort_hours"] > 0
        
        # Check top remediation item (should be highest priority)
        top_item = remediation_report["remediation_items"][0]
        assert top_item["title"] in ["SQL Injection", "Hardcoded Secret"]
        assert top_item["count"] > 0
        assert top_item["priority_score"] > 0


class TestPipelineConfigGenerator:
    """Test cases for pipeline configuration generator"""
    
    @pytest.fixture
    def logger(self):
        return Mock(spec=StructuredLogger)
    
    @pytest.fixture
    def config_generator(self, logger):
        return PipelineConfigGenerator(logger)
    
    @pytest.fixture
    def base_config(self):
        return PipelineConfig(
            platform=PipelinePlatform.GITHUB_ACTIONS,
            project_name="test-project",
            security_tools=[SecurityScanTool.BANDIT, SecurityScanTool.SAFETY, SecurityScanTool.TRIVY],
            python_version="3.11",
            fail_on_critical=True,
            fail_on_high=False,
            upload_sarif=True
        )
    
    def test_generator_initialization(self, config_generator):
        """Test configuration generator initialization"""
        assert len(config_generator.default_tools) == 4
        assert PipelinePlatform.GITHUB_ACTIONS in config_generator.default_tools
        assert PipelinePlatform.AZURE_DEVOPS in config_generator.default_tools
    
    def test_github_actions_config_generation(self, config_generator, base_config):
        """Test GitHub Actions configuration generation"""
        
        config_content = config_generator.generate_pipeline_config(base_config)
        
        # Should be valid YAML
        import yaml
        config_dict = yaml.safe_load(config_content)
        
        # Verify structure
        assert "name" in config_dict
        assert "on" in config_dict
        assert "jobs" in config_dict
        assert "security-scan" in config_dict["jobs"]
        
        # Verify job structure
        job = config_dict["jobs"]["security-scan"]
        assert "runs-on" in job
        assert "steps" in job
        
        # Should have steps for each security tool
        step_names = [step.get("name", "") for step in job["steps"]]
        assert any("Bandit" in name for name in step_names)
        assert any("Safety" in name for name in step_names)
        assert any("Trivy" in name for name in step_names)
        assert any("Advanced Security Pipeline" in name for name in step_names)
    
    def test_azure_devops_config_generation(self, config_generator, base_config):
        """Test Azure DevOps configuration generation"""
        
        base_config.platform = PipelinePlatform.AZURE_DEVOPS
        config_content = config_generator.generate_pipeline_config(base_config)
        
        # Should be valid YAML
        import yaml
        config_dict = yaml.safe_load(config_content)
        
        # Verify Azure DevOps structure
        assert "trigger" in config_dict
        assert "pool" in config_dict
        assert "stages" in config_dict
        
        # Should have security stage
        stages = config_dict["stages"]
        assert len(stages) > 0
        assert stages[0]["stage"] == "SecurityScan"
    
    def test_gitlab_ci_config_generation(self, config_generator, base_config):
        """Test GitLab CI configuration generation"""
        
        base_config.platform = PipelinePlatform.GITLAB_CI
        config_content = config_generator.generate_pipeline_config(base_config)
        
        # Should be valid YAML
        import yaml
        config_dict = yaml.safe_load(config_content)
        
        # Verify GitLab CI structure
        assert "stages" in config_dict
        assert "security" in config_dict["stages"]
        
        # Should have security jobs
        job_names = [key for key in config_dict.keys() if key not in ["stages", "variables", "cache", "before_script"]]
        assert any("security" in name.lower() or "bandit" in name.lower() for name in job_names)
    
    def test_jenkins_config_generation(self, config_generator, base_config):
        """Test Jenkins configuration generation"""
        
        base_config.platform = PipelinePlatform.JENKINS
        config_content = config_generator.generate_pipeline_config(base_config)
        
        # Should be valid Jenkinsfile content
        assert "pipeline {" in config_content
        assert "agent any" in config_content
        assert "stages {" in config_content
        assert "Security Scanning" in config_content
    
    def test_all_platforms_generation(self, config_generator, base_config):
        """Test generating configurations for all platforms"""
        
        temp_dir = Path(tempfile.mkdtemp())
        
        try:
            config_generator.generate_all_configs(base_config, temp_dir)
            
            # Should have created files for all platforms
            assert (temp_dir / ".github" / "workflows" / "security-scan.yml").exists()
            assert (temp_dir / ".azure" / "azure-pipelines-security.yml").exists()
            assert (temp_dir / ".gitlab-ci-security.yml").exists()
            assert (temp_dir / "jenkins" / "Jenkinsfile.security").exists()
            
            # Verify each file has content
            for platform_file in [
                temp_dir / ".github" / "workflows" / "security-scan.yml",
                temp_dir / ".azure" / "azure-pipelines-security.yml",
                temp_dir / ".gitlab-ci-security.yml",
                temp_dir / "jenkins" / "Jenkinsfile.security"
            ]:
                assert platform_file.stat().st_size > 0
        
        finally:
            shutil.rmtree(temp_dir)
    
    def test_security_policy_template_generation(self, config_generator):
        """Test security policy template generation"""
        
        temp_file = Path(tempfile.mktemp(suffix=".yml"))
        
        try:
            config_generator.generate_security_policy_template(temp_file)
            
            assert temp_file.exists()
            assert temp_file.stat().st_size > 0
            
            # Should be valid YAML
            import yaml
            with open(temp_file) as f:
                policy = yaml.safe_load(f)
            
            assert "security_policy" in policy
            assert "scan_configuration" in policy["security_policy"]
            assert "security_gates" in policy["security_policy"]
            assert "compliance_frameworks" in policy["security_policy"]
        
        finally:
            if temp_file.exists():
                temp_file.unlink()
    
    def test_dockerfile_generation(self, config_generator):
        """Test Dockerfile generation for security scanning"""
        
        temp_file = Path(tempfile.mktemp(suffix=".dockerfile"))
        
        try:
            config_generator.generate_dockerfile_security_config(temp_file)
            
            assert temp_file.exists()
            assert temp_file.stat().st_size > 0
            
            # Should contain expected security tools
            content = temp_file.read_text()
            assert "bandit" in content.lower()
            assert "safety" in content.lower()
            assert "trivy" in content.lower()
            assert "FROM python:" in content
        
        finally:
            if temp_file.exists():
                temp_file.unlink()
    
    def test_docker_compose_generation(self, config_generator):
        """Test Docker Compose configuration generation"""
        
        temp_file = Path(tempfile.mktemp(suffix=".yml"))
        
        try:
            config_generator.generate_docker_compose_config(temp_file)
            
            assert temp_file.exists()
            assert temp_file.stat().st_size > 0
            
            # Should be valid YAML
            import yaml
            with open(temp_file) as f:
                compose = yaml.safe_load(f)
            
            assert "version" in compose
            assert "services" in compose
            assert "security-scanner" in compose["services"]
        
        finally:
            if temp_file.exists():
                temp_file.unlink()


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])