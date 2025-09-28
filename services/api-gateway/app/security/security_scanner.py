"""
Advanced Security Scanner
Comprehensive security scanning, vulnerability detection, and threat analysis
"""
import re
import hashlib
import ipaddress
import asyncio
import time
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import json
import base64
from urllib.parse import urlparse, parse_qs

from fastapi import Request, Response
import httpx

from app.core.config import Settings
from shared.monitoring.structured_logger import StructuredLogger

class ThreatLevel(str, Enum):
    """Security threat levels"""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class VulnerabilityType(str, Enum):
    """Types of security vulnerabilities"""
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    CSRF = "csrf"
    PATH_TRAVERSAL = "path_traversal"
    COMMAND_INJECTION = "command_injection"
    INSECURE_DESERIALIZATION = "insecure_deserialization"
    AUTHENTICATION_BYPASS = "authentication_bypass"
    AUTHORIZATION_BYPASS = "authorization_bypass"
    INFORMATION_DISCLOSURE = "information_disclosure"
    MALICIOUS_FILE_UPLOAD = "malicious_file_upload"
    BRUTE_FORCE = "brute_force"
    DDoS = "ddos"
    BOT_ATTACK = "bot_attack"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"

class AttackPattern(str, Enum):
    """Known attack patterns"""
    RECONNAISSANCE = "reconnaissance"
    EXPLOITATION = "exploitation"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    PERSISTENCE = "persistence"
    DEFENSE_EVASION = "defense_evasion"
    CREDENTIAL_ACCESS = "credential_access"
    DISCOVERY = "discovery"
    LATERAL_MOVEMENT = "lateral_movement"
    COLLECTION = "collection"
    EXFILTRATION = "exfiltration"
    IMPACT = "impact"

@dataclass
class SecurityThreat:
    """Security threat detection result"""
    threat_id: str
    threat_type: VulnerabilityType
    threat_level: ThreatLevel
    title: str
    description: str
    evidence: Dict[str, Any]
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None
    endpoint: Optional[str] = None
    detected_at: datetime = field(default_factory=datetime.utcnow)
    attack_patterns: List[AttackPattern] = field(default_factory=list)
    remediation: List[str] = field(default_factory=list)
    confidence_score: float = 0.0

@dataclass
class SecurityScanResult:
    """Security scan result"""
    scan_id: str
    target: str
    scan_type: str
    threats_detected: List[SecurityThreat]
    scan_duration: float
    total_checks: int
    vulnerabilities_found: int
    risk_score: float
    started_at: datetime
    completed_at: datetime
    recommendations: List[str] = field(default_factory=list)

