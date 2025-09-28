#!/usr/bin/env python3
"""
Test runner script for API Gateway service
Provides comprehensive testing with reporting and coverage
"""
import os
import sys
import subprocess
import argparse
import time
from pathlib import Path
from typing import List, Dict, Any
import json


class TestRunner:
    """Comprehensive test runner for API Gateway"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.test_results = {}
        self.start_time = None
        self.end_time = None
    
    def run_unit_tests(self, verbose: bool = False, coverage: bool = True) -> Dict[str, Any]:
        """Run unit tests with optional coverage"""
        print("🧪 Running unit tests...")
        
        cmd = ["python", "-m", "pytest"]
        
        if verbose:
            cmd.append("-v")
        
        if coverage:
            cmd.extend([
                "--cov=app",
                "--cov-report=html:htmlcov",
                "--cov-report=xml:coverage.xml",
                "--cov-report=term-missing"
            ])
        
        cmd.extend([
            "--tb=short",
            "--junitxml=test-results.xml",
            "tests/"
        ])
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            return {
                "command": " ".join(cmd),
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0
            }
        
        except subprocess.TimeoutExpired:
            return {
                "command": " ".join(cmd),
                "returncode": -1,
                "stdout": "",
                "stderr": "Tests timed out after 5 minutes",
                "success": False
            }
        except Exception as e:
            return {
                "command": " ".join(cmd),
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "success": False
            }
    
    def run_linting(self) -> Dict[str, Any]:
        """Run code linting checks"""
        print("🔍 Running code linting...")
        
        results = {}
        
        # Flake8 linting
        flake8_cmd = ["python", "-m", "flake8", "app/", "tests/", "--max-line-length=100"]
        try:
            result = subprocess.run(flake8_cmd, cwd=self.project_root, capture_output=True, text=True)
            results["flake8"] = {
                "success": result.returncode == 0,
                "output": result.stdout + result.stderr
            }
        except Exception as e:
            results["flake8"] = {"success": False, "output": str(e)}
        
        # Black formatting check
        black_cmd = ["python", "-m", "black", "--check", "--diff", "app/", "tests/"]
        try:
            result = subprocess.run(black_cmd, cwd=self.project_root, capture_output=True, text=True)
            results["black"] = {
                "success": result.returncode == 0,
                "output": result.stdout + result.stderr
            }
        except Exception as e:
            results["black"] = {"success": False, "output": str(e)}
        
        # isort import sorting check
        isort_cmd = ["python", "-m", "isort", "--check-only", "--diff", "app/", "tests/"]
        try:
            result = subprocess.run(isort_cmd, cwd=self.project_root, capture_output=True, text=True)
            results["isort"] = {
                "success": result.returncode == 0,
                "output": result.stdout + result.stderr
            }
        except Exception as e:
            results["isort"] = {"success": False, "output": str(e)}
        
        return results
    
    def run_type_checking(self) -> Dict[str, Any]:
        """Run type checking with mypy"""
        print("🔧 Running type checking...")
        
        cmd = ["python", "-m", "mypy", "app/", "--ignore-missing-imports"]
        
        try:
            result = subprocess.run(cmd, cwd=self.project_root, capture_output=True, text=True)
            return {
                "success": result.returncode == 0,
                "output": result.stdout + result.stderr
            }
        except Exception as e:
            return {"success": False, "output": str(e)}
    
    def run_security_checks(self) -> Dict[str, Any]:
        """Run security vulnerability checks"""
        print("🔒 Running security checks...")
        
        results = {}
        
        # Safety check for known vulnerabilities
        safety_cmd = ["python", "-m", "safety", "check", "--json"]
        try:
            result = subprocess.run(safety_cmd, cwd=self.project_root, capture_output=True, text=True)
            results["safety"] = {
                "success": result.returncode == 0,
                "output": result.stdout + result.stderr
            }
        except Exception as e:
            results["safety"] = {"success": False, "output": str(e)}
        
        # Bandit security linting
        bandit_cmd = ["python", "-m", "bandit", "-r", "app/", "-f", "json"]
        try:
            result = subprocess.run(bandit_cmd, cwd=self.project_root, capture_output=True, text=True)
            results["bandit"] = {
                "success": result.returncode == 0,
                "output": result.stdout + result.stderr
            }
        except Exception as e:
            results["bandit"] = {"success": False, "output": str(e)}
        
        return results
    
    def generate_test_report(self) -> str:
        """Generate comprehensive test report"""
        report = []
        report.append("=" * 80)
        report.append("API GATEWAY TEST REPORT")
        report.append("=" * 80)
        report.append(f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if self.start_time and self.end_time:
            duration = self.end_time - self.start_time
            report.append(f"Total duration: {duration:.2f} seconds")
        
        report.append("")
        
        # Unit Tests Results
        if "unit_tests" in self.test_results:
            unit_results = self.test_results["unit_tests"]
            report.append("📋 UNIT TESTS")
            report.append("-" * 40)
            report.append(f"Status: {'✅ PASSED' if unit_results['success'] else '❌ FAILED'}")
            
            if unit_results["stdout"]:
                report.append("\nOutput:")
                report.append(unit_results["stdout"])
            
            if unit_results["stderr"]:
                report.append("\nErrors:")
                report.append(unit_results["stderr"])
            report.append("")
        
        # Linting Results
        if "linting" in self.test_results:
            lint_results = self.test_results["linting"]
            report.append("🔍 CODE LINTING")
            report.append("-" * 40)
            
            for tool, result in lint_results.items():
                status = "✅ PASSED" if result["success"] else "❌ FAILED"
                report.append(f"{tool.upper()}: {status}")
                
                if not result["success"] and result["output"]:
                    report.append(f"  Issues found:")
                    for line in result["output"].split("\n")[:10]:  # Show first 10 lines
                        if line.strip():
                            report.append(f"    {line}")
            report.append("")
        
        # Type Checking Results
        if "type_checking" in self.test_results:
            type_results = self.test_results["type_checking"]
            report.append("🔧 TYPE CHECKING")
            report.append("-" * 40)
            report.append(f"Status: {'✅ PASSED' if type_results['success'] else '❌ FAILED'}")
            
            if not type_results["success"] and type_results["output"]:
                report.append("\nType errors:")
                for line in type_results["output"].split("\n")[:10]:
                    if line.strip():
                        report.append(f"  {line}")
            report.append("")
        
        # Security Results
        if "security" in self.test_results:
            sec_results = self.test_results["security"]
            report.append("🔒 SECURITY CHECKS")
            report.append("-" * 40)
            
            for tool, result in sec_results.items():
                status = "✅ PASSED" if result["success"] else "❌ FAILED"
                report.append(f"{tool.upper()}: {status}")
                
                if not result["success"] and result["output"]:
                    report.append(f"  Issues found:")
                    # Try to parse JSON output for better formatting
                    try:
                        if tool == "safety" and result["output"].strip().startswith("["):
                            issues = json.loads(result["output"])
                            for issue in issues[:5]:  # Show first 5 issues
                                report.append(f"    {issue.get('package', 'Unknown')}: {issue.get('advisory', 'Security issue')}")
                    except:
                        # Fallback to raw output
                        for line in result["output"].split("\n")[:5]:
                            if line.strip():
                                report.append(f"    {line}")
            report.append("")
        
        # Summary
        report.append("📊 SUMMARY")
        report.append("-" * 40)
        
        all_success = True
        for category, results in self.test_results.items():
            if isinstance(results, dict):
                if "success" in results:
                    if not results["success"]:
                        all_success = False
                else:
                    # For nested results like linting
                    for tool_result in results.values():
                        if not tool_result.get("success", True):
                            all_success = False
        
        report.append(f"Overall Status: {'✅ ALL CHECKS PASSED' if all_success else '❌ SOME CHECKS FAILED'}")
        
        if not all_success:
            report.append("\n⚠️  Please fix the issues above before deploying to production.")
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def run_all_tests(self, args) -> bool:
        """Run all test suites"""
        print("🚀 Starting comprehensive test suite...")
        print(f"Project root: {self.project_root}")
        print("")
        
        self.start_time = time.time()
        
        # Run unit tests
        self.test_results["unit_tests"] = self.run_unit_tests(
            verbose=args.verbose,
            coverage=args.coverage
        )
        
        # Run linting (if not skipped)
        if not args.skip_lint:
            self.test_results["linting"] = self.run_linting()
        
        # Run type checking (if not skipped)
        if not args.skip_types:
            self.test_results["type_checking"] = self.run_type_checking()
        
        # Run security checks (if not skipped)
        if not args.skip_security:
            self.test_results["security"] = self.run_security_checks()
        
        self.end_time = time.time()
        
        # Generate and save report
        report = self.generate_test_report()
        
        if args.report_file:
            with open(args.report_file, "w") as f:
                f.write(report)
            print(f"📄 Test report saved to: {args.report_file}")
        
        if not args.quiet:
            print(report)
        
        # Determine overall success
        all_success = True
        for category, results in self.test_results.items():
            if isinstance(results, dict):
                if "success" in results:
                    if not results["success"]:
                        all_success = False
                        break
                else:
                    # For nested results
                    for tool_result in results.values():
                        if not tool_result.get("success", True):
                            all_success = False
                            break
            if not all_success:
                break
        
        return all_success


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Comprehensive test runner for API Gateway")
    
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose test output")
    parser.add_argument("--no-coverage", dest="coverage", action="store_false", help="Skip coverage report")
    parser.add_argument("--skip-lint", action="store_true", help="Skip linting checks")
    parser.add_argument("--skip-types", action="store_true", help="Skip type checking")
    parser.add_argument("--skip-security", action="store_true", help="Skip security checks")
    parser.add_argument("--quiet", "-q", action="store_true", help="Quiet output (only report file)")
    parser.add_argument("--report-file", default="test-report.txt", help="Test report output file")
    
    args = parser.parse_args()
    
    # Find project root
    current_dir = Path(__file__).parent.parent
    if not (current_dir / "app").exists():
        print("❌ Error: Could not find project root (missing 'app' directory)")
        sys.exit(1)
    
    # Create test runner and run tests
    runner = TestRunner(current_dir)
    success = runner.run_all_tests(args)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()