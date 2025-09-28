# Security Scanning Integration Documentation

## Overview

The Security Scanning Integration provides comprehensive automated security scanning capabilities for CI/CD pipelines. This system integrates advanced vulnerability detection, compliance checking, and automated reporting into continuous integration and deployment workflows.

## Architecture Overview

### Core Components

```
┌─────────────────────────────────────────────────────────────────┐
│                Security Scanning Integration                    │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐   │
│  │   Vulnerability │ │   CI/CD         │ │   Pipeline      │   │
│  │   Scanner       │ │   Pipeline      │ │   Config        │   │
│  │                 │ │   Integration   │ │   Generator     │   │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                │
           ┌────────────────────┼────────────────────┐
           │                    │                    │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│SAST Scanner     │    │Secrets Detection │    │SCA Scanner      │
│• Static Analysis│    │• API Keys        │    │• Dependencies   │
│• Code Patterns  │    │• Passwords       │    │• CVE Database   │
│• Security Rules │    │• Tokens          │    │• License Check  │
└─────────────────┘    └──────────────────┘    └─────────────────┘

┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│Container        │    │Infrastructure    │    │Compliance       │
│Security         │    │Security          │    │Framework        │
│• Dockerfile     │    │• IaC Analysis    │    │• OWASP Top 10   │
│• Base Images    │    │• Config Review   │    │• CIS Benchmarks │
│• Privileges     │    │• Network Rules   │    │• NIST Framework │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Vulnerability Scanner

### Advanced Vulnerability Scanner

The `AdvancedVulnerabilityScanner` provides comprehensive security scanning capabilities:

#### Scan Types

**Static Application Security Testing (SAST)**
- Code pattern analysis
- Security rule violations
- Common vulnerability detection
- Framework-specific checks

**Secrets Detection**
- API key exposure
- Hardcoded passwords
- JWT tokens
- Cloud credentials

**Software Composition Analysis (SCA)**
- Dependency vulnerability scanning
- License compliance checking
- Version analysis
- CVE database integration

**Container Security**
- Dockerfile security analysis
- Base image vulnerability scanning
- Runtime configuration review
- Privilege escalation detection

**Infrastructure Security**
- Infrastructure as Code analysis
- Configuration drift detection
- Network security rules
- Access control validation

**Compliance Framework Checking**
- OWASP Top 10 compliance
- CIS Benchmark validation
- NIST Cybersecurity Framework
- Industry-specific standards

#### Configuration

```python
from app.security.vulnerability_scanner import (
    AdvancedVulnerabilityScanner, ScanConfiguration, ScanType
)

# Configure scanner
config = ScanConfiguration(
    enabled_scan_types={
        ScanType.SAST,
        ScanType.SECRETS,
        ScanType.SCA,
        ScanType.CONTAINER,
        ScanType.INFRASTRUCTURE,
        ScanType.COMPLIANCE
    },
    max_scan_duration_minutes=60,
    parallel_scans=True,
    fail_on_critical=True,
    fail_on_high=False,
    exclude_patterns=[
        "*/node_modules/*",
        "*/venv/*",
        "*/.git/*"
    ],
    compliance_frameworks=["OWASP", "CIS", "NIST"]
)

# Initialize scanner
scanner = AdvancedVulnerabilityScanner(logger, config)

# Perform comprehensive scan
scan_results = await scanner.scan_application(
    target_path="/path/to/source",
    scan_types={ScanType.SAST, ScanType.SECRETS}
)

