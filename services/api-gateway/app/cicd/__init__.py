"""
CI/CD Security Integration Package
Comprehensive security scanning integration for continuous integration and deployment pipelines
"""
from app.cicd.security_pipeline import (
    SecurityPipelineIntegration,
    PipelineConfiguration,
    PipelineContext,
    DeploymentEnvironment,
    PipelineStage,
    SecurityGate,
    PipelineResult
)

from app.cicd.pipeline_configs import (
    PipelineConfigGenerator,
    PipelineConfig,
    PipelinePlatform,
    SecurityScanTool
)

from app.security.vulnerability_scanner import (
    AdvancedVulnerabilityScanner,
    ScanConfiguration,
    ScanType,
    VulnerabilitySeverity,
    SecurityVulnerability,
    ScanResult
)

__all__ = [
    # Security Pipeline Integration
    "SecurityPipelineIntegration",
    "PipelineConfiguration", 
    "PipelineContext",
    "DeploymentEnvironment",
    "PipelineStage",
    "SecurityGate",
    "PipelineResult",
    
    # Pipeline Configuration Generator
    "PipelineConfigGenerator",
    "PipelineConfig",
    "PipelinePlatform",
    "SecurityScanTool",
    
    # Vulnerability Scanner
    "AdvancedVulnerabilityScanner",
    "ScanConfiguration",
    "ScanType",
    "VulnerabilitySeverity",
    "SecurityVulnerability",
    "ScanResult"
]

# Version information
__version__ = "1.0.0"
__author__ = "API Gateway Security Team"
__description__ = "Advanced security scanning integration for CI/CD pipelines"