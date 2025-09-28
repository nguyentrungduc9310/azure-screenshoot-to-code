#!/usr/bin/env python3
"""
Security Pipeline Runner
Command-line interface for running security scans in CI/CD pipelines
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.cicd.security_pipeline import (
    SecurityPipelineIntegration, PipelineConfiguration, PipelineContext,
    DeploymentEnvironment, ScanConfiguration, ScanType
)
from app.security.vulnerability_scanner import VulnerabilitySeverity
try:
    from shared.monitoring.structured_logger import StructuredLogger
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Run security scans in CI/CD pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Basic scan
    python -m app.cicd.run_security_pipeline --source-path . --pipeline-id "build-123"
    
    # Full scan with specific configuration
    python -m app.cicd.run_security_pipeline \\
        --source-path . \\
        --pipeline-id "build-123" \\
        --branch "main" \\
        --commit "abc123" \\
        --environment "production" \\
        --config-file "security-policy.yml" \\
        --fail-on-high \\
        --upload-sarif
    
    # Scan specific types only
    python -m app.cicd.run_security_pipeline \\
        --source-path . \\
        --pipeline-id "build-123" \\
        --scan-types "sast,secrets,sca"
        """
    )
    
    # Required arguments
    parser.add_argument(
        "--source-path",
        required=True,
        help="Path to source code to scan"
    )
    
    parser.add_argument(
        "--pipeline-id",
        required=True,
        help="Unique pipeline execution ID"
    )
    
    # Optional context arguments
    parser.add_argument(
        "--branch",
        default="unknown",
        help="Git branch name (default: unknown)"
    )
    
    parser.add_argument(
        "--commit",
        default="unknown",
        help="Git commit SHA (default: unknown)"
    )
    
    parser.add_argument(
        "--repository-url",
        default="unknown",
        help="Repository URL (default: unknown)"
    )
    
    parser.add_argument(
        "--environment",
        choices=["development", "staging", "production"],
        default="development",
        help="Deployment environment (default: development)"
    )
    
    parser.add_argument(
        "--triggered-by",
        default="ci-cd",
        help="Who/what triggered the pipeline (default: ci-cd)"
    )
    
    # Configuration arguments
    parser.add_argument(
        "--config-file",
        help="Path to security policy configuration file"
    )
    
    parser.add_argument(
        "--scan-types",
        help="Comma-separated list of scan types (sast,secrets,sca,container,infrastructure,compliance)"
    )
    
    parser.add_argument(
        "--parallel-scans",
        action="store_true",
        default=True,
        help="Run scans in parallel (default: True)"
    )
    
    parser.add_argument(
        "--no-parallel-scans",
        action="store_false",
        dest="parallel_scans",
        help="Run scans sequentially"
    )
    
    # Failure conditions
    parser.add_argument(
        "--fail-on-critical",
        action="store_true",
        default=True,
        help="Fail pipeline on critical vulnerabilities (default: True)"
    )
    
    parser.add_argument(
        "--no-fail-on-critical",
        action="store_false",
        dest="fail_on_critical",
        help="Don't fail pipeline on critical vulnerabilities"
    )
    
    parser.add_argument(
        "--fail-on-high",
        action="store_true",
        default=False,
        help="Fail pipeline on high severity vulnerabilities (default: False)"
    )
    
    parser.add_argument(
        "--max-scan-duration",
        type=int,
        default=60,
        help="Maximum scan duration in minutes (default: 60)"
    )
    
    # Output options
    parser.add_argument(
        "--output-dir",
        default="security_artifacts",
        help="Output directory for reports (default: security_artifacts)"
    )
    
    parser.add_argument(
        "--generate-sarif",
        action="store_true",
        default=True,
        help="Generate SARIF format report (default: True)"
    )
    
    parser.add_argument(
        "--upload-sarif",
        action="store_true",
        default=False,
        help="Upload SARIF to security platform (default: False)"
    )
    
    parser.add_argument(
        "--baseline-comparison",
        action="store_true",
        default=True,
        help="Compare results with baseline (default: True)"
    )
    
    parser.add_argument(
        "--auto-remediation",
        action="store_true",
        default=False,
        help="Attempt automatic remediation (default: False)"
    )
    
    # Verbosity
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress non-error output"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    
    # CI/CD platform specific
    parser.add_argument(
        "--ci-platform",
        choices=["github", "azure", "gitlab", "jenkins", "generic"],
        default="generic",
        help="CI/CD platform for platform-specific integrations"
    )
    
    return parser.parse_args()


