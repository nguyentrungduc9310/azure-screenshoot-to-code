# Screenshot-to-Code Operations Runbook

**Version**: 1.0  
**Last Updated**: January 2025  
**Prepared for**: Operations Team and Support Staff  

---

## Table of Contents

1. [Operations Overview](#operations-overview)
2. [System Health Monitoring](#system-health-monitoring)
3. [Incident Response Procedures](#incident-response-procedures)
4. [Maintenance Procedures](#maintenance-procedures)
5. [Deployment Procedures](#deployment-procedures)
6. [Backup and Recovery](#backup-and-recovery)
7. [Performance Monitoring](#performance-monitoring)
8. [Security Operations](#security-operations)
9. [Cost Management](#cost-management)
10. [Emergency Contacts](#emergency-contacts)

---

## Operations Overview

### Service Level Agreements (SLAs)

```yaml
Production SLAs:
  Availability: 99.9% uptime (8.7 hours downtime per year)
  Response Time: 
    - API endpoints: <500ms (95th percentile)
    - Code generation: <10s (95th percentile)
    - Image processing: <5s (95th percentile)
  Support Response:
    - Critical: 15 minutes
    - High: 2 hours
    - Medium: 8 hours
    - Low: 24 hours
```

### Operational Responsibilities

**Operations Team**:
- System monitoring and alerting
- Incident response and resolution
- Capacity planning and scaling
- Backup verification and recovery testing
- Security monitoring and compliance

**Development Team**:
- Code deployment and rollbacks
- Performance optimization
- Bug fixes and hotfixes
- Feature development and testing

**Support Team**:
- User issue resolution
- Documentation updates
- Training material maintenance
- Customer communication

### Key Metrics Dashboard

**Primary Metrics to Monitor**:
```yaml
System Health:
  - Overall system availability
  - Service response times
  - Error rates by service
  - Database performance metrics
  - Cache hit rates

Business Metrics:
  - Active users (daily/monthly)
  - Code generations per hour
  - AI provider usage distribution
  - Revenue metrics
  - User satisfaction scores

Infrastructure Metrics:
  - CPU and memory utilization
  - Network throughput
  - Storage usage
  - Azure service quotas
  - Cost per service
```

---

## System Health Monitoring

### Health Check Endpoints

**Primary Health Checks**:
```bash
# Application Health
curl -X GET https://api.screenshot-to-code.com/health
# Expected Response: {"status": "healthy", "timestamp": "2025-01-15T10:30:00Z"}

# Database Health
curl -X GET https://api.screenshot-to-code.com/health/database
# Expected Response: {"status": "connected", "response_time_ms": 45}

# Cache Health
curl -X GET https://api.screenshot-to-code.com/health/cache
# Expected Response: {"status": "connected", "hit_rate": 85.2}

# AI Providers Health
curl -X GET https://api.screenshot-to-code.com/health/ai-providers
# Expected Response: {"openai": "healthy", "anthropic": "healthy", "google": "healthy"}
```

### Automated Health Monitoring

**Health Check Schedule**:
```yaml
Health Check Intervals:
  Critical Services:
    - API Gateway: Every 30 seconds
    - Database: Every 60 seconds
    - Authentication: Every 30 seconds
    
  Important Services:
    - AI Providers: Every 2 minutes
    - Cache: Every 2 minutes
    - Storage: Every 5 minutes
    
  Supporting Services:
    - Monitoring: Every 5 minutes
    - Logging: Every 10 minutes
    - CDN: Every 10 minutes

Alert Thresholds:
  - 2 consecutive failures: Warning alert
  - 3 consecutive failures: Critical alert
  - 5 consecutive failures: Page operations team
```

### Monitoring Tools and Dashboards

**Azure Monitor Workbooks**:
1. **System Overview Dashboard**
   - Overall system health status
   - Key performance indicators
   - Active incidents and alerts
   - Resource utilization summary

2. **Performance Dashboard**
   - Response time trends
   - Throughput metrics
   - Error rate analysis
   - Database performance

3. **Security Dashboard**
   - Authentication metrics
   - Failed login attempts
   - Security alerts
   - Compliance status

**Access URLs**:
```bash
# Primary Dashboard
https://portal.azure.com/#@tenant/dashboard/private/screenshot-to-code-overview

# Performance Monitoring
https://portal.azure.com/#@tenant/resource/subscriptions/{subscription-id}/resourceGroups/sktc-prod-rg/providers/Microsoft.Insights/workbooks/performance

# Security Monitoring
https://portal.azure.com/#@tenant/resource/subscriptions/{subscription-id}/resourceGroups/sktc-prod-rg/providers/Microsoft.Insights/workbooks/security
```

---

## Incident Response Procedures

### Incident Classification

**Severity Levels**:
```yaml
Critical (Sev 1):
  - Complete system outage
  - Data loss or corruption
  - Security breach
  - Response Time: 15 minutes
  - Resolution Target: 1 hour
  
High (Sev 2):
  - Partial system outage
  - Performance degradation >50%
  - AI provider failures
  - Response Time: 2 hours
  - Resolution Target: 4 hours
  
Medium (Sev 3):
  - Minor performance issues
  - Non-critical feature failures
  - Warning alerts
  - Response Time: 8 hours
  - Resolution Target: 24 hours
  
Low (Sev 4):
  - Enhancement requests
  - Documentation updates
  - Minor UI issues
  - Response Time: 24 hours
  - Resolution Target: 72 hours
```

### Incident Response Process

**Step-by-Step Response**:

1. **Incident Detection and Acknowledgment** (0-5 minutes)
   ```bash
   # Check system status
   curl -X GET https://api.screenshot-to-code.com/health
   
   # Review recent alerts in Azure Monitor
   az monitor activity-log list --start-time $(date -u -d '1 hour ago' '+%Y-%m-%dT%H:%M:%SZ')
   
   # Acknowledge incident in monitoring system
   # Update status page if customer-facing
   ```

2. **Initial Assessment** (5-15 minutes)
   ```bash
   # Check service health across all environments
   kubectl get pods --all-namespaces
   
   # Review error logs
   az monitor log-analytics query --workspace {workspace-id} --analytics-query "
   AppTraces
   | where TimeGenerated > ago(1h)
   | where SeverityLevel >= 3
   | order by TimeGenerated desc
   | limit 100"
   
   # Check resource utilization
   az monitor metrics list --resource {resource-id} --metric "Percentage CPU"
   ```

3. **Escalation and Communication** (15-30 minutes)
   ```yaml
   Communication Channels:
     - Internal: Slack #incidents channel
     - Customer: Status page update
     - Stakeholders: Email to leadership
     - Documentation: Incident ticket creation
   
   Escalation Path:
     - Level 1: On-call engineer
     - Level 2: Senior operations engineer
     - Level 3: Engineering manager
     - Level 4: CTO/VP Engineering
   ```

4. **Investigation and Diagnosis** (30 minutes - 2 hours)
   ```bash
   # Deep dive into logs
   az monitor log-analytics query --workspace {workspace-id} --analytics-query "
   union AppExceptions, AppTraces, AppRequests
   | where TimeGenerated > ago(2h)
   | where SeverityLevel >= 2
   | order by TimeGenerated desc"
   
   # Check database performance
   az cosmosdb show --name sktc-prod-cosmos --resource-group sktc-prod-rg
   
   # Review AI provider status
   curl -X GET https://status.openai.com/api/v2/status.json
   curl -X GET https://status.anthropic.com/api/v2/status.json
   ```

5. **Resolution Implementation** (2-4 hours)
   ```bash
   # Common resolution actions
   
   # Restart services
   kubectl rollout restart deployment/api-gateway
   kubectl rollout restart deployment/code-generation-service
   
   # Scale up resources
   kubectl scale deployment api-gateway --replicas=10
   
   # Clear cache if needed
   redis-cli -h sktc-prod-cache.redis.cache.windows.net FLUSHDB
   
   # Deploy hotfix if available
   kubectl apply -f hotfix-deployment.yaml
   ```

6. **Verification and Monitoring** (Post-resolution)
   ```bash
   # Verify system health
   curl -X GET https://api.screenshot-to-code.com/health
   
   # Run smoke tests
   python scripts/smoke_tests.py --environment production
   
   # Monitor for 30 minutes post-resolution
   # Update status page and stakeholders
   ```

### Common Incident Scenarios

**Scenario 1: API Gateway Timeout Issues**
```bash
# Symptoms: Increased response times, timeout errors
# Investigation:
kubectl logs -f deployment/api-gateway --tail=100

# Resolution:
kubectl scale deployment api-gateway --replicas=5
kubectl rollout restart deployment/api-gateway

# Verification:
curl -w "@curl-format.txt" -X GET https://api.screenshot-to-code.com/health
```

**Scenario 2: Database Connection Issues**
```bash
# Symptoms: Database connection errors, failed health checks
# Investigation:
az cosmosdb show --name sktc-prod-cosmos --resource-group sktc-prod-rg --query "readLocations"

# Resolution:
# Check connection string in Key Vault
az keyvault secret show --vault-name sktc-prod-kv --name cosmosdb-connection-string

# Restart services to refresh connections
kubectl rollout restart deployment/code-generation-service
```

**Scenario 3: AI Provider Failures**
```bash
# Symptoms: Code generation failures, AI provider errors
# Investigation:
curl -X GET https://api.openai.com/v1/models
curl -X GET https://api.anthropic.com/v1/models

# Resolution:
# Enable fallback provider in configuration
kubectl patch configmap ai-config -p '{"data":{"fallback_enabled":"true"}}'

# Monitor provider rotation
kubectl logs -f deployment/ai-orchestration-service | grep "provider_switch"
```

---

## Maintenance Procedures

### Scheduled Maintenance Windows

**Maintenance Schedule**:
```yaml
Regular Maintenance:
  - Every Sunday 2:00-4:00 AM UTC
  - First Saturday of month 1:00-5:00 AM UTC (extended)
  
Emergency Maintenance:
  - As needed with 2-hour notice minimum
  - Critical security patches: Immediate
  
Blackout Windows:
  - No maintenance during business hours (9 AM - 6 PM UTC)
  - No maintenance during promotional campaigns
  - No maintenance during major holidays
```

### Pre-Maintenance Checklist

**24 Hours Before Maintenance**:
```bash
# 1. Verify backup completion
az backup job list --resource-group sktc-prod-rg --vault-name sktc-backup-vault

# 2. Check system health
curl -X GET https://api.screenshot-to-code.com/health

# 3. Review pending alerts
az monitor activity-log list --start-time $(date -u -d '24 hours ago' '+%Y-%m-%dT%H:%M:%SZ')

# 4. Communicate maintenance window
# Update status page and notify stakeholders

# 5. Prepare rollback plan
kubectl get deployments -o yaml > pre-maintenance-backup.yaml
```

**1 Hour Before Maintenance**:
```bash
# 1. Final system health check
python scripts/pre_maintenance_check.py

# 2. Create configuration backup
kubectl get configmaps -o yaml > configmaps-backup.yaml
kubectl get secrets -o yaml > secrets-backup.yaml

# 3. Scale up services for faster recovery
kubectl scale deployment api-gateway --replicas=3

# 4. Enable maintenance mode
kubectl apply -f maintenance-mode.yaml
```

### During Maintenance Procedures

**Standard Maintenance Tasks**:
```bash
# 1. System Updates
# Update container images
kubectl set image deployment/api-gateway api-gateway=sktc.azurecr.io/api-gateway:v1.2.3

# Apply Kubernetes updates
kubectl apply -f updated-manifests/

# 2. Database Maintenance
# Run index optimization
az cosmosdb sql container throughput update \
  --account-name sktc-prod-cosmos \
  --resource-group sktc-prod-rg \
  --database-name screenshot_to_code \
  --name users \
  --throughput 1000

# 3. Cache Maintenance
# Clear expired keys
redis-cli -h sktc-prod-cache.redis.cache.windows.net EVAL "
for i, name in ipairs(redis.call('KEYS', ARGV[1])) do
  redis.call('DEL', name);
end
return i;
" 0 "expired:*"

# 4. Security Updates
# Rotate secrets if needed
az keyvault secret set --vault-name sktc-prod-kv --name api-key --value "new-secret-value"

# Update certificates
az webapp ssl import --resource-group sktc-prod-rg --name sktc-prod-app --key-vault sktc-prod-kv --certificate-name prod-cert
```

### Post-Maintenance Checklist

**Immediate Post-Maintenance** (0-30 minutes):
```bash
# 1. Disable maintenance mode
kubectl delete -f maintenance-mode.yaml

# 2. Verify all services are running
kubectl get pods --all-namespaces

# 3. Run comprehensive health checks
python scripts/post_maintenance_check.py

# 4. Verify key functionality
python scripts/smoke_tests.py --environment production

# 5. Check performance metrics
curl -w "@curl-format.txt" -X GET https://api.screenshot-to-code.com/api/v1/generate-code
```

**Extended Monitoring** (30 minutes - 4 hours):
```bash
# Monitor error rates
az monitor log-analytics query --workspace {workspace-id} --analytics-query "
AppRequests
| where TimeGenerated > ago(1h)
| summarize ErrorRate = 100.0 * countif(Success == false) / count() by bin(TimeGenerated, 5m)
| order by TimeGenerated desc"

# Monitor performance
az monitor metrics list --resource {app-service-id} --metric "AverageResponseTime" --interval PT5M

# Check user impact
az monitor log-analytics query --workspace {workspace-id} --analytics-query "
AppPageViews
| where TimeGenerated > ago(2h)
| summarize UniqueUsers = dcount(UserId) by bin(TimeGenerated, 15m)
| order by TimeGenerated desc"
```

---

## Deployment Procedures

### Deployment Types

**Deployment Strategies**:
```yaml
Blue-Green Deployment:
  - Zero downtime deployment
  - Full environment swap
  - Easy rollback capability
  - Used for major releases
  
Canary Deployment:  
  - Gradual traffic routing
  - Risk mitigation
  - A/B testing capability
  - Used for feature releases
  
Rolling Deployment:
  - Instance-by-instance updates
  - Continuous availability
  - Resource efficient
  - Used for minor updates
  
Hotfix Deployment:
  - Emergency bug fixes
  - Expedited process
  - Skip non-critical steps
  - Immediate rollback plan
```

### Production Deployment Process

**Standard Deployment Procedure**:
```bash
# 1. Pre-deployment validation
python scripts/pre_deployment_check.py --environment production

# 2. Create deployment backup
kubectl create backup prod-backup-$(date +%Y%m%d-%H%M%S)

# 3. Deploy to staging slot first
az webapp deployment slot create --name sktc-prod-app --resource-group sktc-prod-rg --slot staging

# 4. Run integration tests on staging
python scripts/integration_tests.py --base-url https://sktc-prod-app-staging.azurewebsites.net

# 5. Production deployment
kubectl apply -f production-manifests/ --record

# 6. Monitor deployment progress
kubectl rollout status deployment/api-gateway
kubectl rollout status deployment/code-generation-service

# 7. Run smoke tests
python scripts/smoke_tests.py --environment production

# 8. Monitor for 30 minutes
# Check error rates, response times, and user impact
```

### Rollback Procedures

**Emergency Rollback Process**:
```bash
# 1. Immediate rollback (< 2 minutes)
kubectl rollout undo deployment/api-gateway
kubectl rollout undo deployment/code-generation-service

# 2. Verify rollback success
kubectl rollout status deployment/api-gateway

# 3. Run health checks
curl -X GET https://api.screenshot-to-code.com/health

# 4. Restore database if needed (only if data corruption)
az cosmosdb sql database restore \
  --account-name sktc-prod-cosmos \
  --resource-group sktc-prod-rg \
  --database-name screenshot_to_code \
  --restore-timestamp "2025-01-15T10:00:00Z"

# 5. Clear cache to prevent stale data
redis-cli -h sktc-prod-cache.redis.cache.windows.net FLUSHALL

# 6. Update status page and stakeholders
```

### Deployment Verification

**Post-Deployment Checklist**:
```bash
# 1. Service Health Verification
for service in api-gateway code-generation-service image-processing-service ai-orchestration-service; do
  echo "Checking $service..."
  kubectl get deployment $service
  kubectl logs deployment/$service --tail=10
done

# 2. End-to-End Testing
python scripts/e2e_tests.py --environment production --verbose

# 3. Performance Validation
ab -n 100 -c 10 https://api.screenshot-to-code.com/health

# 4. Database Connectivity
python scripts/db_connectivity_test.py --connection-string "$COSMOS_CONNECTION_STRING"

# 5. AI Provider Connectivity
python scripts/ai_provider_test.py --test-all-providers

# 6. User Journey Testing
python scripts/user_journey_test.py --create-user --generate-code --cleanup
```

---

## Backup and Recovery

### Backup Strategy

**Backup Schedule**:
```yaml
Database Backups:
  - Continuous: Point-in-time recovery enabled
  - Daily: Full backup at 2:00 AM UTC
  - Weekly: Full backup with extended retention
  - Monthly: Archived backup for compliance
  
Application Backups:
  - Configuration: Daily backup of Kubernetes manifests
  - Code: Git repository with branch protection
  - Secrets: Azure Key Vault with versioning
  - Images: Container registry with retention policy
  
Infrastructure Backups:
  - ARM Templates: Version controlled in Git
  - Terraform State: Azure Storage with versioning
  - Network Configuration: Exported to JSON daily
  - Security Policies: Documented and version controlled
```

### Backup Verification

**Daily Backup Check**:
```bash
# 1. Verify database backup completion
az backup job list \
  --resource-group sktc-prod-rg \
  --vault-name sktc-backup-vault \
  --status Completed \
  --start-time $(date -u -d '1 day ago' '+%Y-%m-%dT%H:%M:%SZ')

# 2. Test backup integrity
az cosmosdb sql database restore \
  --account-name sktc-test-cosmos \
  --resource-group sktc-test-rg \
  --database-name test_restore \
  --restore-timestamp $(date -u -d '1 day ago' '+%Y-%m-%dT%H:%M:%SZ') \
  --dry-run

# 3. Verify configuration backup
ls -la backups/config/$(date +%Y-%m-%d)/

# 4. Test secret accessibility
az keyvault secret show --vault-name sktc-prod-kv --name cosmosdb-connection-string
```

### Disaster Recovery Procedures

**Complete System Recovery**:
```bash
# 1. Assess damage and recovery scope
python scripts/disaster_assessment.py --check-all-services

# 2. Activate secondary region (if needed)
az traffic-manager endpoint update \
  --resource-group sktc-prod-rg \
  --profile-name sktc-traffic-manager \
  --endpoint-name primary \
  --endpoint-status Disabled

# 3. Restore infrastructure
az deployment group create \
  --resource-group sktc-recovery-rg \
  --template-file infrastructure/arm-template.json \
  --parameters @recovery-parameters.json

# 4. Restore database
az cosmosdb sql database restore \
  --account-name sktc-recovery-cosmos \
  --resource-group sktc-recovery-rg \
  --database-name screenshot_to_code \
  --restore-timestamp "$RECOVERY_TIMESTAMP"

# 5. Deploy applications
kubectl apply -f recovery-manifests/

# 6. Restore secrets and configuration
az keyvault secret restore --vault-name sktc-recovery-kv --backup-file secrets-backup.bin

# 7. Update DNS and routing
az network dns record-set cname set-record \
  --resource-group dns-rg \
  --zone-name screenshot-to-code.com \
  --record-set-name api \
  --cname sktc-recovery-app.azurewebsites.net

# 8. Verify recovery
python scripts/recovery_verification.py --full-test
```

### Recovery Testing

**Monthly Recovery Test**:
```bash
# 1. Create isolated test environment
az group create --name sktc-recovery-test-rg --location eastus

# 2. Deploy from backup
python scripts/recovery_test.py --environment test --restore-timestamp "latest"

# 3. Run functionality tests
python scripts/e2e_tests.py --environment recovery-test

# 4. Measure recovery time
echo "Recovery completed in: $(python scripts/measure_recovery_time.py)"

# 5. Document results
python scripts/recovery_report.py --output recovery-test-$(date +%Y%m%d).md

# 6. Cleanup test environment
az group delete --name sktc-recovery-test-rg --yes --no-wait
```

---

## Performance Monitoring

### Key Performance Indicators

**Application Performance**:
```yaml
Response Time Metrics:
  - API Gateway: <200ms (95th percentile)
  - Code Generation: <8s (95th percentile)  
  - Image Processing: <3s (95th percentile)
  - Database Queries: <100ms (95th percentile)
  
Throughput Metrics:
  - Requests per second: >100 sustained
  - Concurrent users: >500 simultaneous
  - Code generations per hour: >5,000
  - Cache hit rate: >80%
  
Error Rate Metrics:
  - Overall error rate: <1%
  - 5xx errors: <0.1%
  - Timeout errors: <0.5%
  - AI provider errors: <2%
```

### Performance Monitoring Queries

**Azure Log Analytics Queries**:
```kql
-- Response Time Analysis
AppRequests
| where TimeGenerated > ago(1h)
| summarize 
    AvgResponseTime = avg(DurationMs),
    P95ResponseTime = percentile(DurationMs, 95),
    P99ResponseTime = percentile(DurationMs, 99)
by bin(TimeGenerated, 5m), Name
| order by TimeGenerated desc

-- Error Rate Monitoring
AppRequests
| where TimeGenerated > ago(1h)
| summarize 
    TotalRequests = count(),
    FailedRequests = countif(Success == false),
    ErrorRate = 100.0 * countif(Success == false) / count()
by bin(TimeGenerated, 5m)
| order by TimeGenerated desc

-- Top Slow Requests
AppRequests
| where TimeGenerated > ago(1h)
| where DurationMs > 5000
| order by DurationMs desc
| take 20
| project TimeGenerated, Name, Url, DurationMs, ResultCode

-- AI Provider Performance
AppDependencies
| where TimeGenerated > ago(1h)
| where Type == "HTTP"
| where Target contains "openai" or Target contains "anthropic" or Target contains "google"
| summarize 
    AvgDuration = avg(DurationMs),
    SuccessRate = 100.0 * countif(Success == true) / count(),
    RequestCount = count()
by Target, bin(TimeGenerated, 15m)
| order by TimeGenerated desc
```

### Performance Alerting

**Critical Performance Alerts**:
```bash
# Create response time alert
az monitor metrics alert create \
  --name "High Response Time" \
  --resource-group sktc-prod-rg \
  --resource sktc-prod-app \
  --metric "AverageResponseTime" \
  --operator GreaterThan \
  --threshold 5000 \
  --aggregation Average \
  --window-size 5m \
  --evaluation-frequency 1m \
  --action-group operations-team

# Create error rate alert  
az monitor metrics alert create \
  --name "High Error Rate" \
  --resource-group sktc-prod-rg \
  --resource sktc-prod-app \
  --metric "Http5xx" \
  --operator GreaterThan \
  --threshold 10 \
  --aggregation Total \
  --window-size 5m \
  --evaluation-frequency 1m \
  --action-group critical-alerts
```

### Performance Optimization

**When Performance Issues Occur**:
```bash
# 1. Identify bottlenecks
python scripts/performance_analysis.py --time-range 1h

# 2. Scale up services if needed
kubectl scale deployment api-gateway --replicas=10

# 3. Check database performance
az cosmosdb show-offer --ids /subscriptions/{sub}/resourceGroups/sktc-prod-rg/providers/Microsoft.DocumentDB/databaseAccounts/sktc-prod-cosmos

# 4. Clear cache if necessary
redis-cli -h sktc-prod-cache.redis.cache.windows.net EVAL "
for i, name in ipairs(redis.call('KEYS', ARGV[1])) do
  redis.call('DEL', name);
end
" 0 "slow:*"

# 5. Review AI provider performance
python scripts/ai_provider_health.py --switch-provider-if-slow

# 6. Apply performance optimizations
kubectl apply -f performance-optimizations/
```

---

## Security Operations

### Security Monitoring

**Security Metrics to Monitor**:
```yaml
Authentication Metrics:
  - Failed login attempts
  - Account lockouts
  - Password reset requests
  - Multi-factor authentication usage
  
Access Control Metrics:
  - Privileged account usage
  - Permission escalations
  - Unauthorized access attempts
  - API key usage patterns
  
Security Incidents:
  - Malware detection
  - Suspicious network activity
  - Data exfiltration attempts
  - Security policy violations
```

### Security Alert Responses

**High-Priority Security Alerts**:
```bash
# Multiple Failed Login Attempts
az monitor log-analytics query --workspace {workspace-id} --analytics-query "
SigninLogs
| where TimeGenerated > ago(1h)
| where ResultType != '0'
| summarize FailedAttempts = count() by UserPrincipalName, IPAddress
| where FailedAttempts > 10"

# Response: Lock account and investigate
az ad user update --id {user-id} --account-enabled false

# Suspicious API Usage
az monitor log-analytics query --workspace {workspace-id} --analytics-query "
AppRequests
| where TimeGenerated > ago(1h)
| summarize RequestCount = count() by ClientIP
| where RequestCount > 1000"

# Response: Implement rate limiting
kubectl apply -f security/rate-limiting.yaml
```

### Security Incident Response

**Security Incident Process**:
```bash
# 1. Immediate Response (0-15 minutes)
# Isolate affected systems
kubectl patch deployment api-gateway -p '{"spec":{"replicas":0}}'

# Block suspicious IPs
az network nsg rule create \
  --resource-group sktc-prod-rg \
  --nsg-name sktc-prod-nsg \
  --name block-suspicious-ip \
  --priority 100 \
  --access Deny \
  --source-address-prefixes {suspicious-ip}

# 2. Investigation (15-60 minutes)
# Collect logs for analysis
az monitor log-analytics query --workspace {workspace-id} --analytics-query "
union AppRequests, AppExceptions, AppTraces, SigninLogs
| where TimeGenerated > ago(4h)
| where ClientIP == '{suspicious-ip}' or UserPrincipalName == '{suspicious-user}'"

# 3. Containment (1-4 hours)
# Rotate compromised keys
az keyvault secret set --vault-name sktc-prod-kv --name api-key --value "new-secure-key"

# Update authentication requirements
az ad app update --id {app-id} --required-resource-access @updated-permissions.json

# 4. Recovery (4-24 hours)  
# Restore services with enhanced security
kubectl apply -f security/enhanced-security-config.yaml

# Verify system integrity
python scripts/security_verification.py --full-scan
```

### Security Maintenance

**Regular Security Tasks**:
```bash
# Weekly security tasks
# 1. Review access logs
az monitor log-analytics query --workspace {workspace-id} --analytics-query "
SigninLogs
| where TimeGenerated > ago(7d)
| summarize SigninCount = count(), DistinctLocations = dcount(Location) by UserPrincipalName
| order by SigninCount desc"

# 2. Check for security updates
az vm assess-patches --resource-group sktc-prod-rg --vm-name sktc-prod-vm

# 3. Validate SSL certificates
python scripts/ssl_certificate_check.py --check-expiration

# 4. Review API key usage
python scripts/api_key_audit.py --check-unused-keys

# Monthly security tasks
# 1. Penetration testing
python scripts/security_scan.py --full-scan

# 2. Access review
az ad group member list --group operations-team
az ad group member list --group admin-team

# 3. Secret rotation
python scripts/rotate_secrets.py --rotate-all

# 4. Security policy review
python scripts/security_compliance_check.py --generate-report
```

---

## Cost Management

### Cost Monitoring

**Daily Cost Tracking**:
```bash
# Get current month costs
az consumption usage list --start-date $(date -d "$(date +%Y-%m-01)" +%Y-%m-%d) --end-date $(date +%Y-%m-%d)

# Cost by resource group
az consumption usage list --start-date $(date -d "1 month ago" +%Y-%m-%d) | jq '.[] | {resource: .instanceName, cost: .pretaxCost}'

# Top cost contributors
az monitor log-analytics query --workspace {workspace-id} --analytics-query "
AzureCosts
| where TimeGenerated > ago(30d)
| summarize TotalCost = sum(Cost) by ResourceGroup, ServiceName
| order by TotalCost desc
| take 10"
```

### Cost Optimization

**Cost Reduction Strategies**:
```bash
# 1. Right-size compute resources
az monitor metrics list --resource {app-service-id} --metric "CpuPercentage" --aggregation Average
# Scale down if CPU < 50% consistently

# 2. Optimize database throughput
az cosmosdb sql container throughput show --account-name sktc-prod-cosmos --database-name screenshot_to_code --name users
# Reduce RU/s if utilization < 70%

# 3. Review storage usage
az storage blob list --account-name sktcstorage --container-name images --query "length(@)"
# Implement lifecycle policies for old images

# 4. Analyze AI provider costs
python scripts/ai_cost_analysis.py --compare-providers --recommend-optimization

# 5. Review unused resources
az resource list --query "[?tags.Environment=='production' and tags.LastUsed < '$(date -d '30 days ago' +%Y-%m-%d)']"
```

### Budget Alerts

**Cost Alert Configuration**:
```bash
# Create budget alert
az consumption budget create \
  --budget-name "Monthly Production Budget" \
  --amount 5000 \
  --resource-group sktc-prod-rg \
  --time-grain Monthly \
  --time-period start-date=$(date +%Y-%m-01) \
  --notifications \
    amount=80 \
    contact-emails=ops-team@company.com \
    operator=GreaterThan \
    threshold-type=Actual

# Weekly cost review
python scripts/weekly_cost_report.py --send-email ops-team@company.com
```

---

## Emergency Contacts

### Escalation Matrix

**Contact Information**:
```yaml
Level 1 - Operations Team:
  Primary On-Call: +1-555-0101 (operations@company.com)
  Secondary On-Call: +1-555-0102 (ops-backup@company.com)
  Team Lead: +1-555-0103 (ops-lead@company.com)
  
Level 2 - Engineering Team:
  Senior Engineer: +1-555-0201 (senior-eng@company.com)
  Engineering Manager: +1-555-0202 (eng-manager@company.com)
  Tech Lead: +1-555-0203 (tech-lead@company.com)
  
Level 3 - Leadership:
  CTO: +1-555-0301 (cto@company.com)
  VP Engineering: +1-555-0302 (vp-eng@company.com)
  CEO: +1-555-0303 (ceo@company.com)
  
External Vendors:
  Azure Support: +1-800-MICROSOFT
  OpenAI Support: support@openai.com
  Anthropic Support: support@anthropic.com
```

### Communication Channels

**Internal Communication**:
- Slack: #incidents (primary), #operations (secondary)
- Email: ops-team@company.com (group), critical-alerts@company.com
- Phone: Conference bridge +1-555-BRIDGE

**External Communication**:
- Status Page: https://status.screenshot-to-code.com
- Customer Support: support@company.com
- Social Media: @ScreenshotToCode (Twitter)

### Emergency Procedures

**Emergency Contact Process**:
1. **Immediate Response** (0-5 minutes)
   - Primary on-call engineer acknowledges incident
   - Initial assessment and severity classification
   - Activate incident response team if Sev 1/2

2. **Escalation Triggers**:
   - 30 minutes without resolution progress
   - Customer-facing outage continues
   - Security incident confirmed
   - Data loss or corruption suspected

3. **Communication Protocol**:
   - Update stakeholders every 30 minutes during active incidents
   - Status page updated within 15 minutes of incident detection
   - Post-incident report within 24 hours of resolution

---

## Conclusion

This operations runbook provides comprehensive procedures for maintaining the Screenshot-to-Code system. Regular review and updates of these procedures are essential as the system evolves.

**Key Success Factors**:
- Proactive monitoring and alerting
- Clear escalation procedures
- Regular testing of recovery procedures
- Continuous improvement based on incident learnings
- Strong communication during incidents

---

**Document Prepared By**: Operations Team  
**Review Schedule**: Monthly  
**Next Review Date**: February 15, 2025  
**Document Owner**: Operations Manager