# Generate report
report = scanner.generate_scan_report(scan_results)
```

### Vulnerability Detection Patterns

**SQL Injection Detection**
```python
# Pattern: SQL query construction with string formatting
vulnerable_patterns = {
    "sql_injection": {
        "pattern": r"(execute|query|cursor\.execute).*%.*",
        "severity": "high",
        "cwe_id": "CWE-89"
    }
}
```

**Command Injection Detection**
```python
# Pattern: Shell command execution with user input
vulnerable_patterns = {
    "command_injection": {
        "pattern": r"(os\.system|subprocess\.call).*shell=True",
        "severity": "high", 
        "cwe_id": "CWE-78"
    }
}
```

**Hardcoded Secrets Detection**
```python
# Pattern: Hardcoded credentials in source code
secret_patterns = {
    "aws_access_key": {
        "pattern": r"AKIA[0-9A-Z]{16}",
        "severity": "critical"
    },
    "generic_api_key": {
        "pattern": r"['\"]?[a-zA-Z0-9_-]*api[_-]?key['\"]?\s*[:=]\s*['\"]?[a-zA-Z0-9_-]{20,}['\"]?",
        "severity": "high"
    }
}
```

## CI/CD Pipeline Integration

### Security Pipeline Integration

The `SecurityPipelineIntegration` class orchestrates security scanning within CI/CD pipelines:

#### Pipeline Configuration

```python
from app.cicd.security_pipeline import (
    SecurityPipelineIntegration, PipelineConfiguration, 
    PipelineContext, DeploymentEnvironment
)

# Configure pipeline
config = PipelineConfiguration(
    enabled_stages=[PipelineStage.BUILD, PipelineStage.SECURITY_SCAN],
    fail_pipeline_on_critical=True,
    fail_pipeline_on_high=False,
    generate_reports=True,
    upload_results=True,
    baseline_comparison=True,
    auto_remediation=False
)

# Create pipeline context
context = PipelineContext(
    pipeline_id="build-123",
    commit_sha="abc123def456",
    branch_name="main",
    repository_url="https://github.com/org/repo",
    environment=DeploymentEnvironment.PRODUCTION,
    triggered_by="ci-cd",
    timestamp=datetime.utcnow()
)

# Execute security pipeline
pipeline = SecurityPipelineIntegration(logger, config)
result = await pipeline.execute_security_pipeline(
    source_path="/path/to/source",
    context=context
)
```

#### Security Gates

Security gates define quality criteria that must be met for pipeline progression:

```python
# Example security gate configuration
security_gates = [
    SecurityGate(
        name="build_security_scan",
        stage=PipelineStage.BUILD,
        scan_types=[ScanType.SAST, ScanType.SECRETS],
        max_critical=0,
        max_high=2,
        max_medium=10,
        blocking=True
    ),
    SecurityGate(
        name="production_readiness_gate",
        stage=PipelineStage.DEPLOY,
        scan_types=[ScanType.SAST, ScanType.SECRETS, ScanType.SCA, ScanType.CONTAINER],
        max_critical=0,
        max_high=0,
        max_medium=5,
        compliance_required=["OWASP", "CIS"],
        blocking=True
    )
]
```

#### Risk Assessment

The pipeline generates comprehensive risk assessments:

```python
# Example risk assessment output
risk_assessment = {
    "risk_score": 45.0,
    "risk_level": "MEDIUM",
    "deployment_recommendation": "ALLOW",
    "total_vulnerabilities": 8,
    "severity_breakdown": {
        "critical": 0,
        "high": 2,
        "medium": 4,
        "low": 2,
        "info": 0
    },
    "gates_status": {
        "total": 4,
        "passed": 3,
        "failed": 1
    }
}
```

## Pipeline Configuration Generator

### Multi-Platform Support

Generate CI/CD pipeline configurations for different platforms:

```python
from app.cicd.pipeline_configs import (
    PipelineConfigGenerator, PipelineConfig, 
    PipelinePlatform, SecurityScanTool
)

# Configure pipeline generation
config = PipelineConfig(
    platform=PipelinePlatform.GITHUB_ACTIONS,
    project_name="my-project",
    security_tools=[
        SecurityScanTool.BANDIT,
        SecurityScanTool.SAFETY,
        SecurityScanTool.TRIVY,
        SecurityScanTool.CODEQL
    ],
    python_version="3.11",
    fail_on_critical=True,
    fail_on_high=False,
    upload_sarif=True
)

# Generate configuration
generator = PipelineConfigGenerator(logger)
pipeline_yaml = generator.generate_pipeline_config(config)

# Generate for all platforms
generator.generate_all_configs(config, output_dir="./pipeline-configs")
```

### GitHub Actions Example

```yaml
name: Security Scan - my-project
on:
  push:
    branches: ["main", "develop", "release/*"]
  pull_request:
    branches: ["main", "develop"]
  schedule:
    - cron: "0 2 * * 1"

