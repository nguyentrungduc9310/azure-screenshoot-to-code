#!/usr/bin/env python3
"""
Automated Copilot Studio Agent Deployment Script
Command-line tool for deploying and managing Screenshot-to-Code agents
"""
import asyncio
import argparse
import json
import os
import sys
from typing import Dict, Any, Optional
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from app.copilot.agent_deployer import (
    CopilotStudioAgentDeployer, DeploymentConfig, DeploymentEnvironment
)
from shared.monitoring.structured_logger import StructuredLogger


class AgentDeploymentCLI:
    """Command-line interface for agent deployment"""
    
    def __init__(self):
        self.logger = StructuredLogger(service_name="agent-deployment-cli")
        self.deployer: Optional[CopilotStudioAgentDeployer] = None
        
    async def setup(self):
        """Initialize the deployment components"""
        self.deployer = CopilotStudioAgentDeployer(self.logger)
        await self.deployer.start()
    
    async def cleanup(self):
        """Clean up resources"""
        if self.deployer:
            await self.deployer.stop()
    
    def load_config_from_file(self, config_file: str) -> Dict[str, Any]:
        """Load deployment configuration from JSON file"""
        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            # Validate required fields
            required_fields = [
                'environment', 'tenant_id', 'application_id', 
                'client_secret', 'webhook_url', 'webhook_secret'
            ]
            
            for field in required_fields:
                if field not in config_data:
                    raise ValueError(f"Missing required field: {field}")
            
            return config_data
            
        except FileNotFoundError:
            self.logger.error(f"Configuration file not found: {config_file}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in configuration file: {e}")
            sys.exit(1)
        except ValueError as e:
            self.logger.error(f"Configuration validation failed: {e}")
            sys.exit(1)
    
    def create_config_from_args(self, args) -> DeploymentConfig:
        """Create deployment config from command line arguments"""
        return DeploymentConfig(
            environment=DeploymentEnvironment(args.environment),
            tenant_id=args.tenant_id,
            application_id=args.application_id,
            client_secret=args.client_secret,
            webhook_url=args.webhook_url,
            webhook_secret=args.webhook_secret,
            agent_name=args.agent_name or "Screenshot to Code Assistant",
            agent_description=args.agent_description or "AI-powered assistant that converts UI screenshots into clean, production-ready code",
            supported_languages=args.languages or ["en", "vi", "fr", "de", "ja", "zh"]
        )
    
    async def deploy_command(self, args):
        """Handle deploy command"""
        print("🚀 Starting agent deployment...")
        
        try:
            # Load configuration
            if args.config_file:
                config_data = self.load_config_from_file(args.config_file)
                config = DeploymentConfig(
                    environment=DeploymentEnvironment(config_data['environment']),
                    tenant_id=config_data['tenant_id'],
                    application_id=config_data['application_id'],
                    client_secret=config_data['client_secret'],
                    webhook_url=config_data['webhook_url'],
                    webhook_secret=config_data['webhook_secret'],
                    agent_name=config_data.get('agent_name', "Screenshot to Code Assistant"),
                    agent_description=config_data.get('agent_description', "AI-powered assistant"),
                    supported_languages=config_data.get('supported_languages', ["en"])
                )
            else:
                config = self.create_config_from_args(args)
            
            # Deploy the agent
            result = await self.deployer.deploy_agent(config)
            
            if result.success:
                print("✅ Agent deployment successful!")
                print(f"   Agent ID: {result.agent_id}")
                print(f"   Agent URL: {result.agent_url}")
                print(f"   Deployment ID: {result.deployment_id}")
                
                if result.warnings:
                    print("\n⚠️  Warnings:")
                    for warning in result.warnings:
                        print(f"   - {warning}")
                
                # Save deployment info
                if args.output_file:
                    output_data = {
                        "agent_id": result.agent_id,
                        "agent_url": result.agent_url,
                        "deployment_id": result.deployment_id,
                        "environment": config.environment.value,
                        "deployed_at": "datetime.utcnow().isoformat()",
                        "warnings": result.warnings
                    }
                    
                    with open(args.output_file, 'w') as f:
                        json.dump(output_data, f, indent=2)
                    
                    print(f"   Deployment info saved to: {args.output_file}")
                
            else:
                print("❌ Agent deployment failed!")
                print(f"   Error: {result.error}")
                sys.exit(1)
                
        except Exception as e:
            print(f"❌ Deployment failed with exception: {e}")
            self.logger.error("Deployment failed", error=str(e))
            sys.exit(1)
    
    async def status_command(self, args):
        """Handle status command"""
        print(f"📊 Checking agent status...")
        
        try:
            # Create minimal config for status check
            config = DeploymentConfig(
                environment=DeploymentEnvironment(args.environment),
                tenant_id=args.tenant_id,
                application_id=args.application_id,
                client_secret=args.client_secret,
                webhook_url="",  # Not needed for status
                webhook_secret=""  # Not needed for status
            )
            
            status = await self.deployer.get_agent_status(args.agent_id, config)
            
            print(f"   Agent ID: {status['agent_id']}")
            print(f"   Status: {status['status']}")
            print(f"   Name: {status.get('name', 'N/A')}")
            print(f"   Environment: {status.get('environment', 'N/A')}")
            print(f"   Webhook Configured: {status.get('webhook_configured', False)}")
            
            if status.get('created_at'):
                print(f"   Created: {status['created_at']}")
            if status.get('last_modified'):
                print(f"   Last Modified: {status['last_modified']}")
            if status.get('error'):
                print(f"   Error: {status['error']}")
                
        except Exception as e:
            print(f"❌ Status check failed: {e}")
            sys.exit(1)
    
    async def update_command(self, args):
        """Handle update command"""
        print(f"🔄 Updating agent...")
        
        try:
            config = self.create_config_from_args(args)
            result = await self.deployer.update_agent(args.agent_id, config)
            
            if result.success:
                print("✅ Agent update successful!")
                print(f"   Agent ID: {result.agent_id}")
                print(f"   Agent URL: {result.agent_url}")
                
                if result.warnings:
                    print("\n⚠️  Warnings:")
                    for warning in result.warnings:
                        print(f"   - {warning}")
            else:
                print("❌ Agent update failed!")
                print(f"   Error: {result.error}")
                sys.exit(1)
                
        except Exception as e:
            print(f"❌ Update failed: {e}")
            sys.exit(1)
    
    async def delete_command(self, args):
        """Handle delete command"""
        if not args.force:
            response = input(f"Are you sure you want to delete agent {args.agent_id}? (y/N): ")
            if response.lower() != 'y':
                print("Deletion cancelled.")
                return
        
        print(f"🗑️  Deleting agent...")
        
        try:
            config = DeploymentConfig(
                environment=DeploymentEnvironment(args.environment),
                tenant_id=args.tenant_id,
                application_id=args.application_id,
                client_secret=args.client_secret,
                webhook_url="",  # Not needed for deletion
                webhook_secret=""  # Not needed for deletion
            )
            
            success = await self.deployer.delete_agent(args.agent_id, config)
            
            if success:
                print("✅ Agent deleted successfully!")
            else:
                print("❌ Agent deletion failed!")
                sys.exit(1)
                
        except Exception as e:
            print(f"❌ Deletion failed: {e}")
            sys.exit(1)
    
    async def test_command(self, args):
        """Handle test command"""
        print(f"🧪 Testing agent webhook...")
        
        try:
            import aiohttp
            from datetime import datetime
            
            test_payload = {
                "activities": [{
                    "type": "event",
                    "id": "test-cli",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "from": {"id": "cli-test", "name": "CLI Test"},
                    "conversation": {"id": "test-conversation"},
                    "value": {"type": "deploymentTest"}
                }]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(args.webhook_url, json=test_payload) as response:
                    success = response.status in [200, 201]
                    response_text = await response.text()
                    
                    print(f"   Status Code: {response.status}")
                    print(f"   Success: {success}")
                    
                    if response_text:
                        print(f"   Response: {response_text[:200]}...")
                    
                    if not success:
                        sys.exit(1)
                        
        except Exception as e:
            print(f"❌ Test failed: {e}")
            sys.exit(1)


def create_parser():
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        description="Deploy and manage Copilot Studio agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Deploy from config file
  python deploy_agent.py deploy --config-file config.json
  
  # Deploy with command line arguments
  python deploy_agent.py deploy --environment development --tenant-id xxx --application-id yyy --client-secret zzz --webhook-url https://api.com/webhook --webhook-secret secret123
  
  # Check agent status
  python deploy_agent.py status --agent-id agent123 --environment development --tenant-id xxx --application-id yyy --client-secret zzz
  
  # Test webhook
  python deploy_agent.py test --webhook-url https://api.com/webhook
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Deploy command
    deploy_parser = subparsers.add_parser('deploy', help='Deploy a new agent')
    deploy_parser.add_argument('--config-file', help='JSON configuration file')
    deploy_parser.add_argument('--environment', choices=['development', 'staging', 'production'], help='Deployment environment')
    deploy_parser.add_argument('--tenant-id', help='Azure tenant ID')
    deploy_parser.add_argument('--application-id', help='Azure application ID')
    deploy_parser.add_argument('--client-secret', help='Azure client secret')
    deploy_parser.add_argument('--webhook-url', help='Webhook endpoint URL')
    deploy_parser.add_argument('--webhook-secret', help='Webhook secret')
    deploy_parser.add_argument('--agent-name', help='Agent display name')
    deploy_parser.add_argument('--agent-description', help='Agent description')
    deploy_parser.add_argument('--languages', nargs='+', help='Supported languages')
    deploy_parser.add_argument('--output-file', help='File to save deployment info')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Check agent status')
    status_parser.add_argument('--agent-id', required=True, help='Agent ID')
    status_parser.add_argument('--environment', required=True, choices=['development', 'staging', 'production'])
    status_parser.add_argument('--tenant-id', required=True, help='Azure tenant ID')
    status_parser.add_argument('--application-id', required=True, help='Azure application ID')
    status_parser.add_argument('--client-secret', required=True, help='Azure client secret')
    
    # Update command
    update_parser = subparsers.add_parser('update', help='Update existing agent')
    update_parser.add_argument('--agent-id', required=True, help='Agent ID')
    update_parser.add_argument('--environment', required=True, choices=['development', 'staging', 'production'])
    update_parser.add_argument('--tenant-id', required=True, help='Azure tenant ID')
    update_parser.add_argument('--application-id', required=True, help='Azure application ID')
    update_parser.add_argument('--client-secret', required=True, help='Azure client secret')
    update_parser.add_argument('--webhook-url', help='Updated webhook endpoint URL')
    update_parser.add_argument('--webhook-secret', help='Updated webhook secret')
    update_parser.add_argument('--agent-name', help='Updated agent display name')
    update_parser.add_argument('--agent-description', help='Updated agent description')
    update_parser.add_argument('--languages', nargs='+', help='Updated supported languages')
    
    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete agent')
    delete_parser.add_argument('--agent-id', required=True, help='Agent ID')
    delete_parser.add_argument('--environment', required=True, choices=['development', 'staging', 'production'])
    delete_parser.add_argument('--tenant-id', required=True, help='Azure tenant ID')
    delete_parser.add_argument('--application-id', required=True, help='Azure application ID')
    delete_parser.add_argument('--client-secret', required=True, help='Azure client secret')
    delete_parser.add_argument('--force', action='store_true', help='Skip confirmation')
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Test webhook connectivity')
    test_parser.add_argument('--webhook-url', required=True, help='Webhook URL to test')
    
    return parser


async def main():
    """Main entry point"""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    cli = AgentDeploymentCLI()
    
    try:
        await cli.setup()
        
        if args.command == 'deploy':
            await cli.deploy_command(args)
        elif args.command == 'status':
            await cli.status_command(args)
        elif args.command == 'update':
            await cli.update_command(args)
        elif args.command == 'delete':
            await cli.delete_command(args)
        elif args.command == 'test':
            await cli.test_command(args)
            
    finally:
        await cli.cleanup()


if __name__ == "__main__":
    asyncio.run(main())