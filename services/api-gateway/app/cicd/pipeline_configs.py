"""
CI/CD Pipeline Configuration Generator
Generate pipeline configurations for different CI/CD platforms (GitHub Actions, Azure DevOps, GitLab CI)
"""
try:
    import yaml
except ImportError:
    yaml = None
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

try:
    from shared.monitoring.structured_logger import StructuredLogger
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger


class PipelinePlatform(str, Enum):
    """Supported CI/CD platforms"""
    GITHUB_ACTIONS = "github_actions"
    AZURE_DEVOPS = "azure_devops"
    GITLAB_CI = "gitlab_ci"
    JENKINS = "jenkins"


class SecurityScanTool(str, Enum):
    """Security scanning tools"""
    BANDIT = "bandit"           # Python security linter
    SAFETY = "safety"           # Python dependency scanner
    SEMGREP = "semgrep"         # Static analysis
    TRIVY = "trivy"             # Container and filesystem scanner
    SNYK = "snyk"               # Vulnerability scanner
    CODEQL = "codeql"           # GitHub's semantic code analysis
    SONARQUBE = "sonarqube"     # Code quality and security


@dataclass
class PipelineConfig:
    """Pipeline configuration"""
    platform: PipelinePlatform
    project_name: str
    security_tools: List[SecurityScanTool] = field(default_factory=list)
    python_version: str = "3.11"
    fail_on_critical: bool = True
    fail_on_high: bool = False
    upload_sarif: bool = True
    generate_badges: bool = True
    slack_notifications: bool = False
    email_notifications: bool = False
    custom_commands: List[str] = field(default_factory=list)