def load_configuration(config_file: Optional[str], args) -> PipelineConfiguration:
    """Load pipeline configuration from file and command line arguments"""
    
    # Start with default configuration
    config = PipelineConfiguration()
    
    # Load from file if specified
    if config_file and Path(config_file).exists():
        try:
            try:
                import yaml
                with open(config_file, 'r') as f:
                    file_config = yaml.safe_load(f)
            except ImportError:
                # Fallback to JSON if YAML not available
                with open(config_file, 'r') as f:
                    file_config = json.load(f)
            
            # Apply file configuration
            security_policy = file_config.get('security_policy', {})
            
            if 'scan_configuration' in security_policy:
                scan_config = security_policy['scan_configuration']
                
                config.scan_configuration.enabled_scan_types = set(
                    ScanType(scan_type) for scan_type in scan_config.get('enabled_scan_types', [])
                )
                config.scan_configuration.max_scan_duration_minutes = scan_config.get('max_scan_duration_minutes', 60)
                config.scan_configuration.parallel_scans = scan_config.get('parallel_scans', True)
                config.scan_configuration.fail_on_critical = scan_config.get('fail_on_critical', True)
                config.scan_configuration.fail_on_high = scan_config.get('fail_on_high', False)
                config.scan_configuration.exclude_patterns = scan_config.get('exclude_patterns', [])
                config.scan_configuration.include_patterns = scan_config.get('include_patterns', [])
                config.scan_configuration.compliance_frameworks = scan_config.get('compliance_frameworks', [])
            
        except Exception as e:
            print(f"Warning: Failed to load configuration file {config_file}: {e}", file=sys.stderr)
    
    # Override with command line arguments
    if args.scan_types:
        scan_type_map = {
            'sast': ScanType.SAST,
            'secrets': ScanType.SECRETS,
            'sca': ScanType.SCA,
            'container': ScanType.CONTAINER,
            'infrastructure': ScanType.INFRASTRUCTURE,
            'compliance': ScanType.COMPLIANCE
        }
        
        enabled_types = set()
        for scan_type_name in args.scan_types.split(','):
            scan_type_name = scan_type_name.strip().lower()
            if scan_type_name in scan_type_map:
                enabled_types.add(scan_type_map[scan_type_name])
        
        config.scan_configuration.enabled_scan_types = enabled_types
    
    # Apply other command line arguments
    config.scan_configuration.parallel_scans = args.parallel_scans
    config.scan_configuration.max_scan_duration_minutes = args.max_scan_duration
    config.fail_pipeline_on_critical = args.fail_on_critical
    config.fail_pipeline_on_high = args.fail_on_high
    config.baseline_comparison = args.baseline_comparison
    config.auto_remediation = args.auto_remediation
    config.generate_reports = True
    
    return config


def setup_logging(args) -> StructuredLogger:
    """Setup structured logging"""
    
    if args.quiet:
        log_level = "ERROR"
    elif args.verbose:
        log_level = "DEBUG"
    else:
        log_level = args.log_level
    
    logger = StructuredLogger(
        service_name="security-pipeline",
        environment="ci-cd",
        log_level=log_level
    )
    
    return logger


def create_pipeline_context(args) -> PipelineContext:
    """Create pipeline execution context"""
    
    return PipelineContext(
        pipeline_id=args.pipeline_id,
        commit_sha=args.commit,
        branch_name=args.branch,
        repository_url=args.repository_url,
        environment=DeploymentEnvironment(args.environment),
        triggered_by=args.triggered_by,
        timestamp=datetime.utcnow(),
        metadata={
            "ci_platform": args.ci_platform,
            "source_path": args.source_path,
            "output_dir": args.output_dir
        }
    )


