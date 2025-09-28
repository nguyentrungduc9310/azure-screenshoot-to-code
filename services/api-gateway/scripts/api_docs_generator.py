#!/usr/bin/env python3
"""
API Documentation Generator
Generates comprehensive API documentation with examples and interactive testing
"""
import os
import sys
import json
import yaml
from pathlib import Path
from typing import Dict, Any, List
import subprocess
import requests
import time


class APIDocumentationGenerator:
    """Generate comprehensive API documentation"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.base_url = "http://localhost:8000"
        self.api_prefix = "/api/v1"
    
    def start_test_server(self) -> subprocess.Popen:
        """Start the API server for documentation generation"""
        print("🚀 Starting API server...")
        
        env = os.environ.copy()
        env.update({
            "ENVIRONMENT": "testing",
            "ENABLE_AUTHENTICATION": "false",
            "ENABLE_RATE_LIMITING": "false",
            "ENABLE_SWAGGER_UI": "true",
            "LOG_LEVEL": "WARNING"  # Reduce noise
        })
        
        cmd = [
            "uvicorn", "app.main:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload", "false"
        ]
        
        process = subprocess.Popen(
            cmd,
            cwd=self.project_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait for server to start
        for _ in range(30):  # Wait up to 30 seconds
            try:
                response = requests.get(f"{self.base_url}/health", timeout=1)
                if response.status_code == 200:
                    print("✅ API server started successfully")
                    return process
            except:
                time.sleep(1)
        
        process.terminate()
        raise RuntimeError("Failed to start API server")
    
    def fetch_openapi_spec(self) -> Dict[str, Any]:
        """Fetch OpenAPI specification from running server"""
        print("📋 Fetching OpenAPI specification...")
        
        try:
            response = requests.get(f"{self.base_url}/openapi.json", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise RuntimeError(f"Failed to fetch OpenAPI spec: {e}")
    
    def generate_markdown_docs(self, openapi_spec: Dict[str, Any]) -> str:
        """Generate markdown documentation from OpenAPI spec"""
        print("📝 Generating Markdown documentation...")
        
        docs = []
        docs.append("# API Gateway Documentation")
        docs.append("")
        docs.append("Auto-generated API documentation from OpenAPI specification.")
        docs.append("")
        
        # Info section
        info = openapi_spec.get("info", {})
        docs.append(f"**Version**: {info.get('version', 'Unknown')}")
        docs.append(f"**Description**: {info.get('description', 'No description')}")
        docs.append("")
        
        # Servers
        servers = openapi_spec.get("servers", [])
        if servers:
            docs.append("## Servers")
            docs.append("")
            for server in servers:
                docs.append(f"- **{server.get('description', 'Default')}**: `{server.get('url', 'Unknown')}`")
            docs.append("")
        
        # Security
        security_schemes = openapi_spec.get("components", {}).get("securitySchemes", {})
        if security_schemes:
            docs.append("## Authentication")
            docs.append("")
            for scheme_name, scheme in security_schemes.items():
                docs.append(f"### {scheme_name}")
                docs.append(f"**Type**: {scheme.get('type', 'Unknown')}")
                if scheme.get("scheme"):
                    docs.append(f"**Scheme**: {scheme.get('scheme')}")
                if scheme.get("bearerFormat"):
                    docs.append(f"**Format**: {scheme.get('bearerFormat')}")
                docs.append("")
        
        # Paths
        paths = openapi_spec.get("paths", {})
        if paths:
            docs.append("## Endpoints")
            docs.append("")
            
            # Group paths by tags
            paths_by_tag = {}
            for path, methods in paths.items():
                for method, spec in methods.items():
                    if method in ["get", "post", "put", "delete", "patch"]:
                        tags = spec.get("tags", ["Untagged"])
                        tag = tags[0] if tags else "Untagged"
                        
                        if tag not in paths_by_tag:
                            paths_by_tag[tag] = []
                        
                        paths_by_tag[tag].append({
                            "path": path,
                            "method": method.upper(),
                            "spec": spec
                        })
            
            # Generate documentation for each tag
            for tag, endpoints in paths_by_tag.items():
                docs.append(f"### {tag}")
                docs.append("")
                
                for endpoint in endpoints:
                    path = endpoint["path"]
                    method = endpoint["method"]
                    spec = endpoint["spec"]
                    
                    docs.append(f"#### {method} {path}")
                    docs.append("")
                    
                    # Description
                    if spec.get("summary"):
                        docs.append(f"**{spec['summary']}**")
                        docs.append("")
                    
                    if spec.get("description"):
                        docs.append(spec["description"])
                        docs.append("")
                    
                    # Parameters
                    parameters = spec.get("parameters", [])
                    if parameters:
                        docs.append("**Parameters:**")
                        docs.append("")
                        for param in parameters:
                            name = param.get("name", "unknown")
                            location = param.get("in", "unknown")
                            required = " *(required)*" if param.get("required") else ""
                            description = param.get("description", "No description")
                            docs.append(f"- `{name}` ({location}){required}: {description}")
                        docs.append("")
                    
                    # Request body
                    request_body = spec.get("requestBody")
                    if request_body:
                        docs.append("**Request Body:**")
                        docs.append("")
                        content = request_body.get("content", {})
                        for content_type, schema_info in content.items():
                            docs.append(f"Content-Type: `{content_type}`")
                            docs.append("")
                            
                            # Try to show example
                            example = schema_info.get("example")
                            if example:
                                docs.append("```json")
                                docs.append(json.dumps(example, indent=2))
                                docs.append("```")
                                docs.append("")
                    
                    # Responses
                    responses = spec.get("responses", {})
                    if responses:
                        docs.append("**Responses:**")
                        docs.append("")
                        for status_code, response_spec in responses.items():
                            description = response_spec.get("description", "No description")
                            docs.append(f"- `{status_code}`: {description}")
                        docs.append("")
                    
                    docs.append("---")
                    docs.append("")
        
        return "\n".join(docs)
    
    def generate_curl_examples(self, openapi_spec: Dict[str, Any]) -> str:
        """Generate cURL examples for API endpoints"""
        print("💻 Generating cURL examples...")
        
        examples = []
        examples.append("# API Gateway cURL Examples")
        examples.append("")
        examples.append("Collection of cURL examples for testing the API Gateway endpoints.")
        examples.append("")
        
        paths = openapi_spec.get("paths", {})
        
        for path, methods in paths.items():
            for method, spec in methods.items():
                if method in ["get", "post", "put", "delete", "patch"]:
                    examples.append(f"## {method.upper()} {path}")
                    examples.append("")
                    
                    if spec.get("summary"):
                        examples.append(f"**{spec['summary']}**")
                        examples.append("")
                    
                    # Build cURL command
                    curl_cmd = [f"curl -X {method.upper()}"]
                    curl_cmd.append(f'"{self.base_url}{path}"')
                    
                    # Add headers
                    headers = ['-H "Content-Type: application/json"']
                    
                    # Add auth if required
                    security = spec.get("security", [])
                    if security:
                        headers.append('-H "Authorization: Bearer YOUR_TOKEN"')
                    
                    # Add request body example
                    request_body = spec.get("requestBody")
                    if request_body:
                        content = request_body.get("content", {})
                        json_content = content.get("application/json")
                        if json_content and json_content.get("example"):
                            body_json = json.dumps(json_content["example"], separators=(',', ':'))
                            curl_cmd.append(f"-d '{body_json}'")
                    
                    # Combine command
                    full_cmd = " \\\n  ".join(curl_cmd + headers)
                    
                    examples.append("```bash")
                    examples.append(full_cmd)
                    examples.append("```")
                    examples.append("")
        
        return "\n".join(examples)
    
    def test_endpoints(self) -> Dict[str, Any]:
        """Test key endpoints and collect response examples"""
        print("🧪 Testing endpoints and collecting examples...")
        
        test_results = {}
        
        # Test health endpoints
        health_endpoints = [
            "/health",
            "/health/live",
            "/health/ready",
            "/health/detailed"
        ]
        
        for endpoint in health_endpoints:
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=5)
                test_results[endpoint] = {
                    "status_code": response.status_code,
                    "response": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
                    "headers": dict(response.headers)
                }
            except Exception as e:
                test_results[endpoint] = {
                    "error": str(e)
                }
        
        # Test other endpoints (they might fail due to downstream services)
        other_endpoints = [
            ("/api/v1/code/variants", "GET"),
            ("/api/v1/images/providers", "GET")
        ]
        
        for endpoint, method in other_endpoints:
            try:
                if method == "GET":
                    response = requests.get(f"{self.base_url}{endpoint}", timeout=5)
                else:
                    response = requests.post(f"{self.base_url}{endpoint}", timeout=5)
                
                test_results[endpoint] = {
                    "status_code": response.status_code,
                    "response": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text[:500],
                    "headers": dict(response.headers)
                }
            except Exception as e:
                test_results[endpoint] = {
                    "error": str(e)
                }
        
        return test_results
    
    def generate_test_report(self, test_results: Dict[str, Any]) -> str:
        """Generate endpoint testing report"""
        report = []
        report.append("# API Endpoint Test Report")
        report.append("")
        report.append(f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        for endpoint, result in test_results.items():
            report.append(f"## {endpoint}")
            report.append("")
            
            if "error" in result:
                report.append(f"❌ **Error**: {result['error']}")
            else:
                status = result["status_code"]
                status_emoji = "✅" if 200 <= status < 300 else "⚠️" if 400 <= status < 500 else "❌"
                report.append(f"{status_emoji} **Status**: {status}")
                
                # Show response (truncated)
                if "response" in result:
                    response_str = json.dumps(result["response"], indent=2) if isinstance(result["response"], dict) else str(result["response"])
                    if len(response_str) > 1000:
                        response_str = response_str[:1000] + "..."
                    
                    report.append("")
                    report.append("**Response:**")
                    report.append("```json")
                    report.append(response_str)
                    report.append("```")
                
                # Show key headers
                if "headers" in result:
                    interesting_headers = ["content-type", "x-correlation-id", "x-response-time", "x-ratelimit-limit"]
                    found_headers = {k: v for k, v in result["headers"].items() if k.lower() in interesting_headers}
                    
                    if found_headers:
                        report.append("")
                        report.append("**Headers:**")
                        for header, value in found_headers.items():
                            report.append(f"- `{header}`: {value}")
            
            report.append("")
            report.append("---")
            report.append("")
        
        return "\n".join(report)
    
    def generate_all_documentation(self, output_dir: Path):
        """Generate all documentation files"""
        print("📚 Generating comprehensive API documentation...")
        
        output_dir.mkdir(exist_ok=True)
        
        # Start server
        server_process = None
        try:
            server_process = self.start_test_server()
            
            # Fetch OpenAPI spec
            openapi_spec = self.fetch_openapi_spec()
            
            # Save OpenAPI spec
            with open(output_dir / "openapi.json", "w") as f:
                json.dump(openapi_spec, f, indent=2)
            
            # Save OpenAPI spec as YAML
            with open(output_dir / "openapi.yaml", "w") as f:
                yaml.dump(openapi_spec, f, default_flow_style=False)
            
            # Generate markdown docs
            markdown_docs = self.generate_markdown_docs(openapi_spec)
            with open(output_dir / "api-reference.md", "w") as f:
                f.write(markdown_docs)
            
            # Generate cURL examples
            curl_examples = self.generate_curl_examples(openapi_spec)
            with open(output_dir / "curl-examples.md", "w") as f:
                f.write(curl_examples)
            
            # Test endpoints and generate report
            test_results = self.test_endpoints()
            test_report = self.generate_test_report(test_results)
            with open(output_dir / "endpoint-test-report.md", "w") as f:
                f.write(test_report)
            
            print(f"✅ Documentation generated successfully in: {output_dir}")
            print(f"📄 Files created:")
            print(f"  - openapi.json - OpenAPI specification (JSON)")
            print(f"  - openapi.yaml - OpenAPI specification (YAML)")
            print(f"  - api-reference.md - Complete API reference")
            print(f"  - curl-examples.md - cURL command examples")
            print(f"  - endpoint-test-report.md - Endpoint testing report")
            
        finally:
            if server_process:
                server_process.terminate()
                server_process.wait()
                print("🛑 API server stopped")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate comprehensive API documentation")
    parser.add_argument("--output-dir", "-o", default="docs/generated", help="Output directory for documentation")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL for API server")
    
    args = parser.parse_args()
    
    # Find project root
    current_dir = Path(__file__).parent.parent
    if not (current_dir / "app").exists():
        print("❌ Error: Could not find project root (missing 'app' directory)")
        sys.exit(1)
    
    # Create generator and generate docs
    generator = APIDocumentationGenerator(current_dir)
    generator.base_url = args.base_url
    
    output_path = current_dir / args.output_dir
    
    try:
        generator.generate_all_documentation(output_path)
    except Exception as e:
        print(f"❌ Error generating documentation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()