permissions:
  contents: read
  security-events: write
  actions: read

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      
      - name: Run Bandit security scan
        run: |
          pip install bandit[toml]
          bandit -r . -f json -o bandit-report.json || true
      
      - name: Run Safety check
        run: |
          pip install safety
          safety check --json --output safety-report.json || true
      
      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          format: 'sarif'
          output: 'trivy-results.sarif'
      
      - name: Initialize CodeQL
        uses: github/codeql-action/init@v2
        with:
          languages: python
      
      - name: Run Advanced Security Pipeline
        run: |
          python -m app.cicd.run_security_pipeline \
            --source-path . \
            --pipeline-id ${{ github.run_id }} \
            --branch ${{ github.ref_name }} \
            --commit ${{ github.sha }}
      
      - name: Upload Security Reports
        uses: actions/upload-artifact@v3
        with:
          name: security-reports
          path: security_artifacts/
```

## Command Line Interface

### Security Pipeline Runner

The `run_security_pipeline.py` script provides a command-line interface:

```bash
# Basic scan
python -m app.cicd.run_security_pipeline \
  --source-path . \
  --pipeline-id "build-123"

# Full scan with configuration
python -m app.cicd.run_security_pipeline \
  --source-path . \
  --pipeline-id "build-123" \
  --branch "main" \
  --commit "abc123" \
  --environment "production" \
  --config-file "security-policy.yml" \
  --fail-on-high \
  --upload-sarif

# Specific scan types only
python -m app.cicd.run_security_pipeline \
  --source-path . \
  --pipeline-id "build-123" \
  --scan-types "sast,secrets,sca"
```

### Command Line Options

```bash
Required Arguments:
  --source-path PATH        Path to source code to scan
  --pipeline-id ID          Unique pipeline execution ID

Optional Arguments:
  --branch NAME             Git branch name
  --commit SHA              Git commit SHA
  --environment ENV         Deployment environment (development|staging|production)
  --config-file PATH        Security policy configuration file
  --scan-types TYPES        Comma-separated scan types
  --fail-on-critical        Fail pipeline on critical vulnerabilities
  --fail-on-high           Fail pipeline on high severity vulnerabilities
  --max-scan-duration N     Maximum scan duration in minutes
  --output-dir PATH         Output directory for reports
  --generate-sarif          Generate SARIF format report
  --baseline-comparison     Compare results with baseline
  --auto-remediation        Attempt automatic remediation
  --ci-platform PLATFORM   CI/CD platform (github|azure|gitlab|jenkins)
  --verbose                 Enable verbose output
  --quiet                   Suppress non-error output
```

## Security Policy Configuration

### YAML Configuration File

```yaml
security_policy:
  version: "1.0"
  description: "Security scanning and compliance policy"
  
  scan_configuration:
    enabled_scan_types:
      - "static_analysis"
      - "secrets_detection"
      - "software_composition"
      - "container_security"
      - "infrastructure_security"
      - "compliance_check"
    
    max_scan_duration_minutes: 60
    parallel_scans: true
    fail_on_critical: true
    fail_on_high: false
    
    exclude_patterns:
      - "*/node_modules/*"
      - "*/venv/*"
      - "*/build/*"
      - "*/dist/*"
      - "*/.git/*"
    
    include_patterns:
      - "**/*.py"
      - "**/*.js"
      - "**/*.ts"
      - "**/*.yml"
      - "**/*.yaml"
      - "**/Dockerfile*"
      - "**/requirements*.txt"
    
    compliance_frameworks:
      - "OWASP"
      - "CIS"
      - "NIST"
  
  security_gates:
    - name: "build_security_gate"
      stage: "build"
      scan_types: ["static_analysis", "secrets_detection"]
      max_critical: 0
      max_high: 2
      max_medium: 10
      blocking: true
    
    - name: "production_readiness_gate"
      stage: "deploy"
      scan_types: ["static_analysis", "secrets_detection", "software_composition", "container_security"]
      max_critical: 0
      max_high: 0
      max_medium: 5
      compliance_required: ["OWASP", "CIS"]
      blocking: true
  
  notification_settings:
    slack_webhook: "${SLACK_WEBHOOK_URL}"
    email_recipients:
      - "security-team@company.com"
    notify_on_failure: true
    notify_on_new_vulnerabilities: true
  
  remediation_settings:
    auto_remediation: false
    create_issues: true
    assign_to: "security-team"