def print_summary(pipeline_result, args):
    """Print pipeline execution summary"""
    
    if args.quiet:
        return
    
    print("\n" + "="*80)
    print("SECURITY PIPELINE SUMMARY")
    print("="*80)
    
    # Basic information
    print(f"Pipeline ID: {pipeline_result.pipeline_id}")
    print(f"Branch: {pipeline_result.context.branch_name}")
    print(f"Environment: {pipeline_result.context.environment.value}")
    print(f"Duration: {pipeline_result.duration_seconds:.1f} seconds")
    print(f"Overall Status: {pipeline_result.overall_status}")
    
    # Risk assessment
    risk = pipeline_result.risk_assessment
    print(f"\nRisk Assessment:")
    print(f"  Risk Level: {risk.get('risk_level', 'UNKNOWN')}")
    print(f"  Risk Score: {risk.get('risk_score', 0):.1f}/100")
    print(f"  Total Vulnerabilities: {risk.get('total_vulnerabilities', 0)}")
    
    # Severity breakdown
    severity_breakdown = risk.get('severity_breakdown', {})
    print(f"  Critical: {severity_breakdown.get('critical', 0)}")
    print(f"  High: {severity_breakdown.get('high', 0)}")
    print(f"  Medium: {severity_breakdown.get('medium', 0)}")
    print(f"  Low: {severity_breakdown.get('low', 0)}")
    print(f"  Info: {severity_breakdown.get('info', 0)}")
    
    # Security gates
    gates_status = risk.get('gates_status', {})
    print(f"\nSecurity Gates:")
    print(f"  Total: {gates_status.get('total', 0)}")
    print(f"  Passed: {gates_status.get('passed', 0)}")
    print(f"  Failed: {gates_status.get('failed', 0)}")
    
    # Deployment recommendation
    print(f"\nDeployment Recommendation: {risk.get('deployment_recommendation', 'UNKNOWN')}")
    
    # Artifacts
    if pipeline_result.artifacts:
        print(f"\nGenerated Artifacts:")
        for artifact in pipeline_result.artifacts:
            print(f"  - {artifact}")
    
    print("="*80)


def handle_ci_platform_integration(args, pipeline_result):
    """Handle CI/CD platform specific integrations"""
    
    # GitHub Actions integration
    if args.ci_platform == "github":
        # Set output variables
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                f.write(f"security_status={pipeline_result.overall_status}\n")
                f.write(f"risk_level={pipeline_result.risk_assessment.get('risk_level', 'UNKNOWN')}\n")
                f.write(f"total_vulnerabilities={pipeline_result.risk_assessment.get('total_vulnerabilities', 0)}\n")
                f.write(f"critical_count={pipeline_result.risk_assessment.get('severity_breakdown', {}).get('critical', 0)}\n")
        
        # Create step summary
        if 'GITHUB_STEP_SUMMARY' in os.environ:
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'w') as f:
                f.write("# Security Scan Results\n\n")
                f.write(f"**Status:** {pipeline_result.overall_status}\n")
                f.write(f"**Risk Level:** {pipeline_result.risk_assessment.get('risk_level', 'UNKNOWN')}\n")
                f.write(f"**Total Vulnerabilities:** {pipeline_result.risk_assessment.get('total_vulnerabilities', 0)}\n\n")
                
                severity_breakdown = pipeline_result.risk_assessment.get('severity_breakdown', {})
                f.write("## Vulnerability Breakdown\n")
                f.write(f"- Critical: {severity_breakdown.get('critical', 0)}\n")
                f.write(f"- High: {severity_breakdown.get('high', 0)}\n")
                f.write(f"- Medium: {severity_breakdown.get('medium', 0)}\n")
                f.write(f"- Low: {severity_breakdown.get('low', 0)}\n")
    
    # Azure DevOps integration
    elif args.ci_platform == "azure":
        # Set pipeline variables
        print(f"##vso[task.setvariable variable=SecurityStatus;isOutput=true]{pipeline_result.overall_status}")
        print(f"##vso[task.setvariable variable=RiskLevel;isOutput=true]{pipeline_result.risk_assessment.get('risk_level', 'UNKNOWN')}")
        print(f"##vso[task.setvariable variable=TotalVulnerabilities;isOutput=true]{pipeline_result.risk_assessment.get('total_vulnerabilities', 0)}")
    
    # GitLab CI integration
    elif args.ci_platform == "gitlab":
        # Create GitLab CI artifacts and reports
        metrics_file = Path(args.output_dir) / args.pipeline_id / "gitlab-metrics.json"
        metrics_file.parent.mkdir(parents=True, exist_ok=True)
        
        gitlab_metrics = {
            "security_status": pipeline_result.overall_status,
            "risk_level": pipeline_result.risk_assessment.get('risk_level', 'UNKNOWN'),
            "total_vulnerabilities": pipeline_result.risk_assessment.get('total_vulnerabilities', 0),
            "severity_breakdown": pipeline_result.risk_assessment.get('severity_breakdown', {})
        }
        
        with open(metrics_file, 'w') as f:
            json.dump(gitlab_metrics, f, indent=2)


