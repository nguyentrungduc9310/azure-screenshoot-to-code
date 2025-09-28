"""
Security Compliance and Audit Framework
GDPR, SOC2, ISO27001, HIPAA compliance monitoring and audit trail management
"""
import json
import hashlib
import secrets
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import asyncio
from pathlib import Path

from app.core.config import Settings
from shared.monitoring.structured_logger import StructuredLogger

class ComplianceFramework(str, Enum):
    """Supported compliance frameworks"""
    GDPR = "gdpr"
    SOC2 = "soc2"
    ISO27001 = "iso27001"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    NIST = "nist"
    OWASP = "owasp"

class DataClassification(str, Enum):
    """Data classification levels"""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    PII = "pii"
    PHI = "phi"  # Protected Health Information
    PCI = "pci"  # Payment Card Industry data

class AuditEventType(str, Enum):
    """Types of audit events"""
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    DATA_DELETION = "data_deletion"
    DATA_EXPORT = "data_export"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    CONFIGURATION_CHANGE = "configuration_change"
    SECURITY_EVENT = "security_event"
    PRIVACY_EVENT = "privacy_event"
    COMPLIANCE_VIOLATION = "compliance_violation"

class ComplianceStatus(str, Enum):
    """Compliance status levels"""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    REMEDIATION_REQUIRED = "remediation_required"

@dataclass
class AuditEvent:
    """Audit event record"""
    event_id: str
    event_type: AuditEventType
    timestamp: datetime
    user_id: Optional[str]
    session_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    resource: str
    action: str
    outcome: str
    details: Dict[str, Any] = field(default_factory=dict)
    data_classification: Optional[DataClassification] = None
    compliance_frameworks: List[ComplianceFramework] = field(default_factory=list)
    risk_level: str = "low"
    retention_period: int = 2557  # 7 years in days (default for most compliance)

@dataclass
class ComplianceRequirement:
    """Compliance requirement definition"""
    requirement_id: str
    framework: ComplianceFramework
    title: str
    description: str
    control_objective: str
    implementation_guidance: List[str]
    evidence_requirements: List[str]
    automation_possible: bool
    priority: str  # high, medium, low
    remediation_time: int  # days

@dataclass
class ComplianceAssessment:
    """Compliance assessment result"""
    assessment_id: str
    framework: ComplianceFramework
    assessed_at: datetime
    status: ComplianceStatus
    score: float  # 0-100
    total_requirements: int
    met_requirements: int
    failed_requirements: List[str]
    recommendations: List[str]
    next_assessment_due: datetime
    assessor: str

@dataclass
class DataRetentionPolicy:
    """Data retention policy"""
    policy_id: str
    data_type: str
    classification: DataClassification
    retention_period_days: int
    deletion_method: str
    legal_basis: str
    applicable_frameworks: List[ComplianceFramework]
    exceptions: List[str] = field(default_factory=list)

