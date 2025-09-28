"""
CI/CD Security Pipeline Integration
Automated security scanning integration for continuous integration and deployment pipelines
"""
import asyncio
import json
import os
import shutil
import tempfile
import zipfile
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

from app.security.vulnerability_scanner import (
    AdvancedVulnerabilityScanner, ScanConfiguration, ScanType, 
    VulnerabilitySeverity, ScanResult
)
try:
    from shared.monitoring.structured_logger import StructuredLogger
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger


class PipelineStage(str, Enum):
    """CI/CD pipeline stages"""
    BUILD = "build"
    TEST = "test"
    SECURITY_SCAN = "security_scan"
    DEPLOY = "deploy"
    POST_DEPLOY = "post_deploy"


class DeploymentEnvironment(str, Enum):
    """Deployment environments"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class PipelineConfiguration:
    """Pipeline security configuration"""
    enabled_stages: List[PipelineStage] = field(default_factory=lambda: list(PipelineStage))
    scan_configuration: ScanConfiguration = field(default_factory=ScanConfiguration)
    fail_pipeline_on_critical: bool = True
    fail_pipeline_on_high: bool = False
    generate_reports: bool = True
    upload_results: bool = True
    notify_on_failure: bool = True
    baseline_comparison: bool = True
    auto_remediation: bool = False
    compliance_gates: List[str] = field(default_factory=lambda: ["OWASP", "CIS"])


@dataclass 
class PipelineContext:
    """Pipeline execution context"""
    pipeline_id: str
    commit_sha: str
    branch_name: str
    repository_url: str
    environment: DeploymentEnvironment
    triggered_by: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SecurityGate:
    """Security gate definition"""
    name: str
    stage: PipelineStage
    scan_types: List[ScanType]
    max_critical: int = 0
    max_high: int = 0
    max_medium: int = -1  # -1 means no limit
    compliance_required: List[str] = field(default_factory=list)
    blocking: bool = True


@dataclass
class PipelineResult:
    """Pipeline security scan result"""
    pipeline_id: str
    context: PipelineContext
    security_gates: List[SecurityGate]
    scan_results: Dict[str, ScanResult]
    gate_results: Dict[str, bool]
    overall_status: str
    risk_assessment: Dict[str, Any]
    remediation_report: Dict[str, Any]
    artifacts: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class SecurityPipelineIntegration:
    """Security pipeline integration for CI/CD"""
    
    def __init__(self, logger: StructuredLogger, config: PipelineConfiguration = None):
        self.logger = logger
        self.config = config or PipelineConfiguration()
        
        # Initialize vulnerability scanner
        self.scanner = AdvancedVulnerabilityScanner(
            logger=logger,
            config=self.config.scan_configuration
        )
        
        # Security gates configuration
        self.security_gates = self._initialize_security_gates()
        
        # Pipeline history
        self.pipeline_history: Dict[str, PipelineResult] = {}
        
        # Baseline configurations
        self.security_baselines: Dict[str, Dict[str, Any]] = {}
        
        self.logger.info("Security pipeline integration initialized",
                        enabled_stages=[stage.value for stage in self.config.enabled_stages])
    
    async def execute_security_pipeline(
        self,
        source_path: str,
        context: PipelineContext
    ) -> PipelineResult:
        """Execute complete security pipeline"""
        
        start_time = datetime.utcnow()
        
        self.logger.info("Starting security pipeline execution",
                        pipeline_id=context.pipeline_id,
                        branch=context.branch_name,
                        environment=context.environment.value)
        
        try:
            # Initialize pipeline result
            pipeline_result = PipelineResult(
                pipeline_id=context.pipeline_id,
                context=context,
                security_gates=self.security_gates,
                scan_results={},
                gate_results={},
                overall_status="RUNNING",
                risk_assessment={},
                remediation_report={}
            )
            
            # Execute security gates
            gate_success = True
            
            for gate in self.security_gates:
                if gate.stage in self.config.enabled_stages:
                    gate_result = await self._execute_security_gate(
                        gate, source_path, context, pipeline_result
                    )
                    
                    pipeline_result.gate_results[gate.name] = gate_result
                    
                    if not gate_result and gate.blocking:
                        gate_success = False
                        self.logger.error("Security gate failed",
                                        gate_name=gate.name,
                                        pipeline_id=context.pipeline_id)
                        
                        if self.config.fail_pipeline_on_critical:
                            break
            
            # Generate comprehensive report
            pipeline_result.risk_assessment = self._assess_pipeline_risk(pipeline_result)
            pipeline_result.remediation_report = self._generate_remediation_report(pipeline_result)
            
            # Set overall status
            pipeline_result.overall_status = "PASSED" if gate_success else "FAILED"
            
            # Calculate duration
            end_time = datetime.utcnow()
            pipeline_result.duration_seconds = (end_time - start_time).total_seconds()
            
            # Store pipeline result
            self.pipeline_history[context.pipeline_id] = pipeline_result
            
            # Generate artifacts
            if self.config.generate_reports:
                artifacts = await self._generate_pipeline_artifacts(pipeline_result, source_path)
                pipeline_result.artifacts = artifacts
            
            # Baseline comparison
            if self.config.baseline_comparison:
                baseline_comparison = await self._compare_with_baseline(pipeline_result, context)
                pipeline_result.metadata["baseline_comparison"] = baseline_comparison
            
            # Auto-remediation
            if self.config.auto_remediation and pipeline_result.overall_status == "FAILED":
                remediation_results = await self._attempt_auto_remediation(pipeline_result, source_path)
                pipeline_result.metadata["auto_remediation"] = remediation_results
            
            self.logger.info("Security pipeline execution completed",
                           pipeline_id=context.pipeline_id,
                           status=pipeline_result.overall_status,
                           duration_seconds=pipeline_result.duration_seconds,
                           gates_passed=sum(1 for passed in pipeline_result.gate_results.values() if passed),
                           total_gates=len(pipeline_result.gate_results))
            
            return pipeline_result
            
        except Exception as e:
            self.logger.error("Security pipeline execution failed",
                            pipeline_id=context.pipeline_id,
                            error=str(e))
            
            # Create error result
            error_result = PipelineResult(
                pipeline_id=context.pipeline_id,
                context=context,
                security_gates=self.security_gates,
                scan_results={},
                gate_results={},
                overall_status="ERROR",
                risk_assessment={},
                remediation_report={},
                duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
                metadata={"error": str(e)}
            )
            
            return error_result
    
    async def _execute_security_gate(
        self,
        gate: SecurityGate,
        source_path: str,
        context: PipelineContext,
        pipeline_result: PipelineResult
    ) -> bool:
        """Execute a specific security gate"""
        
        self.logger.info("Executing security gate",
                        gate_name=gate.name,
                        stage=gate.stage.value,
                        scan_types=[st.value for st in gate.scan_types])
        
        try:
            # Run scans for this gate
            scan_results = await self.scanner.scan_application(
                source_path, 
                set(gate.scan_types)
            )
            
            # Store scan results
            for scan_type, result in scan_results.items():
                pipeline_result.scan_results[f"{gate.name}_{scan_type.value}"] = result
            
            # Evaluate gate criteria
            gate_passed = self._evaluate_gate_criteria(gate, scan_results)
            
            self.logger.info("Security gate evaluation completed",
                           gate_name=gate.name,
                           passed=gate_passed,
                           total_vulnerabilities=sum(len(r.vulnerabilities) for r in scan_results.values()))
            
            return gate_passed
            
        except Exception as e:
            self.logger.error("Security gate execution failed",
                            gate_name=gate.name,
                            error=str(e))
            return False
    
    def _evaluate_gate_criteria(
        self,
        gate: SecurityGate,
        scan_results: Dict[ScanType, ScanResult]
    ) -> bool:
        """Evaluate if gate criteria are met"""
        
        # Count vulnerabilities by severity
        critical_count = 0
        high_count = 0
        medium_count = 0
        
        for result in scan_results.values():
            critical_count += result.critical_count
            high_count += result.high_count
            medium_count += len([v for v in result.vulnerabilities 
                               if v.severity == VulnerabilitySeverity.MEDIUM])
        
        # Check severity limits
        if critical_count > gate.max_critical:
            self.logger.warning("Security gate failed: too many critical vulnerabilities",
                              gate_name=gate.name,
                              critical_count=critical_count,
                              max_allowed=gate.max_critical)
            return False
        
        if high_count > gate.max_high:
            self.logger.warning("Security gate failed: too many high severity vulnerabilities",
                              gate_name=gate.name,
                              high_count=high_count,
                              max_allowed=gate.max_high)
            return False
        
        if gate.max_medium >= 0 and medium_count > gate.max_medium:
            self.logger.warning("Security gate failed: too many medium severity vulnerabilities",
                              gate_name=gate.name,
                              medium_count=medium_count,
                              max_allowed=gate.max_medium)
            return False
        
        # Check compliance requirements
        for compliance_requirement in gate.compliance_required:
            compliance_violations = []
            for result in scan_results.values():
                if result.scan_type == ScanType.COMPLIANCE:
                    compliance_violations.extend([
                        v for v in result.vulnerabilities
                        if v.metadata.get("framework") == compliance_requirement
                    ])
            
            if compliance_violations:
                self.logger.warning("Security gate failed: compliance violations",
                                  gate_name=gate.name,
                                  framework=compliance_requirement,
                                  violations=len(compliance_violations))
                return False
        
        return True
    
    def _initialize_security_gates(self) -> List[SecurityGate]:
        """Initialize default security gates"""
        return [
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
                name="dependency_security_scan",
                stage=PipelineStage.TEST,
                scan_types=[ScanType.SCA],
                max_critical=0,
                max_high=5,
                max_medium=-1,
                blocking=True
            ),
            SecurityGate(
                name="container_security_scan",
                stage=PipelineStage.SECURITY_SCAN,
                scan_types=[ScanType.CONTAINER],
                max_critical=0,
                max_high=3,
                max_medium=10,
                blocking=True
            ),
            SecurityGate(
                name="infrastructure_security_scan",
                stage=PipelineStage.SECURITY_SCAN,
                scan_types=[ScanType.INFRASTRUCTURE],
                max_critical=0,
                max_high=2,
                max_medium=5,
                blocking=True
            ),
            SecurityGate(
                name="compliance_check",
                stage=PipelineStage.SECURITY_SCAN,
                scan_types=[ScanType.COMPLIANCE],
                max_critical=0,
                max_high=0,
                compliance_required=["OWASP"],
                blocking=False  # Non-blocking for initial implementation
            ),
            SecurityGate(
                name="production_readiness_scan",
                stage=PipelineStage.DEPLOY,
                scan_types=[ScanType.SAST, ScanType.SECRETS, ScanType.SCA, ScanType.CONTAINER],
                max_critical=0,
                max_high=0,
                max_medium=5,
                compliance_required=["OWASP", "CIS"],
                blocking=True
            )
        ]
    
    def _assess_pipeline_risk(self, pipeline_result: PipelineResult) -> Dict[str, Any]:
        """Assess overall pipeline security risk"""
        
        all_vulnerabilities = []
        for result in pipeline_result.scan_results.values():
            all_vulnerabilities.extend(result.vulnerabilities)
        
        # Risk scoring
        severity_weights = {
            VulnerabilitySeverity.CRITICAL: 10.0,
            VulnerabilitySeverity.HIGH: 7.0,
            VulnerabilitySeverity.MEDIUM: 4.0,
            VulnerabilitySeverity.LOW: 1.0,
            VulnerabilitySeverity.INFO: 0.1
        }
        
        risk_score = sum(severity_weights.get(v.severity, 0) for v in all_vulnerabilities)
        risk_score = min(risk_score, 100.0)  # Cap at 100
        
        # Risk categorization
        if risk_score >= 80:
            risk_level = "CRITICAL"
        elif risk_score >= 60:
            risk_level = "HIGH"
        elif risk_score >= 30:
            risk_level = "MEDIUM"
        elif risk_score > 0:
            risk_level = "LOW"
        else:
            risk_level = "MINIMAL"
        
        # Deployment recommendation
        deployment_recommendation = "BLOCK" if risk_level in ["CRITICAL", "HIGH"] else "ALLOW"
        
        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "deployment_recommendation": deployment_recommendation,
            "total_vulnerabilities": len(all_vulnerabilities),
            "severity_breakdown": {
                "critical": len([v for v in all_vulnerabilities if v.severity == VulnerabilitySeverity.CRITICAL]),
                "high": len([v for v in all_vulnerabilities if v.severity == VulnerabilitySeverity.HIGH]),
                "medium": len([v for v in all_vulnerabilities if v.severity == VulnerabilitySeverity.MEDIUM]),
                "low": len([v for v in all_vulnerabilities if v.severity == VulnerabilitySeverity.LOW]),
                "info": len([v for v in all_vulnerabilities if v.severity == VulnerabilitySeverity.INFO])
            },
            "gates_status": {
                "total": len(pipeline_result.gate_results),
                "passed": sum(1 for passed in pipeline_result.gate_results.values() if passed),
                "failed": sum(1 for passed in pipeline_result.gate_results.values() if not passed)
            }
        }
    
    def _generate_remediation_report(self, pipeline_result: PipelineResult) -> Dict[str, Any]:
        """Generate comprehensive remediation report"""
        
        all_vulnerabilities = []
        for result in pipeline_result.scan_results.values():
            all_vulnerabilities.extend(result.vulnerabilities)
        
        # Group vulnerabilities by type and priority
        remediation_items = {}
        
        for vuln in all_vulnerabilities:
            key = f"{vuln.scan_type.value}_{vuln.title}"
            if key not in remediation_items:
                remediation_items[key] = {
                    "title": vuln.title,
                    "scan_type": vuln.scan_type.value,
                    "severity": vuln.severity.value,
                    "count": 0,
                    "files": set(),
                    "remediation": vuln.remediation,
                    "priority_score": 0
                }
            
            remediation_items[key]["count"] += 1
            if vuln.file_path:
                remediation_items[key]["files"].add(vuln.file_path)
            
            # Calculate priority score
            severity_scores = {
                VulnerabilitySeverity.CRITICAL: 10,
                VulnerabilitySeverity.HIGH: 7,
                VulnerabilitySeverity.MEDIUM: 4,
                VulnerabilitySeverity.LOW: 1,
                VulnerabilitySeverity.INFO: 0.1
            }
            remediation_items[key]["priority_score"] += severity_scores.get(vuln.severity, 0)
        
        # Convert sets to lists for JSON serialization
        for item in remediation_items.values():
            item["files"] = list(item["files"])
        
        # Sort by priority score
        sorted_items = sorted(
            remediation_items.values(),
            key=lambda x: x["priority_score"],
            reverse=True
        )
        
        return {
            "total_items": len(sorted_items),
            "high_priority_items": len([item for item in sorted_items if item["priority_score"] >= 7]),
            "remediation_items": sorted_items[:20],  # Top 20 items
            "estimated_effort_hours": self._estimate_remediation_effort(sorted_items),
            "quick_wins": [item for item in sorted_items if item["count"] > 5 and item["severity"] in ["medium", "low"]][:10]
        }
    
    def _estimate_remediation_effort(self, remediation_items: List[Dict[str, Any]]) -> float:
        """Estimate remediation effort in hours"""
        
        effort_estimates = {
            "critical": 4.0,  # hours per vulnerability
            "high": 2.0,
            "medium": 1.0,
            "low": 0.5,
            "info": 0.1
        }
        
        total_effort = 0.0
        for item in remediation_items:
            effort_per_item = effort_estimates.get(item["severity"], 1.0)
            total_effort += effort_per_item * item["count"]
        
        return round(total_effort, 1)
    
    async def _generate_pipeline_artifacts(
        self,
        pipeline_result: PipelineResult,
        source_path: str
    ) -> List[str]:
        """Generate pipeline artifacts (reports, logs, etc.)"""
        
        artifacts = []
        
        try:
            # Create artifacts directory
            artifacts_dir = Path(source_path) / "security_artifacts" / pipeline_result.pipeline_id
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate JSON report
            json_report_path = artifacts_dir / "security_report.json"
            with open(json_report_path, 'w') as f:
                json.dump(self._create_json_report(pipeline_result), f, indent=2, default=str)
            artifacts.append(str(json_report_path))
            
            # Generate HTML report
            html_report_path = artifacts_dir / "security_report.html"
            with open(html_report_path, 'w') as f:
                f.write(self._create_html_report(pipeline_result))
            artifacts.append(str(html_report_path))
            
            # Generate SARIF report (for GitHub/Azure DevOps integration)
            sarif_report_path = artifacts_dir / "security_report.sarif"
            with open(sarif_report_path, 'w') as f:
                json.dump(self._create_sarif_report(pipeline_result), f, indent=2)
            artifacts.append(str(sarif_report_path))
            
            # Generate CSV report for spreadsheet analysis
            csv_report_path = artifacts_dir / "vulnerabilities.csv"
            self._create_csv_report(pipeline_result, csv_report_path)
            artifacts.append(str(csv_report_path))
            
            self.logger.info("Pipeline artifacts generated",
                           pipeline_id=pipeline_result.pipeline_id,
                           artifacts_count=len(artifacts))
            
        except Exception as e:
            self.logger.error("Failed to generate pipeline artifacts",
                            pipeline_id=pipeline_result.pipeline_id,
                            error=str(e))
        
        return artifacts
    
    def _create_json_report(self, pipeline_result: PipelineResult) -> Dict[str, Any]:
        """Create comprehensive JSON report"""
        
        return {
            "pipeline_metadata": {
                "pipeline_id": pipeline_result.pipeline_id,
                "commit_sha": pipeline_result.context.commit_sha,
                "branch_name": pipeline_result.context.branch_name,
                "environment": pipeline_result.context.environment.value,
                "timestamp": pipeline_result.context.timestamp.isoformat(),
                "duration_seconds": pipeline_result.duration_seconds,
                "overall_status": pipeline_result.overall_status
            },
            "risk_assessment": pipeline_result.risk_assessment,
            "security_gates": [
                {
                    "name": gate.name,
                    "stage": gate.stage.value,
                    "scan_types": [st.value for st in gate.scan_types],
                    "passed": pipeline_result.gate_results.get(gate.name, False),
                    "blocking": gate.blocking
                }
                for gate in pipeline_result.security_gates
            ],
            "scan_results": {
                scan_name: {
                    "scan_type": result.scan_type.value,
                    "vulnerabilities_count": len(result.vulnerabilities),
                    "critical_count": result.critical_count,
                    "high_count": result.high_count,
                    "duration_seconds": result.duration_seconds,
                    "status": result.status
                }
                for scan_name, result in pipeline_result.scan_results.items()
            },
            "vulnerabilities": [
                {
                    "id": vuln.id,
                    "title": vuln.title,
                    "severity": vuln.severity.value,
                    "scan_type": vuln.scan_type.value,
                    "file_path": vuln.file_path,
                    "line_number": vuln.line_number,
                    "description": vuln.description,
                    "remediation": vuln.remediation,
                    "cwe_id": vuln.cwe_id,
                    "cve_id": vuln.cve_id
                }
                for result in pipeline_result.scan_results.values()
                for vuln in result.vulnerabilities
            ],
            "remediation_report": pipeline_result.remediation_report,
            "artifacts": pipeline_result.artifacts,
            "metadata": pipeline_result.metadata
        }
    
    def _create_html_report(self, pipeline_result: PipelineResult) -> str:
        """Create HTML report for human consumption"""
        
        # Simple HTML template
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Security Pipeline Report - {pipeline_id}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f4f4f4; padding: 20px; border-radius: 5px; }}
                .status-pass {{ color: green; font-weight: bold; }}
                .status-fail {{ color: red; font-weight: bold; }}
                .severity-critical {{ color: #d32f2f; font-weight: bold; }}
                .severity-high {{ color: #f57c00; font-weight: bold; }}
                .severity-medium {{ color: #ffa000; }}
                .severity-low {{ color: #388e3c; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Security Pipeline Report</h1>
                <p><strong>Pipeline ID:</strong> {pipeline_id}</p>
                <p><strong>Branch:</strong> {branch_name}</p>
                <p><strong>Environment:</strong> {environment}</p>
                <p><strong>Status:</strong> <span class="status-{status_class}">{overall_status}</span></p>
                <p><strong>Risk Level:</strong> {risk_level}</p>
            </div>
            
            <h2>Summary</h2>
            <table>
                <tr><th>Metric</th><th>Count</th></tr>
                <tr><td>Total Vulnerabilities</td><td>{total_vulnerabilities}</td></tr>
                <tr><td>Critical</td><td><span class="severity-critical">{critical_count}</span></td></tr>
                <tr><td>High</td><td><span class="severity-high">{high_count}</span></td></tr>
                <tr><td>Medium</td><td><span class="severity-medium">{medium_count}</span></td></tr>
                <tr><td>Low</td><td><span class="severity-low">{low_count}</span></td></tr>
            </table>
            
            <h2>Security Gates</h2>
            <table>
                <tr><th>Gate Name</th><th>Stage</th><th>Status</th><th>Blocking</th></tr>
                {gates_table}
            </table>
            
            <h2>Top Remediation Items</h2>
            <table>
                <tr><th>Title</th><th>Severity</th><th>Count</th><th>Priority Score</th></tr>
                {remediation_table}
            </table>
        </body>
        </html>
        """
        
        # Prepare data
        risk_assessment = pipeline_result.risk_assessment
        remediation_report = pipeline_result.remediation_report
        
        # Gates table
        gates_rows = ""
        for gate in pipeline_result.security_gates:
            status = "PASS" if pipeline_result.gate_results.get(gate.name, False) else "FAIL"
            status_class = "pass" if status == "PASS" else "fail"
            gates_rows += f"<tr><td>{gate.name}</td><td>{gate.stage.value}</td><td><span class='status-{status_class}'>{status}</span></td><td>{'Yes' if gate.blocking else 'No'}</td></tr>"
        
        # Remediation table
        remediation_rows = ""
        for item in remediation_report.get("remediation_items", [])[:10]:
            remediation_rows += f"<tr><td>{item['title']}</td><td><span class='severity-{item['severity']}'>{item['severity'].upper()}</span></td><td>{item['count']}</td><td>{item['priority_score']:.1f}</td></tr>"
        
        return html_template.format(
            pipeline_id=pipeline_result.pipeline_id,
            branch_name=pipeline_result.context.branch_name,
            environment=pipeline_result.context.environment.value,
            overall_status=pipeline_result.overall_status,
            status_class="pass" if pipeline_result.overall_status == "PASSED" else "fail",
            risk_level=risk_assessment.get("risk_level", "UNKNOWN"),
            total_vulnerabilities=risk_assessment.get("total_vulnerabilities", 0),
            critical_count=risk_assessment.get("severity_breakdown", {}).get("critical", 0),
            high_count=risk_assessment.get("severity_breakdown", {}).get("high", 0),
            medium_count=risk_assessment.get("severity_breakdown", {}).get("medium", 0),
            low_count=risk_assessment.get("severity_breakdown", {}).get("low", 0),
            gates_table=gates_rows,
            remediation_table=remediation_rows
        )
    
    def _create_sarif_report(self, pipeline_result: PipelineResult) -> Dict[str, Any]:
        """Create SARIF format report for tool integration"""
        
        # SARIF 2.1.0 format
        sarif_report = {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "Advanced Security Scanner",
                            "version": "1.0.0",
                            "informationUri": "https://github.com/your-org/security-scanner"
                        }
                    },
                    "results": []
                }
            ]
        }
        
        # Add results
        for result in pipeline_result.scan_results.values():
            for vuln in result.vulnerabilities:
                sarif_result = {
                    "ruleId": vuln.id,
                    "message": {
                        "text": vuln.description
                    },
                    "level": self._map_severity_to_sarif(vuln.severity),
                    "locations": []
                }
                
                if vuln.file_path:
                    sarif_result["locations"].append({
                        "physicalLocation": {
                            "artifactLocation": {
                                "uri": vuln.file_path
                            },
                            "region": {
                                "startLine": vuln.line_number or 1
                            }
                        }
                    })
                
                sarif_report["runs"][0]["results"].append(sarif_result)
        
        return sarif_report
    
    def _create_csv_report(self, pipeline_result: PipelineResult, output_path: Path):
        """Create CSV report for spreadsheet analysis"""
        
        import csv
        
        with open(output_path, 'w', newline='') as csvfile:
            fieldnames = [
                'vulnerability_id', 'title', 'severity', 'scan_type', 'file_path', 
                'line_number', 'description', 'remediation', 'cwe_id', 'cve_id'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for result in pipeline_result.scan_results.values():
                for vuln in result.vulnerabilities:
                    writer.writerow({
                        'vulnerability_id': vuln.id,
                        'title': vuln.title,
                        'severity': vuln.severity.value,
                        'scan_type': vuln.scan_type.value,
                        'file_path': vuln.file_path or '',
                        'line_number': vuln.line_number or '',
                        'description': vuln.description,
                        'remediation': vuln.remediation or '',
                        'cwe_id': vuln.cwe_id or '',
                        'cve_id': vuln.cve_id or ''
                    })
    
    def _map_severity_to_sarif(self, severity: VulnerabilitySeverity) -> str:
        """Map vulnerability severity to SARIF level"""
        mapping = {
            VulnerabilitySeverity.CRITICAL: "error",
            VulnerabilitySeverity.HIGH: "error", 
            VulnerabilitySeverity.MEDIUM: "warning",
            VulnerabilitySeverity.LOW: "note",
            VulnerabilitySeverity.INFO: "note"
        }
        return mapping.get(severity, "warning")
    
    async def _compare_with_baseline(
        self,
        pipeline_result: PipelineResult,
        context: PipelineContext
    ) -> Dict[str, Any]:
        """Compare results with security baseline"""
        
        baseline_key = f"{context.repository_url}_{context.branch_name}"
        
        if baseline_key not in self.security_baselines:
            # No baseline exists, create one
            self.security_baselines[baseline_key] = self._create_baseline(pipeline_result)
            return {"status": "baseline_created", "is_first_scan": True}
        
        baseline = self.security_baselines[baseline_key]
        
        # Compare current results with baseline
        current_critical = pipeline_result.risk_assessment.get("severity_breakdown", {}).get("critical", 0)
        current_high = pipeline_result.risk_assessment.get("severity_breakdown", {}).get("high", 0)
        current_total = pipeline_result.risk_assessment.get("total_vulnerabilities", 0)
        
        baseline_critical = baseline.get("critical_count", 0)
        baseline_high = baseline.get("high_count", 0)
        baseline_total = baseline.get("total_vulnerabilities", 0)
        
        comparison = {
            "status": "compared",
            "is_first_scan": False,
            "trend": {
                "critical": current_critical - baseline_critical,
                "high": current_high - baseline_high,
                "total": current_total - baseline_total
            },
            "baseline_date": baseline.get("created_date"),
            "improvement": current_critical + current_high < baseline_critical + baseline_high
        }
        
        # Update baseline if this scan is better
        if comparison["improvement"]:
            self.security_baselines[baseline_key] = self._create_baseline(pipeline_result)
            comparison["baseline_updated"] = True
        
        return comparison
    
    def _create_baseline(self, pipeline_result: PipelineResult) -> Dict[str, Any]:
        """Create security baseline from pipeline result"""
        
        return {
            "created_date": datetime.utcnow().isoformat(),
            "pipeline_id": pipeline_result.pipeline_id,
            "total_vulnerabilities": pipeline_result.risk_assessment.get("total_vulnerabilities", 0),
            "critical_count": pipeline_result.risk_assessment.get("severity_breakdown", {}).get("critical", 0),
            "high_count": pipeline_result.risk_assessment.get("severity_breakdown", {}).get("high", 0),
            "risk_score": pipeline_result.risk_assessment.get("risk_score", 0),
            "gates_passed": pipeline_result.risk_assessment.get("gates_status", {}).get("passed", 0)
        }
    
    async def _attempt_auto_remediation(
        self,
        pipeline_result: PipelineResult,
        source_path: str
    ) -> Dict[str, Any]:
        """Attempt automated remediation of common issues"""
        
        remediation_results = {
            "attempted": 0,
            "successful": 0,
            "failed": 0,
            "details": []
        }
        
        # Get all vulnerabilities
        all_vulnerabilities = []
        for result in pipeline_result.scan_results.values():
            all_vulnerabilities.extend(result.vulnerabilities)
        
        # Attempt remediation for specific vulnerability types
        for vuln in all_vulnerabilities:
            if self._can_auto_remediate(vuln):
                remediation_results["attempted"] += 1
                
                try:
                    success = await self._apply_auto_remediation(vuln, source_path)
                    if success:
                        remediation_results["successful"] += 1
                        remediation_results["details"].append({
                            "vulnerability_id": vuln.id,
                            "status": "fixed",
                            "action": "automated_fix_applied"
                        })
                    else:
                        remediation_results["failed"] += 1
                        remediation_results["details"].append({
                            "vulnerability_id": vuln.id,
                            "status": "failed",
                            "action": "automated_fix_failed"
                        })
                
                except Exception as e:
                    remediation_results["failed"] += 1
                    remediation_results["details"].append({
                        "vulnerability_id": vuln.id,
                        "status": "error",
                        "action": f"remediation_error: {str(e)}"
                    })
        
        return remediation_results
    
    def _can_auto_remediate(self, vulnerability) -> bool:
        """Check if vulnerability can be automatically remediated"""
        
        # Define auto-remediable vulnerability patterns
        auto_remediable = [
            "debug_mode",  # Can disable debug mode
            "hardcoded_secret",  # Can comment out or move to env vars
            "weak_crypto"  # Can suggest stronger alternatives
        ]
        
        return any(pattern in vulnerability.id.lower() for pattern in auto_remediable)
    
    async def _apply_auto_remediation(self, vulnerability, source_path: str) -> bool:
        """Apply automated remediation for vulnerability"""
        
        # This is a simplified example - real implementation would be more sophisticated
        if not vulnerability.file_path or not vulnerability.line_number:
            return False
        
        try:
            file_path = Path(source_path) / vulnerability.file_path
            if not file_path.exists():
                return False
            
            # Read file
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            # Apply simple fixes
            if "debug_mode" in vulnerability.id.lower():
                # Replace debug=True with debug=False
                target_line = vulnerability.line_number - 1
                if target_line < len(lines):
                    lines[target_line] = lines[target_line].replace("debug=True", "debug=False")
                    lines[target_line] = lines[target_line].replace("DEBUG = True", "DEBUG = False")
            
            elif "hardcoded_secret" in vulnerability.id.lower():
                # Comment out the line and add TODO
                target_line = vulnerability.line_number - 1
                if target_line < len(lines):
                    original_line = lines[target_line]
                    lines[target_line] = f"# TODO: Move to environment variable - {original_line}"
            
            # Write file back
            with open(file_path, 'w') as f:
                f.writelines(lines)
            
            return True
            
        except Exception as e:
            self.logger.error("Auto-remediation failed",
                            vulnerability_id=vulnerability.id,
                            error=str(e))
            return False
    
    def get_pipeline_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get pipeline execution history"""
        
        history = []
        for pipeline_result in list(self.pipeline_history.values())[-limit:]:
            history.append({
                "pipeline_id": pipeline_result.pipeline_id,
                "timestamp": pipeline_result.context.timestamp.isoformat(),
                "branch": pipeline_result.context.branch_name,
                "environment": pipeline_result.context.environment.value,
                "status": pipeline_result.overall_status,
                "duration_seconds": pipeline_result.duration_seconds,
                "risk_level": pipeline_result.risk_assessment.get("risk_level", "UNKNOWN"),
                "total_vulnerabilities": pipeline_result.risk_assessment.get("total_vulnerabilities", 0)
            })
        
        return sorted(history, key=lambda x: x["timestamp"], reverse=True)
    
    def get_security_metrics(self) -> Dict[str, Any]:
        """Get security pipeline metrics"""
        
        if not self.pipeline_history:
            return {"message": "No pipeline history available"}
        
        results = list(self.pipeline_history.values())
        
        return {
            "total_pipelines": len(results),
            "successful_pipelines": len([r for r in results if r.overall_status == "PASSED"]),
            "failed_pipelines": len([r for r in results if r.overall_status == "FAILED"]),
            "average_duration_seconds": sum(r.duration_seconds for r in results) / len(results),
            "average_vulnerabilities": sum(r.risk_assessment.get("total_vulnerabilities", 0) for r in results) / len(results),
            "security_trend": self._calculate_security_trend(results)
        }
    
    def _calculate_security_trend(self, results: List[PipelineResult]) -> str:
        """Calculate security trend over time"""
        
        if len(results) < 2:
            return "insufficient_data"
        
        # Sort by timestamp
        sorted_results = sorted(results, key=lambda x: x.context.timestamp)
        
        # Compare first half with second half
        mid_point = len(sorted_results) // 2
        first_half_avg = sum(r.risk_assessment.get("total_vulnerabilities", 0) for r in sorted_results[:mid_point]) / mid_point
        second_half_avg = sum(r.risk_assessment.get("total_vulnerabilities", 0) for r in sorted_results[mid_point:]) / (len(sorted_results) - mid_point)
        
        if second_half_avg < first_half_avg * 0.8:
            return "improving"
        elif second_half_avg > first_half_avg * 1.2:
            return "degrading"
        else:
            return "stable"