async def main():
    """Main entry point"""
    
    # Parse arguments
    args = parse_arguments()
    
    # Setup logging
    logger = setup_logging(args)
    
    try:
        logger.info("Starting security pipeline execution",
                   pipeline_id=args.pipeline_id,
                   source_path=args.source_path,
                   branch=args.branch,
                   environment=args.environment)
        
        # Load configuration
        config = load_configuration(args.config_file, args)
        
        # Create pipeline context
        context = create_pipeline_context(args)
        
        # Initialize security pipeline
        pipeline = SecurityPipelineIntegration(logger, config)
        
        # Ensure source path exists
        source_path = Path(args.source_path)
        if not source_path.exists():
            logger.error("Source path does not exist", path=args.source_path)
            sys.exit(1)
        
        # Execute security pipeline
        pipeline_result = await pipeline.execute_security_pipeline(
            source_path=str(source_path.resolve()),
            context=context
        )
        
        # Create output directory
        output_dir = Path(args.output_dir) / args.pipeline_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save pipeline result
        result_file = output_dir / "pipeline_result.json"
        with open(result_file, 'w') as f:
            json.dump({
                "pipeline_id": pipeline_result.pipeline_id,
                "overall_status": pipeline_result.overall_status,
                "duration_seconds": pipeline_result.duration_seconds,
                "risk_assessment": pipeline_result.risk_assessment,
                "gate_results": pipeline_result.gate_results,
                "artifacts": pipeline_result.artifacts,
                "metadata": pipeline_result.metadata
            }, f, indent=2, default=str)
        
        # Print summary
        print_summary(pipeline_result, args)
        
        # Handle CI/CD platform integrations
        handle_ci_platform_integration(args, pipeline_result)
        
        # Upload SARIF if requested
        if args.upload_sarif and args.generate_sarif:
            sarif_file = output_dir / "security_report.sarif"
            if sarif_file.exists():
                logger.info("SARIF report generated", file=str(sarif_file))
                # Platform-specific SARIF upload would go here
        
        # Determine exit code
        if pipeline_result.overall_status == "FAILED":
            if args.fail_on_critical or args.fail_on_high:
                logger.error("Pipeline failed due to security gate violations")
                sys.exit(1)
            else:
                logger.warning("Security issues found but pipeline allowed to continue")
        
        logger.info("Security pipeline execution completed successfully",
                   pipeline_id=args.pipeline_id,
                   status=pipeline_result.overall_status,
                   duration=pipeline_result.duration_seconds)
        
        sys.exit(0)
        
    except KeyboardInterrupt:
        logger.info("Security pipeline execution interrupted")
        sys.exit(130)
    
    except Exception as e:
        logger.error("Security pipeline execution failed", error=str(e))
        
        if args.verbose:
            import traceback
            traceback.print_exc()
        
        sys.exit(1)


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())