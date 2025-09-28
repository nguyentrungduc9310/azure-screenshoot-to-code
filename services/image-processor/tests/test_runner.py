"""
Test runner and configuration for Image Processor integration tests
Provides comprehensive test execution with reporting and categorization
"""
import pytest
import sys
import os
from typing import Dict, List, Optional
import argparse
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class TestRunner:
    """Comprehensive test runner for Image Processor service"""
    
    def __init__(self):
        self.test_categories = {
            "unit": {
                "description": "Unit tests for individual components",
                "path": "tests/unit/",
                "markers": ["unit"],
                "timeout": 30
            },
            "integration": {
                "description": "Integration tests for API endpoints",
                "path": "tests/integration/test_api_endpoints.py",
                "markers": ["integration"],
                "timeout": 60
            },
            "e2e": {
                "description": "End-to-end workflow tests",
                "path": "tests/integration/test_e2e_workflows.py",
                "markers": ["e2e"],
                "timeout": 120
            },
            "performance": {
                "description": "Performance and load testing",
                "path": "tests/integration/test_performance.py",
                "markers": ["performance"],
                "timeout": 300
            },
            "security": {
                "description": "Security and authentication tests",
                "path": "tests/integration/test_security.py", 
                "markers": ["security"],
                "timeout": 60
            },
            "compatibility": {
                "description": "Provider compatibility tests",
                "path": "tests/integration/test_provider_compatibility.py",
                "markers": ["compatibility"],
                "timeout": 120
            }
        }
    
    def run_category(self, category: str, verbose: bool = False, coverage: bool = False) -> int:
        """Run tests for a specific category"""
        
        if category not in self.test_categories:
            print(f"Unknown test category: {category}")
            print(f"Available categories: {', '.join(self.test_categories.keys())}")
            return 1
        
        config = self.test_categories[category]
        
        print(f"\n{'='*60}")
        print(f"Running {category.upper()} tests")
        print(f"Description: {config['description']}")
        print(f"Path: {config['path']}")
        print(f"{'='*60}\n")
        
        # Build pytest arguments
        args = [
            config["path"],
            f"--timeout={config['timeout']}",
            "--tb=short",
            "-v" if verbose else "-q"
        ]
        
        # Add markers
        if config["markers"]:
            args.extend(["-m", " or ".join(config["markers"])])
        
        # Add coverage if requested
        if coverage:
            args.extend([
                "--cov=app",
                "--cov-report=term-missing",
                "--cov-report=html:htmlcov",
                "--cov-fail-under=80"
            ])
        
        # Run pytest
        return pytest.main(args)
    
    def run_all(self, exclude: Optional[List[str]] = None, verbose: bool = False, coverage: bool = False) -> Dict[str, int]:
        """Run all test categories"""
        
        exclude = exclude or []
        results = {}
        
        print(f"\n{'='*60}")
        print("Running ALL Image Processor Tests")
        print(f"{'='*60}")
        
        for category in self.test_categories:
            if category in exclude:
                print(f"\nSkipping {category} tests (excluded)")
                results[category] = -1  # Skipped
                continue
                
            result = self.run_category(category, verbose=verbose, coverage=False)  # Coverage only on final run
            results[category] = result
            
            if result != 0:
                print(f"\n❌ {category.upper()} tests FAILED (exit code: {result})")
            else:
                print(f"\n✅ {category.upper()} tests PASSED")
        
        # Summary
        print(f"\n{'='*60}")
        print("TEST SUMMARY")
        print(f"{'='*60}")
        
        passed = sum(1 for r in results.values() if r == 0)
        failed = sum(1 for r in results.values() if r > 0)
        skipped = sum(1 for r in results.values() if r < 0)
        
        for category, result in results.items():
            if result == 0:
                status = "✅ PASSED"
            elif result > 0:
                status = f"❌ FAILED (code: {result})"
            else:
                status = "⏭️  SKIPPED"
            
            print(f"{category.ljust(15)}: {status}")
        
        print(f"\nTotal: {len(results)} categories")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Skipped: {skipped}")
        
        # Generate coverage report if requested and all tests passed
        if coverage and failed == 0:
            print(f"\nGenerating coverage report...")
            coverage_result = pytest.main([
                "tests/",
                "--cov=app",
                "--cov-report=html:htmlcov",
                "--cov-report=term-missing",
                "--cov-fail-under=80",
                "--quiet"
            ])
            
            if coverage_result == 0:
                print("✅ Coverage report generated in htmlcov/")
            else:
                print("❌ Coverage report generation failed")
        
        return results
    
    def run_smoke_tests(self) -> int:
        """Run quick smoke tests to verify basic functionality"""
        
        print(f"\n{'='*60}")
        print("Running SMOKE tests")
        print(f"{'='*60}")
        
        # Run basic health and validation tests
        args = [
            "tests/integration/test_api_endpoints.py::TestImageProcessorAPI::test_health_check",
            "tests/integration/test_api_endpoints.py::TestImageProcessorAPI::test_health_ready",
            "tests/integration/test_api_endpoints.py::TestImageProcessorAPI::test_capabilities_endpoint",
            "tests/integration/test_api_endpoints.py::TestImageProcessorAPI::test_get_providers",
            "--timeout=30",
            "-v"
        ]
        
        return pytest.main(args)
    
    def generate_test_report(self, output_file: str = "test_report.html") -> None:
        """Generate comprehensive test report"""
        
        print(f"\nGenerating comprehensive test report...")
        
        args = [
            "tests/",
            f"--html={output_file}",
            "--self-contained-html",
            "--tb=short",
            "-v"
        ]
        
        result = pytest.main(args)
        
        if result == 0:
            print(f"✅ Test report generated: {output_file}")
        else:
            print(f"❌ Test report generation failed")
    
    def list_tests(self, category: Optional[str] = None) -> None:
        """List available tests"""
        
        if category:
            if category not in self.test_categories:
                print(f"Unknown category: {category}")
                return
            
            config = self.test_categories[category]
            print(f"\nTests in {category.upper()} category:")
            print(f"Path: {config['path']}")
            print(f"Description: {config['description']}")
            
            # List specific tests
            args = [config["path"], "--collect-only", "-q"]
            pytest.main(args)
        else:
            print("\nAvailable test categories:")
            print("-" * 40)
            
            for cat, config in self.test_categories.items():
                print(f"{cat.ljust(15)}: {config['description']}")
                print(f"{''.ljust(15)}  Path: {config['path']}")
                print(f"{''.ljust(15)}  Timeout: {config['timeout']}s")
                print()