```

## Integration Examples

### GitHub Actions Integration

```yaml
# .github/workflows/security-scan.yml
name: Security Scan
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Run Security Pipeline
        run: |
          python -m app.cicd.run_security_pipeline \
            --source-path . \
            --pipeline-id ${{ github.run_id }} \
            --branch ${{ github.ref_name }} \
            --commit ${{ github.sha }} \
            --ci-platform github \
            --fail-on-critical
      
      - name: Upload SARIF results
        uses: github/codeql-action/upload-sarif@v2
        if: always()
        with:
          sarif_file: security_artifacts/${{ github.run_id }}/security_report.sarif
```

### Azure DevOps Integration

```yaml
# azure-pipelines-security.yml
trigger:
  branches:
    include: [main, develop]

pool:
  vmImage: 'ubuntu-latest'

steps:
- task: UsePythonVersion@0
  inputs:
    versionSpec: '3.11'

- script: |
    python -m app.cicd.run_security_pipeline \
      --source-path . \
      --pipeline-id $(Build.BuildId) \
      --branch $(Build.SourceBranchName) \
      --commit $(Build.SourceVersion) \
      --ci-platform azure \
      --fail-on-critical
  displayName: 'Run Security Pipeline'

- task: PublishBuildArtifacts@1
  inputs:
    PathtoPublish: 'security_artifacts/'
    ArtifactName: 'security-reports'
```

### GitLab CI Integration

```yaml
# .gitlab-ci.yml
stages:
  - security

security_scan:
  stage: security
  image: python:3.11
  script:
    - python -m app.cicd.run_security_pipeline
        --source-path .
        --pipeline-id $CI_PIPELINE_ID
        --branch $CI_COMMIT_REF_NAME
        --commit $CI_COMMIT_SHA
        --ci-platform gitlab
        --fail-on-critical
  artifacts:
    paths:
      - security_artifacts/
    expire_in: 1 week
  allow_failure: false
```

## Report Formats

### JSON Report Format

```json
{
  "pipeline_metadata": {
    "pipeline_id": "build-123",
    "commit_sha": "abc123def456",
    "branch_name": "main",
    "environment": "production",
    "timestamp": "2024-01-15T10:30:00Z",
    "duration_seconds": 127.5,
    "overall_status": "PASSED"
  },
  "risk_assessment": {
    "risk_score": 25.0,
    "risk_level": "LOW",
    "deployment_recommendation": "ALLOW",
    "total_vulnerabilities": 3,
    "severity_breakdown": {
      "critical": 0,
      "high": 0,
      "medium": 2,
      "low": 1,
      "info": 0
    }
  },
  "vulnerabilities": [
    {
      "id": "sql_injection_app_py_45",
      "title": "Potential SQL Injection",
      "severity": "medium",
      "scan_type": "static_analysis",
      "file_path": "app.py",
      "line_number": 45,
      "description": "SQL query construction using string formatting",
      "remediation": "Use parameterized queries or ORM methods",
      "cwe_id": "CWE-89"
    }
  ],
  "remediation_report": {
    "total_items": 2,
    "high_priority_items": 0,
    "estimated_effort_hours": 3.5,
    "remediation_items": [
      {
        "title": "Potential SQL Injection",
        "severity": "medium",
        "count": 2,
        "priority_score": 8.0,
        "remediation": "Use parameterized queries or ORM methods"
      }
    ]
  }
}
```

## Installation

### Prerequisites

- Python 3.11 or higher
- Git for version control
- CI/CD platform (GitHub Actions, Azure DevOps, GitLab CI, or Jenkins)

### Basic Installation

1. **Install the security scanning dependencies:**

```bash
pip install bandit[toml] safety semgrep trivy pip-audit
```

2. **Clone or integrate with your project:**

```bash
# Add to your existing project
git clone <repository>
cd services/api-gateway
```

3. **Configure security policy:**

```bash
# Generate security policy template
python -m app.cicd.pipeline_configs generate-policy security-policy.yml
```

## Usage Examples

### Basic Security Scan

```bash
# Run basic security scan
python -m app.cicd.run_security_pipeline \
    --source-path . \
    --pipeline-id "local-scan-001" \
    --branch "main"