class PipelineConfigGenerator:
    """Generate CI/CD pipeline configurations"""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
        
        # Default security tools for each platform
        self.default_tools = {
            PipelinePlatform.GITHUB_ACTIONS: [
                SecurityScanTool.BANDIT,
                SecurityScanTool.SAFETY,
                SecurityScanTool.TRIVY,
                SecurityScanTool.CODEQL
            ],
            PipelinePlatform.AZURE_DEVOPS: [
                SecurityScanTool.BANDIT,
                SecurityScanTool.SAFETY,
                SecurityScanTool.TRIVY,
                SecurityScanTool.SONARQUBE
            ],
            PipelinePlatform.GITLAB_CI: [
                SecurityScanTool.BANDIT,
                SecurityScanTool.SAFETY,
                SecurityScanTool.SEMGREP,
                SecurityScanTool.TRIVY
            ],
            PipelinePlatform.JENKINS: [
                SecurityScanTool.BANDIT,
                SecurityScanTool.SAFETY,
                SecurityScanTool.TRIVY
            ]
        }
    
    def generate_pipeline_config(self, config: PipelineConfig) -> str:
        """Generate pipeline configuration for specified platform"""
        
        self.logger.info("Generating pipeline configuration",
                        platform=config.platform.value,
                        project=config.project_name,
                        tools=[tool.value for tool in config.security_tools])
        
        # Use default tools if none specified
        if not config.security_tools:
            config.security_tools = self.default_tools.get(config.platform, [])
        
        if config.platform == PipelinePlatform.GITHUB_ACTIONS:
            return self._generate_github_actions_config(config)
        elif config.platform == PipelinePlatform.AZURE_DEVOPS:
            return self._generate_azure_devops_config(config)
        elif config.platform == PipelinePlatform.GITLAB_CI:
            return self._generate_gitlab_ci_config(config)
        elif config.platform == PipelinePlatform.JENKINS:
            return self._generate_jenkins_config(config)
        else:
            raise ValueError(f"Unsupported platform: {config.platform}")
    
    def _generate_github_actions_config(self, config: PipelineConfig) -> str:
        """Generate GitHub Actions workflow configuration"""
        
        workflow = {
            "name": f"Security Scan - {config.project_name}",
            "on": {
                "push": {
                    "branches": ["main", "develop", "release/*"]
                },
                "pull_request": {
                    "branches": ["main", "develop"]
                },
                "schedule": [
                    {"cron": "0 2 * * 1"}  # Weekly scan on Mondays at 2 AM
                ]
            },
            "permissions": {
                "contents": "read",
                "security-events": "write",
                "actions": "read"
            },
            "jobs": {
                "security-scan": {
                    "runs-on": "ubuntu-latest",
                    "steps": [
                        {
                            "name": "Checkout code",
                            "uses": "actions/checkout@v4",
                            "with": {
                                "fetch-depth": 0
                            }
                        },
                        {
                            "name": "Set up Python",
                            "uses": "actions/setup-python@v4",
                            "with": {
                                "python-version": config.python_version
                            }
                        },
                        {
                            "name": "Install dependencies",
                            "run": "pip install --upgrade pip && pip install -r requirements.txt || echo 'No requirements.txt found'"
                        }
                    ]
                }
            }
        }
        
        # Add security scanning steps
        steps = workflow["jobs"]["security-scan"]["steps"]
        
        if SecurityScanTool.BANDIT in config.security_tools:
            steps.extend([
                {
                    "name": "Install Bandit",
                    "run": "pip install bandit[toml]"
                },
                {
                    "name": "Run Bandit security scan",
                    "run": "bandit -r . -f json -o bandit-report.json || true"
                },
                {
                    "name": "Upload Bandit results",
                    "uses": "actions/upload-artifact@v3",
                    "with": {
                        "name": "bandit-results",
                        "path": "bandit-report.json"
                    }
                }
            ])
        
        if SecurityScanTool.SAFETY in config.security_tools:
            steps.extend([
                {
                    "name": "Install Safety",
                    "run": "pip install safety"
                },
                {
                    "name": "Run Safety check",
                    "run": "safety check --json --output safety-report.json || true"
                },
                {
                    "name": "Upload Safety results",
                    "uses": "actions/upload-artifact@v3",
                    "with": {
                        "name": "safety-results",
                        "path": "safety-report.json"
                    }
                }
            ])
        
        if SecurityScanTool.TRIVY in config.security_tools:
            steps.extend([
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
                    "name": "Upload Trivy scan results to GitHub Security tab",
                    "uses": "github/codeql-action/upload-sarif@v2",
                    "if": config.upload_sarif,
                    "with": {
                        "sarif_file": "trivy-results.sarif"
                    }
                }
            ])
        
        if SecurityScanTool.CODEQL in config.security_tools:
            steps.extend([
                {
                    "name": "Initialize CodeQL",
                    "uses": "github/codeql-action/init@v2",
                    "with": {
                        "languages": "python"
                    }
                },
                {
                    "name": "Autobuild",
                    "uses": "github/codeql-action/autobuild@v2"
                },
                {
                    "name": "Perform CodeQL Analysis",
                    "uses": "github/codeql-action/analyze@v2"
                }
            ])
        
        # Add custom security pipeline step
        steps.extend([
            {
                "name": "Run Advanced Security Pipeline",
                "run": "python -m app.cicd.run_security_pipeline --source-path . --pipeline-id ${{ github.run_id }} --branch ${{ github.ref_name }} --commit ${{ github.sha }}"
            },
            {
                "name": "Upload Security Reports",
                "uses": "actions/upload-artifact@v3",
                "with": {
                    "name": "security-reports",
                    "path": "security_artifacts/"
                }
            }
        ])
        
        # Add failure handling
        if config.fail_on_critical or config.fail_on_high:
            steps.append({
                "name": "Check Security Gate",
                "run": f"""
                python -c "
                import json
                import sys
                try:
                    with open('security_artifacts/${{{{ github.run_id }}}}/security_report.json', 'r') as f:
                        report = json.load(f)
                    
                    risk = report.get('risk_assessment', {{}})
                    critical = risk.get('severity_breakdown', {{}}).get('critical', 0)
                    high = risk.get('severity_breakdown', {{}}).get('high', 0)
                    
                    {'if critical > 0: sys.exit(1)' if config.fail_on_critical else ''}
                    {'if high > 0: sys.exit(1)' if config.fail_on_high else ''}
                    
                    print(f'Security gate passed: Critical={{critical}}, High={{high}}')
                except Exception as e:
                    print(f'Error checking security gate: {{e}}')
                    sys.exit(1)
                "
                """
            })
        
        # Add notifications
        if config.slack_notifications:
            steps.append({
                "name": "Slack Notification",
                "uses": "8398a7/action-slack@v3",
                "with": {
                    "status": "${{ job.status }}",
                    "channel": "#security",
                    "webhook_url": "${{ secrets.SLACK_WEBHOOK }}"
                },
                "if": "always()"
            })
        
        if yaml:
            return yaml.dump(workflow, default_flow_style=False, sort_keys=False)
        else:
            return json.dumps(workflow, indent=2)
    
    def _generate_azure_devops_config(self, config: PipelineConfig) -> str:
        """Generate Azure DevOps pipeline configuration"""
        
        pipeline = {
            "trigger": {
                "branches": {
                    "include": ["main", "develop", "release/*"]
                }
            },
            "pr": {
                "branches": {
                    "include": ["main", "develop"]
                }
            },
            "schedules": [
                {
                    "cron": "0 2 * * 1",
                    "displayName": "Weekly security scan",
                    "branches": {
                        "include": ["main"]
                    }
                }
            ],
            "pool": {
                "vmImage": "ubuntu-latest"
            },
            "variables": {
                "pythonVersion": config.python_version,
                "projectName": config.project_name
            },
            "stages": [
                {
                    "stage": "SecurityScan",
                    "displayName": "Security Scanning",
                    "jobs": [
                        {
                            "job": "SecurityTests",
                            "displayName": "Run Security Tests",
                            "steps": [
                                {
                                    "task": "UsePythonVersion@0",
                                    "inputs": {
                                        "versionSpec": "$(pythonVersion)"
                                    },
                                    "displayName": "Use Python $(pythonVersion)"
                                },
                                {
                                    "script": "pip install --upgrade pip && pip install -r requirements.txt || echo 'No requirements.txt found'",
                                    "displayName": "Install dependencies"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        # Add security scanning steps
        job_steps = pipeline["stages"][0]["jobs"][0]["steps"]
        
        if SecurityScanTool.BANDIT in config.security_tools:
            job_steps.extend([
                {
                    "script": "pip install bandit[toml]",
                    "displayName": "Install Bandit"
                },
                {
                    "script": "bandit -r . -f json -o $(Agent.TempDirectory)/bandit-report.json || true",
                    "displayName": "Run Bandit security scan"
                },
                {
                    "task": "PublishTestResults@2",
                    "inputs": {
                        "testResultsFiles": "$(Agent.TempDirectory)/bandit-report.json",
                        "testRunTitle": "Bandit Security Scan"
                    },
                    "condition": "always()"
                }
            ])
        
        if SecurityScanTool.TRIVY in config.security_tools:
            job_steps.extend([
                {
                    "script": """
                    sudo apt-get update
                    sudo apt-get install wget apt-transport-https gnupg lsb-release
                    wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | sudo apt-key add -
                    echo "deb https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main" | sudo tee -a /etc/apt/sources.list.d/trivy.list
                    sudo apt-get update
                    sudo apt-get install trivy
                    """,
                    "displayName": "Install Trivy"
                },
                {
                    "script": "trivy fs --format sarif --output $(Agent.TempDirectory)/trivy-results.sarif .",
                    "displayName": "Run Trivy scan"
                }
            ])
        
        if SecurityScanTool.SONARQUBE in config.security_tools:
            job_steps.extend([
                {
                    "task": "SonarQubePrepare@5",
                    "inputs": {
                        "SonarQube": "$(sonarQubeServiceConnection)",
                        "scannerMode": "CLI",
                        "configMode": "manual",
                        "cliProjectKey": "$(projectName)",
                        "cliProjectName": "$(projectName)"
                    }
                },
                {
                    "task": "SonarQubeAnalyze@5"
                },
                {
                    "task": "SonarQubePublish@5",
                    "inputs": {
                        "pollingTimeoutSec": "300"
                    }
                }
            ])
        
        # Add advanced security pipeline
        job_steps.extend([
            {
                "script": "python -m app.cicd.run_security_pipeline --source-path . --pipeline-id $(Build.BuildId) --branch $(Build.SourceBranchName) --commit $(Build.SourceVersion)",
                "displayName": "Run Advanced Security Pipeline"
            },
            {
                "task": "PublishBuildArtifacts@1",
                "inputs": {
                    "PathtoPublish": "security_artifacts/",
                    "ArtifactName": "security-reports"
                },
                "displayName": "Upload Security Reports"
            }
        ])
        
        if yaml:
            return yaml.dump(pipeline, default_flow_style=False, sort_keys=False)
        else:
            return json.dumps(pipeline, indent=2)
    
    def _generate_gitlab_ci_config(self, config: PipelineConfig) -> str:
        """Generate GitLab CI configuration"""
        
        gitlab_ci = {
            "stages": ["test", "security", "deploy"],
            "variables": {
                "PIP_CACHE_DIR": "$CI_PROJECT_DIR/.cache/pip",
                "PYTHON_VERSION": config.python_version
            },
            "cache": {
                "paths": [".cache/pip"]
            },
            "before_script": [
                "python -V",
                "pip install --upgrade pip",
                "pip install -r requirements.txt || echo 'No requirements.txt found'"
            ]
        }
        
        # Security scanning jobs
        if SecurityScanTool.BANDIT in config.security_tools:
            gitlab_ci["bandit_security_scan"] = {
                "stage": "security",
                "image": f"python:{config.python_version}",
                "script": [
                    "pip install bandit[toml]",
                    "bandit -r . -f json -o bandit-report.json || true"
                ],
                "artifacts": {
                    "reports": {
                        "sast": "bandit-report.json"
                    },
                    "expire_in": "1 week"
                },
                "allow_failure": not config.fail_on_high
            }
        
        if SecurityScanTool.SAFETY in config.security_tools:
            gitlab_ci["safety_check"] = {
                "stage": "security",
                "image": f"python:{config.python_version}",
                "script": [
                    "pip install safety",
                    "safety check --json --output safety-report.json || true"
                ],
                "artifacts": {
                    "reports": {
                        "dependency_scanning": "safety-report.json"
                    },
                    "expire_in": "1 week"
                },
                "allow_failure": not config.fail_on_critical
            }
        
        if SecurityScanTool.SEMGREP in config.security_tools:
            gitlab_ci["semgrep_scan"] = {
                "stage": "security",
                "image": "returntocorp/semgrep",
                "script": [
                    "semgrep --config=auto --json --output=semgrep-report.json . || true"
                ],
                "artifacts": {
                    "reports": {
                        "sast": "semgrep-report.json"
                    },
                    "expire_in": "1 week"
                },
                "allow_failure": not config.fail_on_high
            }
        
        if SecurityScanTool.TRIVY in config.security_tools:
            gitlab_ci["trivy_scan"] = {
                "stage": "security",
                "image": "aquasec/trivy:latest",
                "script": [
                    "trivy fs --format json --output trivy-report.json . || true"
                ],
                "artifacts": {
                    "reports": {
                        "container_scanning": "trivy-report.json"
                    },
                    "expire_in": "1 week"
                },
                "allow_failure": not config.fail_on_critical
            }
        
        # Advanced security pipeline job
        gitlab_ci["advanced_security_scan"] = {
            "stage": "security",
            "image": f"python:{config.python_version}",
            "script": [
                "python -m app.cicd.run_security_pipeline --source-path . --pipeline-id $CI_PIPELINE_ID --branch $CI_COMMIT_REF_NAME --commit $CI_COMMIT_SHA"
            ],
            "artifacts": {
                "paths": ["security_artifacts/"],
                "expire_in": "1 week"
            },
            "allow_failure": not (config.fail_on_critical or config.fail_on_high)
        }
        
        if yaml:
            return yaml.dump(gitlab_ci, default_flow_style=False, sort_keys=False)
        else:
            return json.dumps(gitlab_ci, indent=2)
    
    def _generate_jenkins_config(self, config: PipelineConfig) -> str:
        """Generate Jenkins pipeline configuration (Jenkinsfile)"""
        
        jenkinsfile = f'''
pipeline {{
    agent any
    
    environment {{
        PYTHON_VERSION = '{config.python_version}'
        PROJECT_NAME = '{config.project_name}'
    }}
    
    triggers {{
        cron('H 2 * * 1') // Weekly scan on Mondays
    }}
    
    stages {{
        stage('Checkout') {{
            steps {{
                checkout scm
            }}
        }}
        
        stage('Setup') {{
            steps {{
                sh '''
                python${{PYTHON_VERSION}} -m venv venv
                . venv/bin/activate
                pip install --upgrade pip
                pip install -r requirements.txt || echo "No requirements.txt found"
                '''
            }}
        }}
        
        stage('Security Scanning') {{
            parallel {{
'''
        
        # Add security scanning stages
        if SecurityScanTool.BANDIT in config.security_tools:
            jenkinsfile += '''
                stage('Bandit Scan') {
                    steps {
                        sh '''
                        . venv/bin/activate
                        pip install bandit[toml]
                        bandit -r . -f json -o bandit-report.json || true
                        '''
                        publishHTML([
                            allowMissing: false,
                            alwaysLinkToLastBuild: true,
                            keepAll: true,
                            reportDir: '.',
                            reportFiles: 'bandit-report.json',
                            reportName: 'Bandit Security Report'
                        ])
                    }
                }
'''
        
        if SecurityScanTool.SAFETY in config.security_tools:
            jenkinsfile += '''
                stage('Safety Check') {
                    steps {
                        sh '''
                        . venv/bin/activate
                        pip install safety
                        safety check --json --output safety-report.json || true
                        '''
                        archiveArtifacts artifacts: 'safety-report.json', fingerprint: true
                    }
                }
'''
        
        if SecurityScanTool.TRIVY in config.security_tools:
            jenkinsfile += '''
                stage('Trivy Scan') {
                    steps {
                        sh '''
                        curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin
                        trivy fs --format json --output trivy-report.json . || true
                        '''
                        archiveArtifacts artifacts: 'trivy-report.json', fingerprint: true
                    }
                }
'''
        
        jenkinsfile += '''
                stage('Advanced Security Pipeline') {
                    steps {
                        sh '''
                        . venv/bin/activate
                        python -m app.cicd.run_security_pipeline --source-path . --pipeline-id ${BUILD_ID} --branch ${BRANCH_NAME} --commit ${GIT_COMMIT}
                        '''
                        archiveArtifacts artifacts: 'security_artifacts/**/*', fingerprint: true
                    }
                }
            }
        }
'''
        
        # Add post-build actions
        jenkinsfile += '''
        stage('Security Gate') {
            steps {
                script {
                    def report = readJSON file: "security_artifacts/${BUILD_ID}/security_report.json"
                    def critical = report.risk_assessment.severity_breakdown.critical ?: 0
                    def high = report.risk_assessment.severity_breakdown.high ?: 0
                    
                    echo "Security scan results: Critical=${critical}, High=${high}"
                    
'''
        
        if config.fail_on_critical:
            jenkinsfile += '''
                    if (critical > 0) {
                        error("Security gate failed: ${critical} critical vulnerabilities found")
                    }
'''
        
        if config.fail_on_high:
            jenkinsfile += '''
                    if (high > 0) {
                        error("Security gate failed: ${high} high severity vulnerabilities found")
                    }
'''
        
        jenkinsfile += '''
                }
            }
        }
    }
    
    post {
        always {
            cleanWs()
        }
        failure {
'''
        
        if config.email_notifications:
            jenkinsfile += '''
            emailext (
                subject: "Security Scan Failed: ${env.JOB_NAME} - ${env.BUILD_NUMBER}",
                body: "The security scan for ${env.JOB_NAME} build ${env.BUILD_NUMBER} has failed. Please check the console output for details.",
                to: "${env.CHANGE_AUTHOR_EMAIL}"
            )
'''
        
        jenkinsfile += '''
        }
    }
}
'''
        
        return jenkinsfile.strip()
    
    def generate_all_configs(self, base_config: PipelineConfig, output_dir: Path):
        """Generate configurations for all supported platforms"""
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for platform in PipelinePlatform:
            try:
                # Create platform-specific config
                platform_config = PipelineConfig(
                    platform=platform,
                    project_name=base_config.project_name,
                    security_tools=base_config.security_tools or self.default_tools.get(platform, []),
                    python_version=base_config.python_version,
                    fail_on_critical=base_config.fail_on_critical,
                    fail_on_high=base_config.fail_on_high,
                    upload_sarif=base_config.upload_sarif,
                    generate_badges=base_config.generate_badges,
                    slack_notifications=base_config.slack_notifications,
                    email_notifications=base_config.email_notifications
                )
                
                # Generate configuration
                config_content = self.generate_pipeline_config(platform_config)
                
                # Determine filename and extension
                if platform == PipelinePlatform.GITHUB_ACTIONS:
                    filename = "security-scan.yml"
                    subdir = ".github/workflows"
                elif platform == PipelinePlatform.AZURE_DEVOPS:
                    filename = "azure-pipelines-security.yml"
                    subdir = ".azure"
                elif platform == PipelinePlatform.GITLAB_CI:
                    filename = ".gitlab-ci-security.yml"
                    subdir = ""
                elif platform == PipelinePlatform.JENKINS:
                    filename = "Jenkinsfile.security"
                    subdir = "jenkins"
                
                # Create subdirectory if needed
                if subdir:
                    platform_dir = output_dir / subdir
                    platform_dir.mkdir(parents=True, exist_ok=True)
                    config_path = platform_dir / filename
                else:
                    config_path = output_dir / filename
                
                # Write configuration file
                with open(config_path, 'w') as f:
                    f.write(config_content)
                
                self.logger.info("Generated pipeline configuration",
                               platform=platform.value,
                               file_path=str(config_path))
                
            except Exception as e:
                self.logger.error("Failed to generate pipeline configuration",
                                platform=platform.value,
                                error=str(e))
    
    def generate_security_policy_template(self, output_path: Path):
        """Generate security policy template"""
        
        security_policy = {
            "security_policy": {
                "version": "1.0",
                "description": "Security scanning and compliance policy",
                "scan_configuration": {
                    "enabled_scan_types": [
                        "static_analysis",
                        "secrets_detection", 
                        "software_composition",
                        "container_security",
                        "infrastructure_security",
                        "compliance_check"
                    ],
                    "max_scan_duration_minutes": 60,
                    "parallel_scans": True,
                    "fail_on_critical": True,
                    "fail_on_high": False,
                    "exclude_patterns": [
                        "*/node_modules/*",
                        "*/venv/*",
                        "*/build/*",
                        "*/dist/*",
                        "*/.git/*",
                        "*/test_data/*",
                        "*/migrations/*"
                    ],
                    "include_patterns": [
                        "**/*.py",
                        "**/*.js",
                        "**/*.ts",
                        "**/*.yml",
                        "**/*.yaml",
                        "**/Dockerfile*",
                        "**/requirements*.txt"
                    ]
                },
                "security_gates": [
                    {
                        "name": "build_security_gate",
                        "stage": "build",
                        "scan_types": ["static_analysis", "secrets_detection"],
                        "max_critical": 0,
                        "max_high": 2,
                        "max_medium": 10,
                        "blocking": True
                    },
                    {
                        "name": "dependency_security_gate", 
                        "stage": "test",
                        "scan_types": ["software_composition"],
                        "max_critical": 0,
                        "max_high": 5,
                        "blocking": True
                    },
                    {
                        "name": "production_readiness_gate",
                        "stage": "deploy",
                        "scan_types": ["static_analysis", "secrets_detection", "software_composition", "container_security"],
                        "max_critical": 0,
                        "max_high": 0,
                        "max_medium": 5,
                        "compliance_required": ["OWASP", "CIS"],
                        "blocking": True
                    }
                ],
                "compliance_frameworks": ["OWASP", "CIS", "NIST"],
                "notification_settings": {
                    "slack_webhook": "${SLACK_WEBHOOK_URL}",
                    "email_recipients": ["security-team@company.com"],
                    "notify_on_failure": True,
                    "notify_on_new_vulnerabilities": True
                },
                "remediation_settings": {
                    "auto_remediation": False,
                    "create_issues": True,
                    "assign_to": "security-team"
                }
            }
        }
        
        with open(output_path, 'w') as f:
            if yaml:
                yaml.dump(security_policy, f, default_flow_style=False, sort_keys=False)
            else:
                json.dump(security_policy, f, indent=2)
        
        self.logger.info("Generated security policy template", file_path=str(output_path))
    
    def generate_dockerfile_security_config(self, output_path: Path):
        """Generate Dockerfile with security scanning tools"""
        
        dockerfile_content = f"""
# Security Scanner Dockerfile
FROM python:{self.default_tools.get(PipelinePlatform.GITHUB_ACTIONS, [])[0] if self.default_tools else '3.11'}-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    curl \\
    wget \\
    git \\
    && rm -rf /var/lib/apt/lists/*

# Install Trivy
RUN curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin

# Install Python security tools
RUN pip install --no-cache-dir \\
    bandit[toml] \\
    safety \\
    semgrep \\
    pip-audit

# Create non-root user
RUN useradd --create-home --shell /bin/bash scanner
USER scanner
WORKDIR /home/scanner

# Copy application code
COPY --chown=scanner:scanner . .

# Install Python dependencies
RUN pip install --user -r requirements.txt || echo "No requirements.txt found"

# Default command
CMD ["python", "-m", "app.cicd.run_security_pipeline", "--source-path", ".", "--pipeline-id", "local-scan"]
"""
        
        with open(output_path, 'w') as f:
            f.write(dockerfile_content.strip())
        
        self.logger.info("Generated security scanner Dockerfile", file_path=str(output_path))
    
    def generate_docker_compose_config(self, output_path: Path):
        """Generate Docker Compose configuration for security scanning"""
        
        compose_config = {
            "version": "3.8",
            "services": {
                "security-scanner": {
                    "build": {
                        "context": ".",
                        "dockerfile": "Dockerfile.security"
                    },
                    "volumes": [
                        ".:/home/scanner",
                        "/var/run/docker.sock:/var/run/docker.sock"
                    ],
                    "environment": [
                        "SCANNER_CONFIG_FILE=/home/scanner/security-policy.yml"
                    ],
                    "networks": ["security-network"]
                },
                "redis": {
                    "image": "redis:7-alpine",
                    "networks": ["security-network"],
                    "volumes": ["redis-data:/data"]
                }
            },
            "networks": {
                "security-network": {
                    "driver": "bridge"
                }
            },
            "volumes": {
                "redis-data": {}
            }
        }
        
        with open(output_path, 'w') as f:
            if yaml:
                yaml.dump(compose_config, f, default_flow_style=False, sort_keys=False)
            else:
                json.dump(compose_config, f, indent=2)
        
        self.logger.info("Generated Docker Compose configuration", file_path=str(output_path))