def main():
    """Main entry point for test runner"""
    
    parser = argparse.ArgumentParser(description="Image Processor Test Runner")
    
    parser.add_argument(
        "command",
        choices=["run", "all", "smoke", "list", "report"],
        help="Command to execute"
    )
    
    parser.add_argument(
        "category",
        nargs="?",
        choices=["unit", "integration", "e2e", "performance", "security", "compatibility"],
        help="Test category to run (for 'run' command)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    
    parser.add_argument(
        "--coverage", "-c",
        action="store_true",
        help="Generate coverage report"
    )
    
    parser.add_argument(
        "--exclude",
        nargs="*",
        choices=["unit", "integration", "e2e", "performance", "security", "compatibility"],
        help="Categories to exclude (for 'all' command)"
    )
    
    parser.add_argument(
        "--output", "-o",
        default="test_report.html",
        help="Output file for report command"
    )
    
    args = parser.parse_args()
    
    runner = TestRunner()
    
    if args.command == "run":
        if not args.category:
            print("Error: Category required for 'run' command")
            parser.print_help()
            return 1
        
        return runner.run_category(args.category, verbose=args.verbose, coverage=args.coverage)
    
    elif args.command == "all":
        results = runner.run_all(exclude=args.exclude, verbose=args.verbose, coverage=args.coverage)
        # Return non-zero if any tests failed
        return max(results.values()) if results.values() else 0
    
    elif args.command == "smoke":
        return runner.run_smoke_tests()
    
    elif args.command == "list":
        runner.list_tests(args.category)
        return 0
    
    elif args.command == "report":
        runner.generate_test_report(args.output)
        return 0
    
    else:
        parser.print_help()
        return 1

if __name__ == "__main__":
    sys.exit(main())