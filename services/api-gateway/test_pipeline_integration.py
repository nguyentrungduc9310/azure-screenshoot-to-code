#!/usr/bin/env python3
"""
Test Security Pipeline Integration
"""
import sys
import asyncio
import tempfile
import json
from pathlib import Path

# Add current directory to path
sys.path.insert(0, '.')

# Import mock logger directly
import importlib.util
spec = importlib.util.spec_from_file_location("mock_logger", "app/cicd/mock_logger.py")
mock_logger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mock_logger)

# Import security pipeline directly
spec = importlib.util.spec_from_file_location("security_pipeline", "app/cicd/security_pipeline.py")
security_pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(security_pipeline)

# Import pipeline configs directly
spec = importlib.util.spec_from_file_location("pipeline_configs", "app/cicd/pipeline_configs.py")
pipeline_configs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline_configs)

async def test_pipeline_integration():
    """Test complete security pipeline integration"""
    
    print("=" * 80)
    print("TESTING SECURITY PIPELINE INTEGRATION")
    print("=" * 80)
    
    # 1. Test Pipeline Configuration Generation
    print("\n1. Testing Pipeline Configuration Generation...")
    logger = mock_logger.MockStructuredLogger("test-pipeline")
    config_generator = pipeline_configs.PipelineConfigGenerator(logger)
    
    # Test GitHub Actions config
    github_config = pipeline_configs.PipelineConfig(
        platform=pipeline_configs.PipelinePlatform.GITHUB_ACTIONS,
        project_name="test-project",
        fail_on_critical=True,
        fail_on_high=False
    )
    
    github_yaml = config_generator.generate_pipeline_config(github_config)
    print(f"✓ Generated GitHub Actions config ({len(github_yaml)} characters)")
    
    # Test Azure DevOps config
    azure_config = pipeline_configs.PipelineConfig(
        platform=pipeline_configs.PipelinePlatform.AZURE_DEVOPS,
        project_name="test-project"
    )
    
    azure_yaml = config_generator.generate_pipeline_config(azure_config)
    print(f"✓ Generated Azure DevOps config ({len(azure_yaml)} characters)")
    
    # 2. Test Security Pipeline Execution
    print("\n2. Testing Security Pipeline Execution...")
    
    # Create pipeline configuration
    pipeline_config = security_pipeline.PipelineConfiguration(
        scan_configuration=security_pipeline.ScanConfiguration(
            enabled_scan_types={
                security_pipeline.ScanType.SAST,
                security_pipeline.ScanType.SECRETS
            },
            max_scan_duration_minutes=5,
            parallel_scans=False,
            fail_on_critical=True
        ),
        fail_pipeline_on_critical=True,
        baseline_comparison=True,
        generate_reports=True
    )
    
    # Create pipeline context
    from datetime import datetime
    context = security_pipeline.PipelineContext(
        pipeline_id="test-pipeline-001",
        commit_sha="abc123",
        branch_name="main",
        repository_url="https://github.com/test/repo",
        environment=security_pipeline.DeploymentEnvironment.DEVELOPMENT,
        triggered_by="test",
        timestamp=datetime.utcnow(),
        metadata={"test": True}
    )
    
    # Initialize pipeline
    pipeline = security_pipeline.SecurityPipelineIntegration(logger, pipeline_config)
    
    # Create test project with vulnerabilities
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir)
        
        # Create test file with security issues
        test_file = project_path / "vulnerable_app.py"
        test_file.write_text("""
# Vulnerable test application
import subprocess
import os

API_SECRET = "sk-1234567890abcdef"  # Hardcoded secret
DATABASE_PASSWORD = "admin123"      # Another secret

def unsafe_command(user_input):
    # Command injection vulnerability
    command = f"ls {user_input}"
    subprocess.run(command, shell=True)

def sql_injection(user_id):
    # SQL injection vulnerability
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    return query

def path_traversal(filename):
    # Path traversal vulnerability
    with open(f"/var/data/{filename}", 'r') as f:
        return f.read()
""")
        
        # Create requirements.txt with vulnerable dependencies
        requirements_file = project_path / "requirements.txt"
        requirements_file.write_text("""
# Vulnerable dependencies for testing
requests==2.25.1
urllib3==1.26.0
jinja2==2.10.1
""")
        
        print(f"Created test project at: {project_path}")
        
        # Execute security pipeline
        print("Running security pipeline...")
        pipeline_result = await pipeline.execute_security_pipeline(
            source_path=str(project_path),
            context=context
        )
        
        # Verify results
        print(f"\n3. Pipeline Results:")
        print(f"  Pipeline ID: {pipeline_result.pipeline_id}")
        print(f"  Overall Status: {pipeline_result.overall_status}")
        print(f"  Duration: {pipeline_result.duration_seconds:.2f} seconds")
        
        # Risk assessment
        risk = pipeline_result.risk_assessment
        print(f"\n4. Risk Assessment:")
        print(f"  Risk Level: {risk.get('risk_level', 'UNKNOWN')}")
        print(f"  Risk Score: {risk.get('risk_score', 0):.1f}/100")
        print(f"  Total Vulnerabilities: {risk.get('total_vulnerabilities', 0)}")
        
        # Severity breakdown
        severity = risk.get('severity_breakdown', {})
        print(f"  Critical: {severity.get('critical', 0)}")
        print(f"  High: {severity.get('high', 0)}")
        print(f"  Medium: {severity.get('medium', 0)}")
        print(f"  Low: {severity.get('low', 0)}")
        
        # Security gates
        gates = risk.get('gates_status', {})
        print(f"\n5. Security Gates:")
        print(f"  Total Gates: {gates.get('total', 0)}")
        print(f"  Passed: {gates.get('passed', 0)}")
        print(f"  Failed: {gates.get('failed', 0)}")
        
        # Gate results details
        if pipeline_result.gate_results:
            print(f"\n6. Gate Details:")
            for gate_name, gate_result in pipeline_result.gate_results.items():
                status = "✓ PASS" if gate_result.get('passed', False) else "✗ FAIL"
                print(f"  {gate_name}: {status}")
        
        # Artifacts
        if pipeline_result.artifacts:
            print(f"\n7. Generated Artifacts:")
            for artifact in pipeline_result.artifacts:
                print(f"  - {artifact}")
        
        # Deployment recommendation
        recommendation = risk.get('deployment_recommendation', 'UNKNOWN')
        print(f"\n8. Deployment Recommendation: {recommendation}")
        
    print("\n" + "=" * 80)
    print("✓ SECURITY PIPELINE INTEGRATION TEST COMPLETED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_pipeline_integration())