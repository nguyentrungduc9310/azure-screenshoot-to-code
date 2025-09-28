#!/usr/bin/env python3
"""
Standalone test for vulnerability scanner
"""
import sys
import asyncio
import tempfile
from pathlib import Path

# Add current directory to path
sys.path.insert(0, '.')

# Import mock logger directly
import importlib.util
spec = importlib.util.spec_from_file_location("mock_logger", "app/cicd/mock_logger.py")
mock_logger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mock_logger)
MockStructuredLogger = mock_logger.MockStructuredLogger

# Import vulnerability scanner directly without package
spec = importlib.util.spec_from_file_location("vulnerability_scanner", "app/security/vulnerability_scanner.py")
vuln_scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vuln_scanner)

AdvancedVulnerabilityScanner = vuln_scanner.AdvancedVulnerabilityScanner
ScanConfiguration = vuln_scanner.ScanConfiguration
ScanType = vuln_scanner.ScanType
VulnerabilitySeverity = vuln_scanner.VulnerabilitySeverity

async def test_vulnerability_scanner():
    """Test vulnerability scanner functionality"""
    
    # Create logger
    logger = MockStructuredLogger("test-scanner")
    
    # Create configuration
    config = ScanConfiguration(
        enabled_scan_types={ScanType.SAST, ScanType.SECRETS},
        max_scan_duration_minutes=10,
        parallel_scans=False,
        fail_on_critical=True
    )
    
    # Create scanner
    scanner = AdvancedVulnerabilityScanner(logger, config)
    
    # Create test project
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir)
        
        # Create test file with vulnerability
        test_file = project_path / "test.py"
        test_file.write_text("""
# Test file with security issues
API_KEY = "sk-1234567890abcdef"  # Hardcoded secret
def vulnerable_function(user_input):
    query = f"SELECT * FROM users WHERE name = '{user_input}'"  # SQL injection
    return query
""")
        
        print(f"Created test project at: {project_path}")
        
        # Run scan
        print("Running security scan...")
        scan_results = await scanner.scan_application(
            str(project_path),
            {ScanType.SAST, ScanType.SECRETS}
        )
        
        # Print results
        print(f"\nScan completed. Found {len(scan_results)} scan types:")
        
        for scan_type, result in scan_results.items():
            print(f"\n{scan_type.value} scan:")
            print(f"  Status: {result.status}")
            print(f"  Duration: {result.duration_seconds:.2f}s")
            print(f"  Vulnerabilities found: {len(result.vulnerabilities)}")
            
            for vuln in result.vulnerabilities:
                print(f"    - {vuln.title} ({vuln.severity.value})")
                print(f"      File: {vuln.file_path}:{vuln.line_number}")
        
        # Generate report
        print("\nGenerating report...")
        report = scanner.generate_scan_report(scan_results)
        
        print(f"Risk Assessment:")
        print(f"  Risk Level: {report['risk_assessment'].get('risk_level', 'Unknown')}")
        print(f"  Risk Score: {report['risk_assessment'].get('risk_score', 0):.1f}")
        print(f"  Total Vulnerabilities: {report['summary']['total_vulnerabilities']}")
        print(f"  Critical: {report['summary']['critical']}")
        print(f"  High: {report['summary']['high']}")
        print(f"  Medium: {report['summary']['medium']}")
        
        # Print some vulnerabilities
        print(f"\nTop Vulnerabilities:")
        for vuln in report['vulnerabilities'][:3]:
            print(f"  - {vuln['title']} ({vuln['severity']})")
            print(f"    {vuln['description']}")
            if vuln.get('remediation'):
                print(f"    Remediation: {vuln['remediation']}")
        
        print(f"\n✓ Vulnerability scanner test completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_vulnerability_scanner())