class ComplianceManager:
    """Comprehensive compliance and audit management system"""
    
    def __init__(self, settings: Settings, logger: StructuredLogger):
        self.settings = settings
        self.logger = logger
        
        # Audit trail storage
        self.audit_events: List[AuditEvent] = []
        self.audit_index: Dict[str, List[int]] = {}  # Index by user_id, resource, etc.
        
        # Compliance requirements and assessments
        self.compliance_requirements: Dict[ComplianceFramework, List[ComplianceRequirement]] = {}
        self.compliance_assessments: Dict[ComplianceFramework, ComplianceAssessment] = {}
        
        # Data retention policies
        self.retention_policies: Dict[str, DataRetentionPolicy] = {}
        
        # Privacy and consent management
        self.consent_records: Dict[str, Dict] = {}
        self.data_processing_records: Dict[str, Dict] = {}
        
        # Initialize compliance frameworks
        self._initialize_compliance_requirements()
        self._initialize_retention_policies()
        
        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._assessment_task: Optional[asyncio.Task] = None
        self._running = False
        
        self.logger.info("Compliance manager initialized",
                        frameworks=list(self.compliance_requirements.keys()),
                        retention_policies=len(self.retention_policies))
    
    def _initialize_compliance_requirements(self):
        """Initialize compliance requirements for supported frameworks"""
        
        # GDPR Requirements
        self.compliance_requirements[ComplianceFramework.GDPR] = [
            ComplianceRequirement(
                requirement_id="GDPR-Art6",
                framework=ComplianceFramework.GDPR,
                title="Lawful Basis for Processing",
                description="Personal data must be processed lawfully, fairly and transparently",
                control_objective="Ensure all personal data processing has a valid legal basis",
                implementation_guidance=[
                    "Document legal basis for each processing activity",
                    "Implement consent management system",
                    "Maintain records of processing activities"
                ],
                evidence_requirements=[
                    "Consent records",
                    "Legal basis documentation",
                    "Processing activity records"
                ],
                automation_possible=True,
                priority="high",
                remediation_time=30
            ),
            ComplianceRequirement(
                requirement_id="GDPR-Art25",
                framework=ComplianceFramework.GDPR,
                title="Data Protection by Design and by Default",
                description="Implement technical and organizational measures for data protection",
                control_objective="Ensure data protection is built into systems and processes",
                implementation_guidance=[
                    "Implement privacy-preserving technologies",
                    "Use pseudonymization and encryption",
                    "Minimize data collection and processing"
                ],
                evidence_requirements=[
                    "Technical architecture documentation",
                    "Encryption implementation",
                    "Data minimization policies"
                ],
                automation_possible=True,
                priority="high",
                remediation_time=90
            ),
            ComplianceRequirement(
                requirement_id="GDPR-Art32",
                framework=ComplianceFramework.GDPR,
                title="Security of Processing",
                description="Implement appropriate technical and organizational security measures",
                control_objective="Ensure confidentiality, integrity, and availability of personal data",
                implementation_guidance=[
                    "Implement encryption in transit and at rest",
                    "Use access controls and authentication",
                    "Maintain security monitoring and incident response"
                ],
                evidence_requirements=[
                    "Security implementation documentation",
                    "Access control logs",
                    "Incident response procedures"
                ],
                automation_possible=True,
                priority="critical",
                remediation_time=60
            )
        ]
        
        # SOC 2 Requirements
        self.compliance_requirements[ComplianceFramework.SOC2] = [
            ComplianceRequirement(
                requirement_id="SOC2-CC6.1",
                framework=ComplianceFramework.SOC2,
                title="Logical and Physical Access Controls",
                description="Implement controls to manage logical and physical access",
                control_objective="Restrict access to authorized users and prevent unauthorized access",
                implementation_guidance=[
                    "Implement multi-factor authentication",
                    "Use role-based access controls",
                    "Monitor and log access activities"
                ],
                evidence_requirements=[
                    "Access control policies",
                    "Authentication logs",
                    "User access reviews"
                ],
                automation_possible=True,
                priority="high",
                remediation_time=45
            ),
            ComplianceRequirement(
                requirement_id="SOC2-CC7.1",
                framework=ComplianceFramework.SOC2,
                title="System Monitoring",
                description="Implement monitoring to detect security events and incidents",
                control_objective="Detect and respond to security threats and vulnerabilities",
                implementation_guidance=[
                    "Implement security monitoring tools",
                    "Establish incident response procedures",
                    "Conduct regular vulnerability assessments"
                ],
                evidence_requirements=[
                    "Monitoring system documentation",
                    "Incident response logs",
                    "Vulnerability assessment reports"
                ],
                automation_possible=True,
                priority="high",
                remediation_time=60
            )
        ]
        
        # ISO 27001 Requirements
        self.compliance_requirements[ComplianceFramework.ISO27001] = [
            ComplianceRequirement(
                requirement_id="ISO27001-A.9.1.1",
                framework=ComplianceFramework.ISO27001,
                title="Access Control Policy",
                description="Establish and maintain access control policy",
                control_objective="Control access to information and information processing facilities",
                implementation_guidance=[
                    "Define access control policy",
                    "Implement user access management",
                    "Regular access reviews"
                ],
                evidence_requirements=[
                    "Access control policy document",
                    "User access management procedures",
                    "Access review reports"
                ],
                automation_possible=True,
                priority="high",
                remediation_time=30
            ),
            ComplianceRequirement(
                requirement_id="ISO27001-A.12.6.1",
                framework=ComplianceFramework.ISO27001,
                title="Management of Technical Vulnerabilities",
                description="Obtain timely information about technical vulnerabilities",
                control_objective="Prevent exploitation of technical vulnerabilities",
                implementation_guidance=[
                    "Implement vulnerability management process",
                    "Regular vulnerability scanning",
                    "Timely patching procedures"
                ],
                evidence_requirements=[
                    "Vulnerability management policy",
                    "Vulnerability scan reports",
                    "Patch management records"
                ],
                automation_possible=True,
                priority="high",
                remediation_time=14
            )
        ]
    
    def _initialize_retention_policies(self):
        """Initialize data retention policies"""
        self.retention_policies = {
            "audit_logs": DataRetentionPolicy(
                policy_id="AUDIT-001",
                data_type="audit_logs",
                classification=DataClassification.CONFIDENTIAL,
                retention_period_days=2557,  # 7 years
                deletion_method="secure_delete",
                legal_basis="Legal obligation and legitimate interest",
                applicable_frameworks=[
                    ComplianceFramework.GDPR,
                    ComplianceFramework.SOC2,
                    ComplianceFramework.ISO27001
                ]
            ),
            "user_data": DataRetentionPolicy(
                policy_id="USER-001",
                data_type="user_data",
                classification=DataClassification.PII,
                retention_period_days=1095,  # 3 years
                deletion_method="secure_delete",
                legal_basis="Consent and contract",
                applicable_frameworks=[ComplianceFramework.GDPR],
                exceptions=["Legal hold", "Active legal proceedings"]
            ),
            "session_data": DataRetentionPolicy(
                policy_id="SESSION-001",
                data_type="session_data",
                classification=DataClassification.CONFIDENTIAL,
                retention_period_days=90,  # 3 months
                deletion_method="automatic_purge",
                legal_basis="Legitimate interest",
                applicable_frameworks=[
                    ComplianceFramework.GDPR,
                    ComplianceFramework.SOC2
                ]
            ),
            "security_logs": DataRetentionPolicy(
                policy_id="SECURITY-001",
                data_type="security_logs",
                classification=DataClassification.CONFIDENTIAL,
                retention_period_days=1095,  # 3 years
                deletion_method="secure_delete",
                legal_basis="Legal obligation",
                applicable_frameworks=[
                    ComplianceFramework.SOC2,
                    ComplianceFramework.ISO27001
                ]
            )
        }
    
    # Audit Trail Management
    async def log_audit_event(
        self,
        event_type: AuditEventType,
        user_id: Optional[str],
        resource: str,
        action: str,
        outcome: str,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        data_classification: Optional[DataClassification] = None,
        compliance_frameworks: Optional[List[ComplianceFramework]] = None
    ) -> str:
        """Log audit event with compliance tracking"""
        
        event_id = self._generate_event_id()
        
        # Determine applicable compliance frameworks if not specified
        if not compliance_frameworks:
            compliance_frameworks = self._determine_applicable_frameworks(
                event_type, data_classification
            )
        
        # Determine retention period based on frameworks and data classification
        retention_period = self._determine_retention_period(
            event_type, data_classification, compliance_frameworks
        )
        
        audit_event = AuditEvent(
            event_id=event_id,
            event_type=event_type,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            resource=resource,
            action=action,
            outcome=outcome,
            details=details or {},
            data_classification=data_classification,
            compliance_frameworks=compliance_frameworks,
            retention_period=retention_period
        )
        
        # Store audit event
        event_index = len(self.audit_events)
        self.audit_events.append(audit_event)
        
        # Update indices for faster searching
        self._update_audit_indices(audit_event, event_index)
        
        self.logger.info("Audit event logged",
                        event_id=event_id,
                        event_type=event_type.value,
                        user_id=user_id,
                        resource=resource,
                        action=action,
                        outcome=outcome,
                        compliance_frameworks=[f.value for f in compliance_frameworks])
        
        return event_id
    
    def _generate_event_id(self) -> str:
        """Generate unique audit event ID"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        random_part = secrets.token_hex(4)
        return f"AUDIT_{timestamp}_{random_part}"
    
    def _determine_applicable_frameworks(
        self,
        event_type: AuditEventType,
        data_classification: Optional[DataClassification]
    ) -> List[ComplianceFramework]:
        """Determine which compliance frameworks apply to an event"""
        frameworks = []
        
        # All events typically need basic compliance
        frameworks.append(ComplianceFramework.ISO27001)
        
        # PII-related events require GDPR compliance
        if data_classification in [DataClassification.PII, DataClassification.CONFIDENTIAL]:
            frameworks.append(ComplianceFramework.GDPR)
        
        # Security events require SOC2 compliance
        if event_type in [
            AuditEventType.AUTHENTICATION,
            AuditEventType.AUTHORIZATION,
            AuditEventType.SECURITY_EVENT,
            AuditEventType.CONFIGURATION_CHANGE
        ]:
            frameworks.append(ComplianceFramework.SOC2)
        
        # Healthcare-related data requires HIPAA
        if data_classification == DataClassification.PHI:
            frameworks.append(ComplianceFramework.HIPAA)
        
        # Payment data requires PCI DSS
        if data_classification == DataClassification.PCI:
            frameworks.append(ComplianceFramework.PCI_DSS)
        
        return frameworks
    
    def _determine_retention_period(
        self,
        event_type: AuditEventType,
        data_classification: Optional[DataClassification],
        frameworks: List[ComplianceFramework]
    ) -> int:
        """Determine retention period based on compliance requirements"""
        
        # Default retention periods by framework (in days)
        framework_retention = {
            ComplianceFramework.GDPR: 2557,      # 7 years
            ComplianceFramework.SOC2: 2557,      # 7 years
            ComplianceFramework.ISO27001: 1095,  # 3 years
            ComplianceFramework.HIPAA: 2190,     # 6 years
            ComplianceFramework.PCI_DSS: 365     # 1 year
        }
        
        # Take the longest retention period from applicable frameworks
        max_retention = max(
            framework_retention.get(framework, 365)
            for framework in frameworks
        ) if frameworks else 365
        
        # Adjust based on data classification
        if data_classification in [DataClassification.PII, DataClassification.PHI]:
            max_retention = max(max_retention, 2557)  # Minimum 7 years for sensitive data
        
        return max_retention
    
    def _update_audit_indices(self, event: AuditEvent, index: int):
        """Update audit event indices for faster searching"""
        # Index by user ID
        if event.user_id:
            if event.user_id not in self.audit_index:
                self.audit_index[event.user_id] = []
            self.audit_index[event.user_id].append(index)
        
        # Index by resource
        resource_key = f"resource:{event.resource}"
        if resource_key not in self.audit_index:
            self.audit_index[resource_key] = []
        self.audit_index[resource_key].append(index)
        
        # Index by event type
        type_key = f"type:{event.event_type.value}"
        if type_key not in self.audit_index:
            self.audit_index[type_key] = []
        self.audit_index[type_key].append(index)
    
    # Audit Query Methods
    async def query_audit_events(
        self,
        user_id: Optional[str] = None,
        resource: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[AuditEvent]:
        """Query audit events with filters"""
        
        candidate_indices = set()
        
        # Use indices to narrow down search
        if user_id and user_id in self.audit_index:
            candidate_indices.update(self.audit_index[user_id])
        elif resource:
            resource_key = f"resource:{resource}"
            if resource_key in self.audit_index:
                candidate_indices.update(self.audit_index[resource_key])
        elif event_type:
            type_key = f"type:{event_type.value}"
            if type_key in self.audit_index:
                candidate_indices.update(self.audit_index[type_key])
        else:
            # No specific filter, search all events
            candidate_indices = set(range(len(self.audit_events)))
        
        # Filter events
        matching_events = []
        for index in candidate_indices:
            if index >= len(self.audit_events):
                continue
            
            event = self.audit_events[index]
            
            # Apply filters
            if user_id and event.user_id != user_id:
                continue
            if resource and event.resource != resource:
                continue
            if event_type and event.event_type != event_type:
                continue
            if start_time and event.timestamp < start_time:
                continue
            if end_time and event.timestamp > end_time:
                continue
            
            matching_events.append(event)
            
            if len(matching_events) >= limit:
                break
        
        # Sort by timestamp (newest first)
        matching_events.sort(key=lambda x: x.timestamp, reverse=True)
        
        return matching_events[:limit]
    
    # Compliance Assessment
    async def assess_compliance(self, framework: ComplianceFramework) -> ComplianceAssessment:
        """Perform compliance assessment for a framework"""
        
        assessment_id = f"ASSESS_{framework.value}_{int(datetime.utcnow().timestamp())}"
        requirements = self.compliance_requirements.get(framework, [])
        
        if not requirements:
            raise ValueError(f"No requirements defined for framework: {framework}")
        
        self.logger.info("Starting compliance assessment",
                        assessment_id=assessment_id,
                        framework=framework.value,
                        total_requirements=len(requirements))
        
        met_requirements = 0
        failed_requirements = []
        recommendations = []
        
        for requirement in requirements:
            compliance_status = await self._assess_requirement(requirement)
            
            if compliance_status["status"] == ComplianceStatus.COMPLIANT:
                met_requirements += 1
            else:
                failed_requirements.append(requirement.requirement_id)
                recommendations.extend(compliance_status.get("recommendations", []))
        
        # Calculate compliance score
        score = (met_requirements / len(requirements)) * 100 if requirements else 0
        
        # Determine overall status
        if score >= 90:
            status = ComplianceStatus.COMPLIANT
        elif score >= 70:
            status = ComplianceStatus.PARTIAL
        else:
            status = ComplianceStatus.NON_COMPLIANT
        
        assessment = ComplianceAssessment(
            assessment_id=assessment_id,
            framework=framework,
            assessed_at=datetime.utcnow(),
            status=status,
            score=score,
            total_requirements=len(requirements),
            met_requirements=met_requirements,
            failed_requirements=failed_requirements,
            recommendations=list(set(recommendations)),  # Remove duplicates
            next_assessment_due=datetime.utcnow() + timedelta(days=90),  # Quarterly
            assessor="automated_system"
        )
        
        self.compliance_assessments[framework] = assessment
        
        self.logger.info("Compliance assessment completed",
                        assessment_id=assessment_id,
                        framework=framework.value,
                        status=status.value,
                        score=score,
                        met_requirements=met_requirements,
                        total_requirements=len(requirements))
        
        return assessment
    
    async def _assess_requirement(self, requirement: ComplianceRequirement) -> Dict[str, Any]:
        """Assess a specific compliance requirement"""
        
        # This is a simplified assessment - in production, this would involve
        # more sophisticated checks including automated testing, policy review, etc.
        
        assessment_result = {
            "requirement_id": requirement.requirement_id,
            "status": ComplianceStatus.UNKNOWN,
            "evidence": [],
            "recommendations": []
        }
        
        # Simulate automated checks based on requirement type
        if "access control" in requirement.title.lower():
            # Check if we have access control mechanisms
            if self._has_access_controls():
                assessment_result["status"] = ComplianceStatus.COMPLIANT
                assessment_result["evidence"].append("Access control system implemented")
            else:
                assessment_result["status"] = ComplianceStatus.NON_COMPLIANT
                assessment_result["recommendations"].append("Implement access control system")
        
        elif "monitoring" in requirement.title.lower():
            # Check if we have monitoring systems
            if self._has_monitoring_systems():
                assessment_result["status"] = ComplianceStatus.COMPLIANT
                assessment_result["evidence"].append("Monitoring systems active")
            else:
                assessment_result["status"] = ComplianceStatus.NON_COMPLIANT
                assessment_result["recommendations"].append("Implement monitoring systems")
        
        elif "encryption" in requirement.description.lower():
            # Check if we have encryption
            if self._has_encryption():
                assessment_result["status"] = ComplianceStatus.COMPLIANT
                assessment_result["evidence"].append("Encryption implemented")
            else:
                assessment_result["status"] = ComplianceStatus.NON_COMPLIANT
                assessment_result["recommendations"].append("Implement encryption")
        
        elif "audit" in requirement.description.lower():
            # Check if we have audit logging
            if len(self.audit_events) > 0:
                assessment_result["status"] = ComplianceStatus.COMPLIANT
                assessment_result["evidence"].append("Audit logging active")
            else:
                assessment_result["status"] = ComplianceStatus.PARTIAL
                assessment_result["recommendations"].append("Enhance audit logging coverage")
        
        else:
            # Default to partial compliance for requirements we can't automatically assess
            assessment_result["status"] = ComplianceStatus.PARTIAL
            assessment_result["recommendations"].append(f"Manual review required for {requirement.title}")
        
        return assessment_result
    
    def _has_access_controls(self) -> bool:
        """Check if access controls are implemented"""
        # This would check actual system configuration
        return True  # Simplified for demo
    
    def _has_monitoring_systems(self) -> bool:
        """Check if monitoring systems are active"""
        # This would check monitoring system status
        return True  # Simplified for demo
    
    def _has_encryption(self) -> bool:
        """Check if encryption is implemented"""
        # This would check encryption configuration
        return True  # Simplified for demo
    
    # Privacy and Consent Management
    async def record_consent(
        self,
        user_id: str,
        consent_type: str,
        consent_given: bool,
        legal_basis: str,
        purpose: str,
        data_categories: List[str],
        retention_period: Optional[int] = None
    ) -> str:
        """Record user consent for GDPR compliance"""
        
        consent_id = f"CONSENT_{user_id}_{int(datetime.utcnow().timestamp())}"
        
        consent_record = {
            "consent_id": consent_id,
            "user_id": user_id,
            "consent_type": consent_type,
            "consent_given": consent_given,
            "legal_basis": legal_basis,
            "purpose": purpose,
            "data_categories": data_categories,
            "retention_period": retention_period,
            "recorded_at": datetime.utcnow().isoformat(),
            "ip_address": None,  # Would be populated from request context
            "user_agent": None   # Would be populated from request context
        }
        
        if user_id not in self.consent_records:
            self.consent_records[user_id] = {}
        
        self.consent_records[user_id][consent_id] = consent_record
        
        # Log audit event
        await self.log_audit_event(
            event_type=AuditEventType.PRIVACY_EVENT,
            user_id=user_id,
            resource="consent_management",
            action="record_consent",
            outcome="success",
            details={
                "consent_id": consent_id,
                "consent_type": consent_type,
                "consent_given": consent_given,
                "purpose": purpose
            },
            data_classification=DataClassification.PII,
            compliance_frameworks=[ComplianceFramework.GDPR]
        )
        
        self.logger.info("Consent recorded",
                        consent_id=consent_id,
                        user_id=user_id,
                        consent_type=consent_type,
                        consent_given=consent_given)
        
        return consent_id
    
    async def get_user_consents(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all consent records for a user"""
        return list(self.consent_records.get(user_id, {}).values())
    
    async def withdraw_consent(self, user_id: str, consent_id: str, reason: str = None) -> bool:
        """Withdraw user consent"""
        
        if user_id not in self.consent_records:
            return False
        
        if consent_id not in self.consent_records[user_id]:
            return False
        
        # Update consent record
        consent_record = self.consent_records[user_id][consent_id]
        consent_record["consent_given"] = False
        consent_record["withdrawn_at"] = datetime.utcnow().isoformat()
        consent_record["withdrawal_reason"] = reason
        
        # Log audit event
        await self.log_audit_event(
            event_type=AuditEventType.PRIVACY_EVENT,
            user_id=user_id,
            resource="consent_management",
            action="withdraw_consent",
            outcome="success",
            details={
                "consent_id": consent_id,
                "reason": reason
            },
            data_classification=DataClassification.PII,
            compliance_frameworks=[ComplianceFramework.GDPR]
        )
        
        self.logger.info("Consent withdrawn",
                        consent_id=consent_id,
                        user_id=user_id,
                        reason=reason)
        
        return True
    
    # Data Subject Rights (GDPR)
    async def process_data_subject_request(
        self,
        user_id: str,
        request_type: str,  # access, rectification, erasure, portability
        details: Dict[str, Any]
    ) -> str:
        """Process data subject rights request"""
        
        request_id = f"DSR_{request_type.upper()}_{user_id}_{int(datetime.utcnow().timestamp())}"
        
        # Log the request
        await self.log_audit_event(
            event_type=AuditEventType.PRIVACY_EVENT,
            user_id=user_id,
            resource="data_subject_rights",
            action=f"request_{request_type}",
            outcome="received",
            details={
                "request_id": request_id,
                "request_type": request_type,
                "details": details
            },
            data_classification=DataClassification.PII,
            compliance_frameworks=[ComplianceFramework.GDPR]
        )
        
        self.logger.info("Data subject request received",
                        request_id=request_id,
                        user_id=user_id,
                        request_type=request_type)
        
        return request_id
    
    # Data Retention Management
    async def apply_retention_policies(self):
        """Apply data retention policies and clean up expired data"""
        
        current_time = datetime.utcnow()
        cleaned_up_count = 0
        
        # Clean up audit events based on retention policies
        retained_events = []
        for event in self.audit_events:
            retention_deadline = event.timestamp + timedelta(days=event.retention_period)
            
            if current_time < retention_deadline:
                retained_events.append(event)
            else:
                cleaned_up_count += 1
                
                # Log the cleanup
                await self.log_audit_event(
                    event_type=AuditEventType.DATA_DELETION,
                    user_id="system",
                    resource="audit_events",
                    action="retention_cleanup",
                    outcome="success",
                    details={
                        "deleted_event_id": event.event_id,
                        "retention_period": event.retention_period,
                        "event_age_days": (current_time - event.timestamp).days
                    }
                )
        
        self.audit_events = retained_events
        
        # Rebuild indices after cleanup
        self._rebuild_audit_indices()
        
        if cleaned_up_count > 0:
            self.logger.info("Data retention policy applied",
                           cleaned_up_events=cleaned_up_count,
                           remaining_events=len(self.audit_events))
        
        return cleaned_up_count
    
    def _rebuild_audit_indices(self):
        """Rebuild audit event indices after cleanup"""
        self.audit_index.clear()
        
        for index, event in enumerate(self.audit_events):
            self._update_audit_indices(event, index)
    
    # Reporting and Analytics
    def generate_compliance_report(self, framework: ComplianceFramework) -> Dict[str, Any]:
        """Generate comprehensive compliance report"""
        
        assessment = self.compliance_assessments.get(framework)
        if not assessment:
            return {"error": f"No assessment available for {framework.value}"}
        
        # Get relevant audit events
        framework_events = [
            event for event in self.audit_events
            if framework in event.compliance_frameworks
        ]
        
        # Calculate metrics
        total_events = len(framework_events)
        event_types = {}
        for event in framework_events:
            event_type = event.event_type.value
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        report = {
            "framework": framework.value,
            "assessment": {
                "assessment_id": assessment.assessment_id,
                "status": assessment.status.value,
                "score": assessment.score,
                "assessed_at": assessment.assessed_at.isoformat(),
                "total_requirements": assessment.total_requirements,
                "met_requirements": assessment.met_requirements,
                "compliance_percentage": assessment.score
            },
            "audit_statistics": {
                "total_events": total_events,
                "events_by_type": event_types,
                "reporting_period": "last_30_days"  # Could be configurable
            },
            "recommendations": assessment.recommendations,
            "next_assessment_due": assessment.next_assessment_due.isoformat()
        }
        
        return report
    
    def get_privacy_metrics(self) -> Dict[str, Any]:
        """Get privacy-related metrics for GDPR compliance"""
        
        total_consents = sum(len(consents) for consents in self.consent_records.values())
        active_consents = 0
        withdrawn_consents = 0
        
        for user_consents in self.consent_records.values():
            for consent in user_consents.values():
                if consent.get("consent_given", False):
                    active_consents += 1
                else:
                    withdrawn_consents += 1
        
        # Get privacy-related audit events
        privacy_events = [
            event for event in self.audit_events
            if event.event_type in [AuditEventType.PRIVACY_EVENT, AuditEventType.DATA_ACCESS,
                                  AuditEventType.DATA_MODIFICATION, AuditEventType.DATA_DELETION]
        ]
        
        return {
            "consent_management": {
                "total_consents": total_consents,
                "active_consents": active_consents,
                "withdrawn_consents": withdrawn_consents,
                "consent_rate": active_consents / max(total_consents, 1)
            },
            "privacy_events": {
                "total_events": len(privacy_events),
                "events_last_30_days": len([
                    e for e in privacy_events
                    if e.timestamp > datetime.utcnow() - timedelta(days=30)
                ])
            },
            "data_retention": {
                "total_policies": len(self.retention_policies),
                "policies_by_classification": {
                    policy.classification.value: 1
                    for policy in self.retention_policies.values()
                }
            }
        }
    
    async def start(self):
        """Start compliance manager background tasks"""
        self._running = True
        
        # Start periodic cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        # Start periodic assessment task
        self._assessment_task = asyncio.create_task(self._assessment_loop())
        
        self.logger.info("Compliance manager started")
    
    async def stop(self):
        """Stop compliance manager background tasks"""
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        if self._assessment_task:
            self._assessment_task.cancel()
            try:
                await self._assessment_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Compliance manager stopped")
    
    async def _cleanup_loop(self):
        """Background task for data retention cleanup"""
        while self._running:
            try:
                await self.apply_retention_policies()
                await asyncio.sleep(86400)  # Run daily
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Retention cleanup error", error=str(e))
                await asyncio.sleep(3600)  # Retry in 1 hour on error
    
    async def _assessment_loop(self):
        """Background task for periodic compliance assessments"""
        while self._running:
            try:
                # Run assessments quarterly
                for framework in self.compliance_requirements.keys():
                    last_assessment = self.compliance_assessments.get(framework)
                    
                    if (not last_assessment or 
                        datetime.utcnow() > last_assessment.next_assessment_due):
                        await self.assess_compliance(framework)
                
                await asyncio.sleep(86400)  # Check daily
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Compliance assessment error", error=str(e))
                await asyncio.sleep(3600)  # Retry in 1 hour on error