class SecurityScanner:
    """Advanced security scanner for threat detection and vulnerability assessment"""
    
    def __init__(self, settings: Settings, logger: StructuredLogger):
        self.settings = settings
        self.logger = logger
        
        # Security patterns and rules
        self.sql_injection_patterns = self._load_sql_injection_patterns()
        self.xss_patterns = self._load_xss_patterns()
        self.path_traversal_patterns = self._load_path_traversal_patterns()
        self.command_injection_patterns = self._load_command_injection_patterns()
        
        # IP reputation and geolocation data
        self.malicious_ips: Set[str] = set()
        self.suspicious_ips: Set[str] = set()
        self.ip_reputation_cache: Dict[str, Dict] = {}
        
        # Bot detection patterns
        self.bot_patterns = self._load_bot_patterns()
        self.suspicious_user_agents = self._load_suspicious_user_agents()
        
        # Attack tracking
        self.attack_attempts: Dict[str, List[datetime]] = {}
        self.blocked_ips: Dict[str, datetime] = {}
        
        # Security metrics
        self.threats_detected = 0
        self.scans_performed = 0
        self.false_positives = 0
        
        self.logger.info("Advanced security scanner initialized",
                        patterns_loaded=len(self.sql_injection_patterns) + len(self.xss_patterns))
    
    def _load_sql_injection_patterns(self) -> List[Dict[str, Any]]:
        """Load SQL injection detection patterns"""
        return [
            {
                "pattern": r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)",
                "flags": re.IGNORECASE,
                "description": "SQL keywords detected",
                "confidence": 0.7
            },
            {
                "pattern": r"('.*'|\".*\"|\b\d+\b).*(=|<|>|LIKE).*('.*'|\".*\"|\b\d+\b)",
                "flags": re.IGNORECASE,
                "description": "SQL comparison operators with quoted values",
                "confidence": 0.8
            },
            {
                "pattern": r"(\w+)\s*=\s*(\w+|'[^']*'|\"[^\"]*\")",
                "flags": re.IGNORECASE,
                "description": "Assignment patterns common in SQL injection",
                "confidence": 0.6
            },
            {
                "pattern": r"(;|\s+)(-{2}|#|/\*|\*/)",
                "flags": re.IGNORECASE,
                "description": "SQL comment patterns",
                "confidence": 0.9
            },
            {
                "pattern": r"\b(OR|AND)\b\s*\d+\s*(=|<|>)\s*\d+",
                "flags": re.IGNORECASE,
                "description": "Boolean-based SQL injection",
                "confidence": 0.85
            },
            {
                "pattern": r"(\+|\s+)(WAITFOR|DELAY|BENCHMARK|SLEEP)\s*\(",
                "flags": re.IGNORECASE,
                "description": "Time-based SQL injection",
                "confidence": 0.9
            }
        ]
    
    def _load_xss_patterns(self) -> List[Dict[str, Any]]:
        """Load XSS detection patterns"""
        return [
            {
                "pattern": r"<\s*script[^>]*>.*?</\s*script\s*>",
                "flags": re.IGNORECASE | re.DOTALL,
                "description": "Script tag injection",
                "confidence": 0.95
            },
            {
                "pattern": r"<\s*iframe[^>]*>",
                "flags": re.IGNORECASE,
                "description": "Iframe injection",
                "confidence": 0.8
            },
            {
                "pattern": r"on\w+\s*=\s*[\"'].*[\"']",
                "flags": re.IGNORECASE,
                "description": "Event handler injection",
                "confidence": 0.85
            },
            {
                "pattern": r"javascript\s*:",
                "flags": re.IGNORECASE,
                "description": "JavaScript protocol injection",
                "confidence": 0.9
            },
            {
                "pattern": r"<\s*(img|link|meta|object|embed)[^>]*>",
                "flags": re.IGNORECASE,
                "description": "HTML tag injection",
                "confidence": 0.7
            },
            {
                "pattern": r"(alert|confirm|prompt)\s*\(",
                "flags": re.IGNORECASE,
                "description": "JavaScript dialog functions",
                "confidence": 0.8
            }
        ]
    
    def _load_path_traversal_patterns(self) -> List[Dict[str, Any]]:
        """Load path traversal detection patterns"""
        return [
            {
                "pattern": r"\.\.[\\/]",
                "flags": re.IGNORECASE,
                "description": "Directory traversal sequences",
                "confidence": 0.9
            },
            {
                "pattern": r"[\\/]etc[\\/]passwd",
                "flags": re.IGNORECASE,
                "description": "Unix password file access",
                "confidence": 0.95
            },
            {
                "pattern": r"[\\/]windows[\\/]system32",
                "flags": re.IGNORECASE,
                "description": "Windows system directory access",
                "confidence": 0.9
            },
            {
                "pattern": r"%2e%2e[%2f%5c]",
                "flags": re.IGNORECASE,
                "description": "URL-encoded directory traversal",
                "confidence": 0.85
            },
            {
                "pattern": r"(\.\.[\\/]){3,}",
                "flags": re.IGNORECASE,
                "description": "Deep directory traversal",
                "confidence": 0.95
            }
        ]
    
    def _load_command_injection_patterns(self) -> List[Dict[str, Any]]:
        """Load command injection detection patterns"""
        return [
            {
                "pattern": r"[;&|`]\s*(cat|ls|dir|type|echo|ping|wget|curl|nc|netcat)",
                "flags": re.IGNORECASE,
                "description": "Command chaining with system commands",
                "confidence": 0.9
            },
            {
                "pattern": r"\$\([^)]+\)",
                "flags": re.IGNORECASE,
                "description": "Command substitution",
                "confidence": 0.8
            },
            {
                "pattern": r"`[^`]+`",
                "flags": re.IGNORECASE,
                "description": "Backtick command execution",
                "confidence": 0.85
            },
            {
                "pattern": r"(>|>>|\|)\s*[\\/]",
                "flags": re.IGNORECASE,
                "description": "Output redirection",
                "confidence": 0.75
            }
        ]
    
    def _load_bot_patterns(self) -> List[Dict[str, Any]]:
        """Load bot detection patterns"""
        return [
            {
                "pattern": r"bot|crawler|spider|scraper",
                "flags": re.IGNORECASE,
                "description": "Common bot identifiers",
                "confidence": 0.8
            },
            {
                "pattern": r"(curl|wget|httpie|python-requests|libwww|lwp)",
                "flags": re.IGNORECASE,
                "description": "Automated tools",
                "confidence": 0.7
            },
            {
                "pattern": r"^$|unknown",
                "flags": re.IGNORECASE,
                "description": "Empty or generic user agent",
                "confidence": 0.6
            }
        ]
    
    def _load_suspicious_user_agents(self) -> Set[str]:
        """Load known suspicious user agent strings"""
        return {
            "sqlmap",
            "nikto",
            "nmap",
            "masscan",
            "gobuster",
            "dirb",
            "dirbuster",
            "burpsuite",
            "owasp zap",
            "w3af",
            "skipfish",
            "acunetix",
            "nessus",
            "openvas"
        }
    
    async def scan_request(self, request: Request) -> List[SecurityThreat]:
        """Scan incoming request for security threats"""
        threats = []
        
        # Get request details
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "")
        method = request.method
        url = str(request.url)
        headers = dict(request.headers)
        
        # Get request body if available
        body = None
        try:
            if method in ["POST", "PUT", "PATCH"]:
                body = await request.body()
                if body:
                    body = body.decode('utf-8', errors='ignore')
        except Exception:
            pass
        
        # Scan for various threats
        threats.extend(await self._scan_sql_injection(request, url, headers, body))
        threats.extend(await self._scan_xss(request, url, headers, body))
        threats.extend(await self._scan_path_traversal(request, url, headers))
        threats.extend(await self._scan_command_injection(request, url, headers, body))
        threats.extend(await self._scan_bot_activity(request, user_agent, ip_address))
        threats.extend(await self._scan_brute_force(request, ip_address))
        threats.extend(await self._scan_suspicious_headers(request, headers))
        threats.extend(await self._scan_rate_limiting(request, ip_address))
        
        # Update metrics
        self.threats_detected += len(threats)
        self.scans_performed += 1
        
        return threats
    
    async def _scan_sql_injection(
        self,
        request: Request,
        url: str,
        headers: Dict[str, str],
        body: Optional[str]
    ) -> List[SecurityThreat]:
        """Scan for SQL injection attempts"""
        threats = []
        
        # Scan URL parameters
        parsed_url = urlparse(url)
        if parsed_url.query:
            params = parse_qs(parsed_url.query)
            for param_name, param_values in params.items():
                for value in param_values:
                    threat = self._check_sql_patterns(value, f"URL parameter: {param_name}")
                    if threat:
                        threat.endpoint = parsed_url.path
                        threat.source_ip = request.client.host if request.client else None
                        threats.append(threat)
        
        # Scan request body
        if body:
            threat = self._check_sql_patterns(body, "Request body")
            if threat:
                threat.endpoint = parsed_url.path
                threat.source_ip = request.client.host if request.client else None
                threats.append(threat)
        
        # Scan specific headers
        suspicious_headers = ["x-forwarded-for", "x-real-ip", "referer", "user-agent"]
        for header_name in suspicious_headers:
            if header_name in headers:
                threat = self._check_sql_patterns(headers[header_name], f"Header: {header_name}")
                if threat:
                    threat.endpoint = parsed_url.path
                    threat.source_ip = request.client.host if request.client else None
                    threats.append(threat)
        
        return threats
    
    def _check_sql_patterns(self, content: str, location: str) -> Optional[SecurityThreat]:
        """Check content against SQL injection patterns"""
        if not content:
            return None
        
        for pattern_info in self.sql_injection_patterns:
            pattern = pattern_info["pattern"]
            flags = pattern_info.get("flags", 0)
            
            if re.search(pattern, content, flags):
                return SecurityThreat(
                    threat_id=self._generate_threat_id(),
                    threat_type=VulnerabilityType.SQL_INJECTION,
                    threat_level=ThreatLevel.HIGH,
                    title="SQL Injection Attempt Detected",
                    description=f"Potential SQL injection detected in {location}: {pattern_info['description']}",
                    evidence={
                        "pattern": pattern,
                        "matched_content": content[:200],  # First 200 chars
                        "location": location,
                        "confidence": pattern_info["confidence"]
                    },
                    confidence_score=pattern_info["confidence"],
                    attack_patterns=[AttackPattern.EXPLOITATION],
                    remediation=[
                        "Use parameterized queries or prepared statements",
                        "Implement input validation and sanitization",
                        "Apply principle of least privilege to database accounts",
                        "Enable SQL injection detection in WAF"
                    ]
                )
        
        return None
    
    async def _scan_xss(
        self,
        request: Request,
        url: str,
        headers: Dict[str, str],
        body: Optional[str]
    ) -> List[SecurityThreat]:
        """Scan for XSS attempts"""
        threats = []
        
        # Scan URL parameters
        parsed_url = urlparse(url)
        if parsed_url.query:
            params = parse_qs(parsed_url.query)
            for param_name, param_values in params.items():
                for value in param_values:
                    threat = self._check_xss_patterns(value, f"URL parameter: {param_name}")
                    if threat:
                        threat.endpoint = parsed_url.path
                        threat.source_ip = request.client.host if request.client else None
                        threats.append(threat)
        
        # Scan request body
        if body:
            threat = self._check_xss_patterns(body, "Request body")
            if threat:
                threat.endpoint = parsed_url.path
                threat.source_ip = request.client.host if request.client else None
                threats.append(threat)
        
        return threats
    
    def _check_xss_patterns(self, content: str, location: str) -> Optional[SecurityThreat]:
        """Check content against XSS patterns"""
        if not content:
            return None
        
        # Decode common encodings
        decoded_content = self._decode_common_encodings(content)
        
        for pattern_info in self.xss_patterns:
            pattern = pattern_info["pattern"]
            flags = pattern_info.get("flags", 0)
            
            if re.search(pattern, decoded_content, flags):
                return SecurityThreat(
                    threat_id=self._generate_threat_id(),
                    threat_type=VulnerabilityType.XSS,
                    threat_level=ThreatLevel.HIGH,
                    title="Cross-Site Scripting (XSS) Attempt Detected",
                    description=f"Potential XSS attack detected in {location}: {pattern_info['description']}",
                    evidence={
                        "pattern": pattern,
                        "matched_content": decoded_content[:200],
                        "original_content": content[:200],
                        "location": location,
                        "confidence": pattern_info["confidence"]
                    },
                    confidence_score=pattern_info["confidence"],
                    attack_patterns=[AttackPattern.EXPLOITATION],
                    remediation=[
                        "Implement proper output encoding/escaping",
                        "Use Content Security Policy (CSP)",
                        "Validate and sanitize all user inputs",
                        "Use secure frameworks with built-in XSS protection"
                    ]
                )
        
        return None
    
    async def _scan_path_traversal(
        self,
        request: Request,
        url: str,
        headers: Dict[str, str]
    ) -> List[SecurityThreat]:
        """Scan for path traversal attempts"""
        threats = []
        
        # Scan URL path and parameters
        parsed_url = urlparse(url)
        
        # Check path
        threat = self._check_path_traversal_patterns(parsed_url.path, "URL path")
        if threat:
            threat.endpoint = parsed_url.path
            threat.source_ip = request.client.host if request.client else None
            threats.append(threat)
        
        # Check parameters
        if parsed_url.query:
            params = parse_qs(parsed_url.query)
            for param_name, param_values in params.items():
                for value in param_values:
                    threat = self._check_path_traversal_patterns(value, f"URL parameter: {param_name}")
                    if threat:
                        threat.endpoint = parsed_url.path
                        threat.source_ip = request.client.host if request.client else None
                        threats.append(threat)
        
        return threats
    
    def _check_path_traversal_patterns(self, content: str, location: str) -> Optional[SecurityThreat]:
        """Check content against path traversal patterns"""
        if not content:
            return None
        
        # Decode common encodings
        decoded_content = self._decode_common_encodings(content)
        
        for pattern_info in self.path_traversal_patterns:
            pattern = pattern_info["pattern"]
            flags = pattern_info.get("flags", 0)
            
            if re.search(pattern, decoded_content, flags):
                return SecurityThreat(
                    threat_id=self._generate_threat_id(),
                    threat_type=VulnerabilityType.PATH_TRAVERSAL,
                    threat_level=ThreatLevel.HIGH,
                    title="Path Traversal Attempt Detected",
                    description=f"Potential path traversal attack detected in {location}: {pattern_info['description']}",
                    evidence={
                        "pattern": pattern,
                        "matched_content": decoded_content[:200],
                        "original_content": content[:200],
                        "location": location,
                        "confidence": pattern_info["confidence"]
                    },
                    confidence_score=pattern_info["confidence"],
                    attack_patterns=[AttackPattern.EXPLOITATION],
                    remediation=[
                        "Implement proper input validation",
                        "Use allow-lists for file access",
                        "Sanitize file paths and names",
                        "Implement access controls on file system"
                    ]
                )
        
        return None
    
    async def _scan_command_injection(
        self,
        request: Request,
        url: str,
        headers: Dict[str, str],
        body: Optional[str]
    ) -> List[SecurityThreat]:
        """Scan for command injection attempts"""
        threats = []
        
        # Scan URL parameters
        parsed_url = urlparse(url)
        if parsed_url.query:
            params = parse_qs(parsed_url.query)
            for param_name, param_values in params.items():
                for value in param_values:
                    threat = self._check_command_injection_patterns(value, f"URL parameter: {param_name}")
                    if threat:
                        threat.endpoint = parsed_url.path
                        threat.source_ip = request.client.host if request.client else None
                        threats.append(threat)
        
        # Scan request body
        if body:
            threat = self._check_command_injection_patterns(body, "Request body")
            if threat:
                threat.endpoint = parsed_url.path
                threat.source_ip = request.client.host if request.client else None
                threats.append(threat)
        
        return threats
    
    def _check_command_injection_patterns(self, content: str, location: str) -> Optional[SecurityThreat]:
        """Check content against command injection patterns"""
        if not content:
            return None
        
        for pattern_info in self.command_injection_patterns:
            pattern = pattern_info["pattern"]
            flags = pattern_info.get("flags", 0)
            
            if re.search(pattern, content, flags):
                return SecurityThreat(
                    threat_id=self._generate_threat_id(),
                    threat_type=VulnerabilityType.COMMAND_INJECTION,
                    threat_level=ThreatLevel.CRITICAL,
                    title="Command Injection Attempt Detected",
                    description=f"Potential command injection detected in {location}: {pattern_info['description']}",
                    evidence={
                        "pattern": pattern,
                        "matched_content": content[:200],
                        "location": location,
                        "confidence": pattern_info["confidence"]
                    },
                    confidence_score=pattern_info["confidence"],
                    attack_patterns=[AttackPattern.EXPLOITATION, AttackPattern.PRIVILEGE_ESCALATION],
                    remediation=[
                        "Never execute user input as system commands",
                        "Use parameterized APIs instead of shell commands",
                        "Implement strict input validation",
                        "Apply principle of least privilege"
                    ]
                )
        
        return None
    
    async def _scan_bot_activity(
        self,
        request: Request,
        user_agent: str,
        ip_address: Optional[str]
    ) -> List[SecurityThreat]:
        """Scan for bot and automated tool activity"""
        threats = []
        
        if not user_agent:
            return threats
        
        # Check against bot patterns
        for pattern_info in self.bot_patterns:
            pattern = pattern_info["pattern"]
            flags = pattern_info.get("flags", 0)
            
            if re.search(pattern, user_agent, flags):
                threats.append(SecurityThreat(
                    threat_id=self._generate_threat_id(),
                    threat_type=VulnerabilityType.BOT_ATTACK,
                    threat_level=ThreatLevel.MEDIUM,
                    title="Bot Activity Detected",
                    description=f"Potential bot activity detected: {pattern_info['description']}",
                    evidence={
                        "user_agent": user_agent,
                        "pattern": pattern,
                        "confidence": pattern_info["confidence"]
                    },
                    source_ip=ip_address,
                    user_agent=user_agent,
                    confidence_score=pattern_info["confidence"],
                    attack_patterns=[AttackPattern.RECONNAISSANCE],
                    remediation=[
                        "Implement bot detection and blocking",
                        "Use CAPTCHAs for suspicious requests",
                        "Rate limit automated requests",
                        "Monitor for unusual request patterns"
                    ]
                ))
        
        # Check against known malicious user agents
        user_agent_lower = user_agent.lower()
        for suspicious_ua in self.suspicious_user_agents:
            if suspicious_ua in user_agent_lower:
                threats.append(SecurityThreat(
                    threat_id=self._generate_threat_id(),
                    threat_type=VulnerabilityType.SUSPICIOUS_ACTIVITY,
                    threat_level=ThreatLevel.HIGH,
                    title="Malicious Tool Detected",
                    description=f"Known security scanning tool detected: {suspicious_ua}",
                    evidence={
                        "user_agent": user_agent,
                        "malicious_tool": suspicious_ua
                    },
                    source_ip=ip_address,
                    user_agent=user_agent,
                    confidence_score=0.9,
                    attack_patterns=[AttackPattern.RECONNAISSANCE],
                    remediation=[
                        "Block known malicious user agents",
                        "Increase monitoring for this IP",
                        "Consider temporary IP blocking",
                        "Alert security team"
                    ]
                ))
        
        return threats
    
    async def _scan_brute_force(self, request: Request, ip_address: Optional[str]) -> List[SecurityThreat]:
        """Scan for brute force attacks"""
        threats = []
        
        if not ip_address:
            return threats
        
        # Track login attempts (simplified - would need more sophisticated tracking)
        path = request.url.path
        if any(endpoint in path for endpoint in ["/login", "/auth", "/signin", "/authenticate"]):
            current_time = datetime.utcnow()
            
            if ip_address not in self.attack_attempts:
                self.attack_attempts[ip_address] = []
            
            # Clean old attempts (last hour)
            self.attack_attempts[ip_address] = [
                attempt for attempt in self.attack_attempts[ip_address]
                if current_time - attempt < timedelta(hours=1)
            ]
            
            # Add current attempt
            self.attack_attempts[ip_address].append(current_time)
            
            # Check for brute force pattern
            recent_attempts = len(self.attack_attempts[ip_address])
            if recent_attempts > 10:  # More than 10 attempts in an hour
                threats.append(SecurityThreat(
                    threat_id=self._generate_threat_id(),
                    threat_type=VulnerabilityType.BRUTE_FORCE,
                    threat_level=ThreatLevel.HIGH,
                    title="Brute Force Attack Detected",
                    description=f"Excessive login attempts detected from {ip_address}",
                    evidence={
                        "attempts_count": recent_attempts,
                        "time_window": "1 hour",
                        "endpoint": path
                    },
                    source_ip=ip_address,
                    endpoint=path,
                    confidence_score=0.85,
                    attack_patterns=[AttackPattern.CREDENTIAL_ACCESS],
                    remediation=[
                        "Implement account lockout policies",
                        "Use CAPTCHA after failed attempts",
                        "Enable rate limiting on authentication endpoints",
                        "Consider temporary IP blocking"
                    ]
                ))
        
        return threats
    
    async def _scan_suspicious_headers(self, request: Request, headers: Dict[str, str]) -> List[SecurityThreat]:
        """Scan for suspicious headers"""
        threats = []
        
        # Check for missing security headers (for responses, but can indicate attack prep)
        suspicious_patterns = {
            "x-forwarded-for": r"^\s*$|localhost|127\.0\.0\.1|0\.0\.0\.0",
            "x-real-ip": r"^\s*$|localhost|127\.0\.0\.1|0\.0\.0\.0",
            "host": r"[<>\"'&]",  # XSS attempts in host header
        }
        
        for header_name, pattern in suspicious_patterns.items():
            if header_name in headers:
                header_value = headers[header_name]
                if re.search(pattern, header_value, re.IGNORECASE):
                    threats.append(SecurityThreat(
                        threat_id=self._generate_threat_id(),
                        threat_type=VulnerabilityType.SUSPICIOUS_ACTIVITY,
                        threat_level=ThreatLevel.MEDIUM,
                        title="Suspicious Header Detected",
                        description=f"Suspicious value in {header_name} header",
                        evidence={
                            "header_name": header_name,
                            "header_value": header_value,
                            "pattern": pattern
                        },
                        source_ip=request.client.host if request.client else None,
                        confidence_score=0.6,
                        attack_patterns=[AttackPattern.EXPLOITATION],
                        remediation=[
                            "Validate and sanitize header values",
                            "Implement header filtering",
                            "Monitor for header manipulation attempts"
                        ]
                    ))
        
        return threats
    
    async def _scan_rate_limiting(self, request: Request, ip_address: Optional[str]) -> List[SecurityThreat]:
        """Scan for rate limiting violations"""
        threats = []
        
        if not ip_address:
            return threats
        
        # This would integrate with actual rate limiting system
        # For now, just detect high-frequency requests
        current_time = datetime.utcnow()
        
        if ip_address not in self.attack_attempts:
            self.attack_attempts[ip_address] = []
        
        # Clean old attempts (last minute)
        self.attack_attempts[ip_address] = [
            attempt for attempt in self.attack_attempts[ip_address]
            if current_time - attempt < timedelta(minutes=1)
        ]
        
        # Add current attempt
        self.attack_attempts[ip_address].append(current_time)
        
        # Check for high-frequency requests
        recent_requests = len(self.attack_attempts[ip_address])
        if recent_requests > 60:  # More than 60 requests per minute
            threats.append(SecurityThreat(
                threat_id=self._generate_threat_id(),
                threat_type=VulnerabilityType.DDoS,
                threat_level=ThreatLevel.HIGH,
                title="High-Frequency Requests Detected",
                description=f"Excessive requests from {ip_address}",
                evidence={
                    "requests_count": recent_requests,
                    "time_window": "1 minute"
                },
                source_ip=ip_address,
                confidence_score=0.8,
                attack_patterns=[AttackPattern.IMPACT],
                remediation=[
                    "Implement rate limiting",
                    "Use DDoS protection services",
                    "Consider IP blocking",
                    "Scale infrastructure to handle load"
                ]
            ))
        
        return threats
    
    def _decode_common_encodings(self, content: str) -> str:
        """Decode common encodings used to bypass filters"""
        decoded = content
        
        try:
            # URL decode
            from urllib.parse import unquote
            decoded = unquote(decoded)
            
            # HTML entity decode
            import html
            decoded = html.unescape(decoded)
            
            # Base64 decode (if it looks like base64)
            if re.match(r'^[A-Za-z0-9+/]*={0,2}$', decoded) and len(decoded) % 4 == 0:
                try:
                    decoded_bytes = base64.b64decode(decoded)
                    decoded = decoded_bytes.decode('utf-8', errors='ignore')
                except Exception:
                    pass
            
        except Exception:
            pass
        
        return decoded
    
    def _generate_threat_id(self) -> str:
        """Generate unique threat ID"""
        timestamp = str(int(time.time() * 1000))
        random_part = hashlib.md5(f"{timestamp}{time.time()}".encode()).hexdigest()[:8]
        return f"THREAT-{timestamp}-{random_part}"
    
    async def perform_vulnerability_scan(self, target_url: str) -> SecurityScanResult:
        """Perform comprehensive vulnerability scan"""
        scan_id = f"SCAN-{int(time.time())}"
        started_at = datetime.utcnow()
        
        self.logger.info("Starting vulnerability scan", scan_id=scan_id, target=target_url)
        
        threats_detected = []
        total_checks = 0
        
        try:
            # Perform various vulnerability checks
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Basic connectivity check
                total_checks += 1
                response = await client.get(target_url)
                
                # Check for information disclosure
                threats_detected.extend(await self._check_information_disclosure(response))
                total_checks += 1
                
                # Check security headers
                threats_detected.extend(await self._check_security_headers(response))
                total_checks += 1
                
                # Check for common vulnerabilities
                threats_detected.extend(await self._check_common_vulnerabilities(client, target_url))
                total_checks += 5  # Multiple checks
        
        except Exception as e:
            self.logger.error("Vulnerability scan failed", scan_id=scan_id, error=str(e))
        
        completed_at = datetime.utcnow()
        scan_duration = (completed_at - started_at).total_seconds()
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(threats_detected)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(threats_detected)
        
        result = SecurityScanResult(
            scan_id=scan_id,
            target=target_url,
            scan_type="comprehensive",
            threats_detected=threats_detected,
            scan_duration=scan_duration,
            total_checks=total_checks,
            vulnerabilities_found=len(threats_detected),
            risk_score=risk_score,
            started_at=started_at,
            completed_at=completed_at,
            recommendations=recommendations
        )
        
        self.logger.info("Vulnerability scan completed",
                        scan_id=scan_id,
                        vulnerabilities_found=len(threats_detected),
                        risk_score=risk_score)
        
        return result
    
    async def _check_information_disclosure(self, response: httpx.Response) -> List[SecurityThreat]:
        """Check for information disclosure vulnerabilities"""
        threats = []
        
        # Check response headers for sensitive information
        sensitive_headers = [
            "server", "x-powered-by", "x-aspnet-version", "x-generator"
        ]
        
        for header in sensitive_headers:
            if header in response.headers:
                threats.append(SecurityThreat(
                    threat_id=self._generate_threat_id(),
                    threat_type=VulnerabilityType.INFORMATION_DISCLOSURE,
                    threat_level=ThreatLevel.LOW,
                    title="Information Disclosure in Headers",
                    description=f"Sensitive information exposed in {header} header",
                    evidence={
                        "header": header,
                        "value": response.headers[header]
                    },
                    confidence_score=0.7,
                    remediation=[
                        f"Remove or obfuscate {header} header",
                        "Configure web server to hide version information",
                        "Review all response headers for sensitive data"
                    ]
                ))
        
        return threats
    
    async def _check_security_headers(self, response: httpx.Response) -> List[SecurityThreat]:
        """Check for missing security headers"""
        threats = []
        
        required_headers = {
            "content-security-policy": "Missing Content Security Policy",
            "x-frame-options": "Missing X-Frame-Options",
            "x-content-type-options": "Missing X-Content-Type-Options",
            "strict-transport-security": "Missing Strict Transport Security",
            "x-xss-protection": "Missing XSS Protection"
        }
        
        for header, description in required_headers.items():
            if header not in response.headers:
                threats.append(SecurityThreat(
                    threat_id=self._generate_threat_id(),
                    threat_type=VulnerabilityType.INFORMATION_DISCLOSURE,
                    threat_level=ThreatLevel.MEDIUM,
                    title="Missing Security Header",
                    description=description,
                    evidence={
                        "missing_header": header
                    },
                    confidence_score=0.8,
                    remediation=[
                        f"Add {header} header to all responses",
                        "Review and implement comprehensive security headers",
                        "Use security header analyzers to verify configuration"
                    ]
                ))
        
        return threats
    
    async def _check_common_vulnerabilities(self, client: httpx.AsyncClient, base_url: str) -> List[SecurityThreat]:
        """Check for common web vulnerabilities"""
        threats = []
        
        # Test common vulnerable endpoints
        test_paths = [
            "/admin",
            "/debug",
            "/test",
            "/.env",
            "/config",
            "/backup",
            "/phpinfo.php",
            "/info.php"
        ]
        
        for path in test_paths:
            try:
                test_url = f"{base_url.rstrip('/')}{path}"
                response = await client.get(test_url)
                
                if response.status_code == 200:
                    threats.append(SecurityThreat(
                        threat_id=self._generate_threat_id(),
                        threat_type=VulnerabilityType.INFORMATION_DISCLOSURE,
                        threat_level=ThreatLevel.MEDIUM,
                        title="Accessible Sensitive Endpoint",
                        description=f"Potentially sensitive endpoint accessible: {path}",
                        evidence={
                            "endpoint": path,
                            "status_code": response.status_code,
                            "response_length": len(response.content)
                        },
                        confidence_score=0.6,
                        remediation=[
                            f"Secure or remove {path} endpoint",
                            "Implement proper access controls",
                            "Review all administrative interfaces"
                        ]
                    ))
            
            except Exception:
                continue  # Skip failed requests
        
        return threats
    
    def _calculate_risk_score(self, threats: List[SecurityThreat]) -> float:
        """Calculate overall risk score based on detected threats"""
        if not threats:
            return 0.0
        
        level_weights = {
            ThreatLevel.INFO: 1,
            ThreatLevel.LOW: 2,
            ThreatLevel.MEDIUM: 5,
            ThreatLevel.HIGH: 8,
            ThreatLevel.CRITICAL: 10
        }
        
        total_weight = sum(level_weights[threat.threat_level] for threat in threats)
        max_possible = len(threats) * level_weights[ThreatLevel.CRITICAL]
        
        return min(total_weight / max_possible * 100, 100.0) if max_possible > 0 else 0.0
    
    def _generate_recommendations(self, threats: List[SecurityThreat]) -> List[str]:
        """Generate security recommendations based on detected threats"""
        recommendations = set()
        
        threat_types = [threat.threat_type for threat in threats]
        
        if VulnerabilityType.SQL_INJECTION in threat_types:
            recommendations.add("Implement parameterized queries and input validation")
        
        if VulnerabilityType.XSS in threat_types:
            recommendations.add("Implement output encoding and Content Security Policy")
        
        if VulnerabilityType.PATH_TRAVERSAL in threat_types:
            recommendations.add("Implement proper file access controls and path validation")
        
        if VulnerabilityType.COMMAND_INJECTION in threat_types:
            recommendations.add("Avoid executing user input as system commands")
        
        if VulnerabilityType.BRUTE_FORCE in threat_types:
            recommendations.add("Implement account lockout and rate limiting")
        
        if VulnerabilityType.BOT_ATTACK in threat_types:
            recommendations.add("Implement bot detection and CAPTCHA protection")
        
        # General recommendations
        recommendations.add("Regularly update all software components")
        recommendations.add("Implement comprehensive logging and monitoring")
        recommendations.add("Conduct regular security assessments")
        recommendations.add("Implement Web Application Firewall (WAF)")
        
        return list(recommendations)
    
    def get_security_metrics(self) -> Dict[str, Any]:
        """Get security scanner metrics"""
        return {
            "threats_detected": self.threats_detected,
            "scans_performed": self.scans_performed,
            "false_positives": self.false_positives,
            "patterns_loaded": {
                "sql_injection": len(self.sql_injection_patterns),
                "xss": len(self.xss_patterns),
                "path_traversal": len(self.path_traversal_patterns),
                "command_injection": len(self.command_injection_patterns),
                "bot_patterns": len(self.bot_patterns)
            },
            "blocked_ips": len(self.blocked_ips),
            "tracked_ips": len(self.attack_attempts)
        }