```

### Advanced Configuration

```bash
# Run comprehensive scan with specific settings
python -m app.cicd.run_security_pipeline \
    --source-path . \
    --pipeline-id "build-123" \
    --branch "main" \
    --commit "abc123" \
    --environment "production" \
    --config-file "security-policy.yml" \
    --scan-types "sast,secrets,sca" \
    --fail-on-high \
    --upload-sarif
```

## CI/CD Integration

### GitHub Actions Integration

**Workflow file:** `.github/workflows/security-scan.yml`

```yaml
name: Security Scan
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

permissions:
  contents: read
  security-events: write

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Run Security Pipeline
        run: |
          python -m app.cicd.run_security_pipeline \
            --source-path . \
            --pipeline-id ${{ github.run_id }} \
            --branch ${{ github.ref_name }} \
            --commit ${{ github.sha }} \
            --ci-platform github
```

### SARIF Report Format

```json
{
  "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
  "version": "2.1.0",
  "runs": [
    {
      "tool": {
        "driver": {
          "name": "Advanced Security Scanner",
          "version": "1.0.0"
        }
      },
      "results": [
        {
          "ruleId": "sql_injection_app_py_45",
          "message": {
            "text": "SQL query construction using string formatting may be vulnerable to injection"
          },
          "level": "warning",
          "locations": [
            {
              "physicalLocation": {
                "artifactLocation": {
                  "uri": "app.py"
                },
                "region": {
                  "startLine": 45
                }
              }
            }
          ]
        }
      ]
    }
  ]
}
```

### HTML Report Format

The system generates comprehensive HTML reports with:
- Executive summary with risk assessment
- Vulnerability breakdown by severity
- Security gate status
- Remediation priorities
- Detailed vulnerability listings
- Trend analysis and baseline comparison

## Performance and Scalability

### Optimization Features

**Parallel Scanning**
- Multiple scan types execute concurrently
- Configurable concurrency limits
- Resource-aware execution

**Intelligent Caching**
- Scan result caching for repeated scans
- Baseline comparison optimization
- Pattern matching optimization

**Resource Management**
- Configurable scan timeouts
- Memory usage monitoring
- CPU usage optimization

### Performance Metrics

```python
# Example performance metrics
metrics = {
    "scan_duration_seconds": 127.5,
    "vulnerabilities_per_second": 0.024,
    "files_scanned": 150,
    "lines_of_code_analyzed": 25000,
    "memory_usage_mb": 256,
    "cpu_usage_percent": 45
}
```

## Security Considerations

### Secure Scanning

- Sandboxed execution environment
- No sensitive data exposure in logs
- Secure artifact storage
- Access control for scan results

### Data Privacy

- Minimal data collection
- Anonymized reporting options
- Configurable data retention
- GDPR compliance support

### Audit Trail

- Comprehensive audit logging
- Scan execution tracking
- Change detection and alerting
- Compliance reporting

## Troubleshooting

### Common Issues

**Scan Timeouts**
```bash
# Increase scan timeout
python -m app.cicd.run_security_pipeline \
  --max-scan-duration 120 \
  --source-path .
```

**Memory Issues**
```bash
# Disable parallel scans for large codebases
python -m app.cicd.run_security_pipeline \
  --no-parallel-scans \
  --source-path .
```

**False Positives**
```yaml
# Configure exclusion patterns in security policy
scan_configuration:
  exclude_patterns:
    - "*/test_data/*"
    - "*_test.py"
    - "*/migrations/*"
```

### Debug Mode

```bash
# Enable verbose logging
python -m app.cicd.run_security_pipeline \
  --verbose \
  --log-level DEBUG \
  --source-path .
```

### Support

For issues related to security scanning integration:
1. Check scan logs and debug output
2. Review security policy configuration
3. Verify scan tool availability and versions
4. Test with minimal scan configuration
5. Contact security team for critical issues

The Security Scanning Integration provides comprehensive, automated security scanning capabilities that integrate seamlessly into CI/CD pipelines while maintaining performance and providing actionable security insights.