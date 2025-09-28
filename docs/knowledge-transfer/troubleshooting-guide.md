# Screenshot-to-Code Troubleshooting Guide

**Version**: 1.0  
**Last Updated**: January 2025  
**Prepared for**: Technical Support and Operations Teams  

---

## Table of Contents

1. [Troubleshooting Overview](#troubleshooting-overview)
2. [System Health Diagnostics](#system-health-diagnostics)
3. [Common Issues and Solutions](#common-issues-and-solutions)
4. [Service-Specific Troubleshooting](#service-specific-troubleshooting)
5. [Performance Issues](#performance-issues)
6. [Database Issues](#database-issues)
7. [AI Provider Issues](#ai-provider-issues)
8. [Security and Authentication Issues](#security-and-authentication-issues)
9. [Network and Connectivity Issues](#network-and-connectivity-issues)
10. [Monitoring and Logging](#monitoring-and-logging)

---

## Troubleshooting Overview

### Troubleshooting Methodology

**Systematic Approach**:
1. **Problem Identification**: Clearly define the issue and its symptoms
2. **Information Gathering**: Collect logs, metrics, and system state
3. **Root Cause Analysis**: Identify the underlying cause
4. **Solution Implementation**: Apply appropriate fixes
5. **Verification**: Confirm the issue is resolved
6. **Documentation**: Record the solution for future reference

### Quick Health Check Commands

**Essential Health Checks**:
```bash
# Overall system health
curl -s https://api.screenshot-to-code.com/health | jq '.'

# Service availability
kubectl get pods --all-namespaces | grep -v Running

# Database connectivity
az cosmosdb show --name sktc-prod-cosmos --resource-group sktc-prod-rg --query "documentEndpoint"

# Cache status
redis-cli -h sktc-prod-cache.redis.cache.windows.net ping

# AI provider status
curl -s https://status.openai.com/api/v2/status.json | jq '.status.indicator'
```

### Log Analysis Tools

**Log Query Examples**:
```bash
# Recent errors across all services
az monitor log-analytics query --workspace {workspace-id} --analytics-query "
union AppExceptions, AppTraces
| where TimeGenerated > ago(1h)
| where SeverityLevel >= 3
| order by TimeGenerated desc
| take 20"

# Performance issues
az monitor log-analytics query --workspace {workspace-id} --analytics-query "
AppRequests
| where TimeGenerated > ago(1h)
| where DurationMs > 5000
| order by DurationMs desc
| take 10"

# Authentication failures
az monitor log-analytics query --workspace {workspace-id} --analytics-query "
SigninLogs
| where TimeGenerated > ago(1h)
| where ResultType != '0'
| summarize count() by ResultType, UserPrincipalName"
```

---

## System Health Diagnostics

### Automated Health Check Script

**Comprehensive Health Check**:
```bash
#!/bin/bash
# health_check.sh - Comprehensive system health verification

echo "=== Screenshot-to-Code System Health Check ==="
echo "Timestamp: $(date)"
echo ""

# Function to check HTTP endpoint
check_endpoint() {
    local url=$1
    local name=$2
    local expected_status=${3:-200}
    
    echo -n "Checking $name... "
    response=$(curl -s -o /dev/null -w "%{http_code}" "$url")
    
    if [ "$response" -eq "$expected_status" ]; then
        echo "✅ OK ($response)"
        return 0
    else
        echo "❌ FAILED ($response)"
        return 1
    fi
}

# Check main endpoints
check_endpoint "https://api.screenshot-to-code.com/health" "API Health"
check_endpoint "https://api.screenshot-to-code.com/docs" "API Documentation"
check_endpoint "https://screenshot-to-code.com" "Frontend"

# Check service pods
echo ""
echo "=== Kubernetes Pod Status ==="
kubectl get pods --all-namespaces | grep -E "(screenshot|sktc)" | while read line; do
    status=$(echo $line | awk '{print $4}')
    name=$(echo $line | awk '{print $2}')
    if [ "$status" = "Running" ]; then
        echo "✅ $name: $status"
    else
        echo "❌ $name: $status"
    fi
done

# Check database connection
echo ""
echo "=== Database Connectivity ==="
if az cosmosdb show --name sktc-prod-cosmos --resource-group sktc-prod-rg > /dev/null 2>&1; then
    echo "✅ Cosmos DB: Connected"
else
    echo "❌ Cosmos DB: Connection failed"
fi

# Check cache
echo ""
echo "=== Cache Status ==="
if redis-cli -h sktc-prod-cache.redis.cache.windows.net ping > /dev/null 2>&1; then
    echo "✅ Redis Cache: Available"
else
    echo "❌ Redis Cache: Unavailable"
fi

# Check AI providers
echo ""
echo "=== AI Provider Status ==="
for provider in openai anthropic google; do
    case $provider in
        openai)
            status=$(curl -s https://status.openai.com/api/v2/status.json | jq -r '.status.indicator')
            ;;
        anthropic)
            status=$(curl -s -o /dev/null -w "%{http_code}" https://api.anthropic.com/v1/messages)
            ;;
        google)
            status=$(curl -s -o /dev/null -w "%{http_code}" https://generativelanguage.googleapis.com/v1/models)
            ;;
    esac
    
    if [[ "$status" == "none" || "$status" == "200" ]]; then
        echo "✅ $provider: Operational"
    else
        echo "⚠️ $provider: $status"
    fi
done

echo ""
echo "=== Health Check Complete ==="
```

### Service Discovery

**Find Service Issues**:
```bash
# Identify unhealthy services
kubectl get pods --all-namespaces --field-selector=status.phase!=Running

# Check service logs for errors
kubectl logs --all-containers=true --selector=app=api-gateway --tail=50 | grep -i error

# Resource utilization check
kubectl top pods --all-namespaces --sort-by=cpu

# Network connectivity between services
kubectl exec -it deployment/api-gateway -- nslookup code-generation-service

# Check service endpoints
kubectl get endpoints --all-namespaces | grep screenshot
```

---

## Common Issues and Solutions

### Issue 1: Application Not Responding

**Symptoms**:
- HTTP 503 Service Unavailable
- Connection timeouts
- No response from health endpoints

**Diagnosis**:
```bash
# Check if services are running
kubectl get pods --selector=app=api-gateway

# Check service logs
kubectl logs deployment/api-gateway --tail=100

# Check resource utilization
kubectl describe pod $(kubectl get pods --selector=app=api-gateway -o jsonpath='{.items[0].metadata.name}')

# Check load balancer status
az network lb show --name sktc-prod-lb --resource-group sktc-prod-rg --query "provisioningState"
```

**Solutions**:
```bash
# Restart the service
kubectl rollout restart deployment/api-gateway

# Scale up if resource constrained
kubectl scale deployment api-gateway --replicas=5

# Check and fix configuration
kubectl get configmap api-gateway-config -o yaml

# Clear DNS cache if needed
kubectl delete pods --selector=k8s-app=kube-dns --namespace=kube-system
```

### Issue 2: Slow Response Times

**Symptoms**:
- API responses taking >10 seconds
- Timeout errors in client applications
- High response time metrics

**Diagnosis**:
```bash
# Check response time metrics
az monitor log-analytics query --workspace {workspace-id} --analytics-query "
AppRequests
| where TimeGenerated > ago(1h)
| summarize avg(DurationMs), percentile(DurationMs, 95) by Name
| order by avg_DurationMs desc"

# Check database performance
az monitor metrics list --resource /subscriptions/{sub}/resourceGroups/sktc-prod-rg/providers/Microsoft.DocumentDB/databaseAccounts/sktc-prod-cosmos --metric "TotalRequestUnits"

# Check cache hit rate
redis-cli -h sktc-prod-cache.redis.cache.windows.net info stats | grep keyspace_hits
```

**Solutions**:
```bash
# Scale up application
kubectl scale deployment api-gateway --replicas=8

# Increase database throughput
az cosmosdb sql container throughput update \
    --account-name sktc-prod-cosmos \
    --resource-group sktc-prod-rg \
    --database-name screenshot_to_code \
    --name users \
    --throughput 2000

# Clear slow cache entries
redis-cli -h sktc-prod-cache.redis.cache.windows.net EVAL "
for i, name in ipairs(redis.call('KEYS', ARGV[1])) do
  local ttl = redis.call('TTL', name)
  if ttl > 3600 then
    redis.call('DEL', name)
  end
end" 0 "*"

# Enable performance optimizations
kubectl patch deployment api-gateway -p '{"spec":{"template":{"spec":{"containers":[{"name":"api-gateway","env":[{"name":"PERFORMANCE_MODE","value":"aggressive"}]}]}}}}'
```

### Issue 3: Authentication Failures

**Symptoms**:
- 401 Unauthorized responses
- "Invalid token" errors
- Users unable to log in

**Diagnosis**:
```bash
# Check authentication service status
kubectl logs deployment/auth-service --tail=50

# Verify Azure AD configuration
az ad app show --id {app-id} --query "identifierUris"

# Check token validation
curl -H "Authorization: Bearer {test-token}" https://api.screenshot-to-code.com/health

# Review failed authentication logs
az monitor log-analytics query --workspace {workspace-id} --analytics-query "
SigninLogs
| where TimeGenerated > ago(1h)
| where ResultType != '0'
| project TimeGenerated, UserPrincipalName, ResultType, ResultDescription"
```

**Solutions**:
```bash
# Restart authentication service
kubectl rollout restart deployment/auth-service

# Update authentication configuration
kubectl patch configmap auth-config -p '{"data":{"AZURE_AD_TENANT_ID":"correct-tenant-id"}}'

# Refresh service secrets
az keyvault secret show --vault-name sktc-prod-kv --name azure-ad-client-secret
kubectl create secret generic auth-secrets --from-literal=client-secret="new-secret" --dry-run=client -o yaml | kubectl apply -f -

# Clear authentication cache
redis-cli -h sktc-prod-cache.redis.cache.windows.net DEL "auth:*"
```

### Issue 4: Database Connection Issues

**Symptoms**:
- "Connection timeout" errors
- Database queries failing
- High database latency

**Diagnosis**:
```bash
# Check Cosmos DB status
az cosmosdb show --name sktc-prod-cosmos --resource-group sktc-prod-rg --query "readLocations[0].provisioningState"

# Check connection string
az keyvault secret show --vault-name sktc-prod-kv --name cosmosdb-connection-string

# Test connectivity from service
kubectl exec deployment/api-gateway -- nslookup sktc-prod-cosmos.documents.azure.com

# Check database metrics
az monitor metrics list --resource /subscriptions/{sub}/resourceGroups/sktc-prod-rg/providers/Microsoft.DocumentDB/databaseAccounts/sktc-prod-cosmos --metric "TotalRequestUnits,ProvisionedThroughput"
```

**Solutions**:
```bash
# Restart services to refresh connections
kubectl rollout restart deployment/api-gateway
kubectl rollout restart deployment/code-generation-service

# Increase connection pool size
kubectl patch deployment api-gateway -p '{"spec":{"template":{"spec":{"containers":[{"name":"api-gateway","env":[{"name":"DB_POOL_SIZE","value":"20"}]}]}}}}'

# Scale up database throughput
az cosmosdb sql database throughput update \
    --account-name sktc-prod-cosmos \
    --resource-group sktc-prod-rg \
    --name screenshot_to_code \
    --throughput 1000

# Update connection string if needed
kubectl create secret generic db-connection --from-literal=connection-string="new-connection-string" --dry-run=client -o yaml | kubectl apply -f -
```

---

## Service-Specific Troubleshooting

### API Gateway Service Issues

**Common Problems**:
```yaml
Issue: High Memory Usage
Symptoms: 
  - Out of memory errors
  - Pod restarts
  - Slow response times
  
Diagnosis:
  - Check memory metrics: kubectl top pod {api-gateway-pod}
  - Review memory limits: kubectl describe pod {api-gateway-pod}
  - Check for memory leaks in logs
  
Solutions:
  - Increase memory limits
  - Restart service to clear memory
  - Enable garbage collection tuning
  - Investigate memory leaks in code
```

**Troubleshooting Commands**:
```bash
# Check API Gateway health
kubectl logs deployment/api-gateway | grep -E "(ERROR|WARN|Memory)" | tail -20

# Monitor resource usage
kubectl top pod --selector=app=api-gateway

# Check service configuration
kubectl get configmap api-gateway-config -o yaml

# Test specific endpoints
curl -v https://api.screenshot-to-code.com/api/v1/health
curl -v https://api.screenshot-to-code.com/api/v1/generate-code
```

### Image Processing Service Issues

**Common Problems**:
```yaml
Issue: Image Upload Failures
Symptoms:
  - "File too large" errors
  - "Invalid format" errors
  - Upload timeouts
  
Diagnosis:
  - Check file size limits in configuration
  - Verify supported formats
  - Check storage connectivity
  - Review processing logs
  
Solutions:
  - Adjust file size limits
  - Add format validation
  - Check blob storage connectivity
  - Optimize image processing pipeline
```

**Troubleshooting Commands**:
```bash
# Check image processing service
kubectl logs deployment/image-processing-service | grep -E "(upload|error|timeout)" | tail -20

# Test image upload
curl -X POST -F "image=@test-image.png" https://api.screenshot-to-code.com/api/v1/upload

# Check storage connectivity
kubectl exec deployment/image-processing-service -- az storage blob list --account-name sktcstorage --container-name images | head -5

# Monitor processing times
az monitor log-analytics query --workspace {workspace-id} --analytics-query "
AppRequests
| where Name contains 'upload'
| where TimeGenerated > ago(1h)
| summarize avg(DurationMs) by bin(TimeGenerated, 5m)"
```

### Code Generation Service Issues

**Common Problems**:
```yaml
Issue: AI Provider Timeouts
Symptoms:
  - "Request timeout" errors
  - Incomplete code generation
  - High response times
  
Diagnosis:
  - Check AI provider status
  - Review timeout configurations
  - Monitor provider response times
  - Check provider rate limits
  
Solutions:
  - Increase timeout values
  - Implement provider fallback
  - Optimize prompt size
  - Monitor provider quotas
```

**Troubleshooting Commands**:
```bash
# Check code generation service
kubectl logs deployment/code-generation-service | grep -E "(timeout|provider|error)" | tail -20

# Test code generation
curl -X POST -H "Content-Type: application/json" -d '{"image_url":"test-url","framework":"react"}' https://api.screenshot-to-code.com/api/v1/generate-code

# Check AI provider connectivity
kubectl exec deployment/code-generation-service -- curl -s https://api.openai.com/v1/models | head -20

# Monitor generation success rates
az monitor log-analytics query --workspace {workspace-id} --analytics-query "
AppRequests
| where Name contains 'generate-code'
| where TimeGenerated > ago(1h)
| summarize SuccessRate = 100.0 * countif(Success == true) / count() by bin(TimeGenerated, 15m)"
```

---

## Performance Issues

### High CPU Usage

**Diagnosis Steps**:
```bash
# Identify high CPU pods
kubectl top pods --all-namespaces --sort-by=cpu | head -10

# Check CPU metrics over time
az monitor metrics list --resource {app-service-id} --metric "CpuPercentage" --start-time $(date -u -d '1 hour ago' '+%Y-%m-%dT%H:%M:%SZ')

# Analyze CPU usage patterns
az monitor log-analytics query --workspace {workspace-id} --analytics-query "
Perf
| where TimeGenerated > ago(1h)
| where ObjectName == 'Processor'
| where CounterName == '% Processor Time'
| summarize avg(CounterValue) by bin(TimeGenerated, 5m), Computer"
```

**Resolution Actions**:
```bash
# Scale up pods
kubectl scale deployment api-gateway --replicas=6

# Increase CPU limits
kubectl patch deployment api-gateway -p '{"spec":{"template":{"spec":{"containers":[{"name":"api-gateway","resources":{"limits":{"cpu":"2000m"}}}]}}}}'

# Enable CPU profiling
kubectl patch deployment api-gateway -p '{"spec":{"template":{"spec":{"containers":[{"name":"api-gateway","env":[{"name":"ENABLE_PROFILING","value":"true"}]}]}}}}'

# Check for CPU-intensive processes
kubectl exec deployment/api-gateway -- top -b -n 1 | head -20
```

### High Memory Usage

**Diagnosis Steps**:
```bash
# Check memory usage
kubectl top pods --all-namespaces --sort-by=memory | head -10

# Analyze memory trends
az monitor metrics list --resource {app-service-id} --metric "MemoryPercentage"

# Check for memory leaks
kubectl exec deployment/api-gateway -- cat /proc/meminfo
```

**Resolution Actions**:
```bash
# Increase memory limits
kubectl patch deployment api-gateway -p '{"spec":{"template":{"spec":{"containers":[{"name":"api-gateway","resources":{"limits":{"memory":"2Gi"}}}]}}}}'

# Restart services to free memory
kubectl rollout restart deployment/api-gateway

# Enable garbage collection tuning
kubectl patch deployment api-gateway -p '{"spec":{"template":{"spec":{"containers":[{"name":"api-gateway","env":[{"name":"PYTHONUNBUFFERED","value":"1"},{"name":"GC_ENABLE","value":"true"}]}]}}}}'
```

### Database Performance Issues

**Diagnosis Steps**:
```bash
# Check Cosmos DB metrics
az monitor metrics list --resource /subscriptions/{sub}/resourceGroups/sktc-prod-rg/providers/Microsoft.DocumentDB/databaseAccounts/sktc-prod-cosmos --metric "TotalRequestUnits,NormalizedRUConsumption"

# Analyze slow queries
az monitor log-analytics query --workspace {workspace-id} --analytics-query "
AppDependencies
| where Type == 'Azure DocumentDB'
| where TimeGenerated > ago(1h)
| where DurationMs > 1000
| order by DurationMs desc
| take 10"

# Check database connectivity
kubectl exec deployment/api-gateway -- python -c "
import os
from azure.cosmos import CosmosClient
client = CosmosClient(os.environ['COSMOS_CONNECTION_STRING'])
print('Database accessible:', client.list_databases())
"
```

**Resolution Actions**:
```bash
# Increase database throughput
az cosmosdb sql container throughput update \
    --account-name sktc-prod-cosmos \
    --resource-group sktc-prod-rg \
    --database-name screenshot_to_code \
    --name users \
    --throughput 2000

# Optimize queries
# Review and add indexes in Azure portal

# Implement connection pooling
kubectl patch deployment api-gateway -p '{"spec":{"template":{"spec":{"containers":[{"name":"api-gateway","env":[{"name":"DB_CONNECTION_POOL_SIZE","value":"50"}]}]}}}}'
```

---

## Database Issues

### Connection Pool Exhaustion

**Symptoms**:
- "Connection pool exhausted" errors
- Intermittent database connectivity issues
- High connection count metrics

**Diagnosis**:
```bash
# Check current connections
az monitor log-analytics query --workspace {workspace-id} --analytics-query "
AppDependencies
| where Type == 'Azure DocumentDB'
| where TimeGenerated > ago(1h)
| summarize ConnectionCount = dcount(Id) by bin(TimeGenerated, 5m)"

# Check connection pool configuration
kubectl describe deployment api-gateway | grep -A 5 -B 5 DB_POOL_SIZE
```

**Solutions**:
```bash
# Increase connection pool size
kubectl patch deployment api-gateway -p '{"spec":{"template":{"spec":{"containers":[{"name":"api-gateway","env":[{"name":"DB_POOL_SIZE","value":"100"}]}]}}}}'

# Implement connection retry logic
kubectl patch deployment api-gateway -p '{"spec":{"template":{"spec":{"containers":[{"name":"api-gateway","env":[{"name":"DB_RETRY_COUNT","value":"3"}]}]}}}}'

# Monitor connection usage
az monitor log-analytics query --workspace {workspace-id} --analytics-query "
AppDependencies
| where Type == 'Azure DocumentDB'
| where TimeGenerated > ago(1h)
| summarize ActiveConnections = count() by bin(TimeGenerated, 5m)"
```

### Query Performance Issues

**Symptoms**:
- Slow database queries (>1000ms)
- High RU consumption
- Query timeout errors

**Diagnosis**:
```bash
# Identify slow queries
az monitor log-analytics query --workspace {workspace-id} --analytics-query "
AppDependencies
| where Type == 'Azure DocumentDB'
| where DurationMs > 1000
| order by DurationMs desc
| project TimeGenerated, Data, DurationMs"

# Check RU consumption
az cosmosdb sql container show --account-name sktc-prod-cosmos --resource-group sktc-prod-rg --database-name screenshot_to_code --name users --query "throughputPolicy"
```

**Solutions**:
```bash
# Add database indexes (via Azure portal or SDK)
# Example: Add index on frequently queried fields

# Increase container throughput temporarily
az cosmosdb sql container throughput update \
    --account-name sktc-prod-cosmos \
    --resource-group sktc-prod-rg \
    --database-name screenshot_to_code \
    --name users \
    --throughput 3000

# Implement query optimization
kubectl patch configmap api-gateway-config -p '{"data":{"ENABLE_QUERY_OPTIMIZATION":"true"}}'
```

---

## AI Provider Issues

### OpenAI API Issues

**Common Problems**:
```yaml
Rate Limiting:
  Symptoms: "Rate limit exceeded" errors
  Diagnosis: Check API usage in OpenAI dashboard
  Solutions: 
    - Implement exponential backoff
    - Switch to alternative provider
    - Increase rate limits with OpenAI

Model Unavailability:
  Symptoms: "Model not available" errors
  Diagnosis: Check OpenAI status page
  Solutions:
    - Use fallback model
    - Switch to alternative provider
    - Wait for service restoration
```

**Troubleshooting Commands**:
```bash
# Test OpenAI connectivity
curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models

# Check API usage
kubectl logs deployment/code-generation-service | grep -i "openai" | tail -20

# Monitor OpenAI response times
az monitor log-analytics query --workspace {workspace-id} --analytics-query "
AppDependencies
| where Target contains 'openai'
| where TimeGenerated > ago(1h)
| summarize avg(DurationMs), count() by bin(TimeGenerated, 15m)"

# Switch to fallback provider
kubectl patch configmap ai-config -p '{"data":{"PRIMARY_PROVIDER":"anthropic"}}'
```

### Anthropic Claude Issues

**Common Problems**:
```yaml
Authentication Issues:
  Symptoms: "Invalid API key" errors
  Diagnosis: Verify API key in Key Vault
  Solutions:
    - Refresh API key
    - Check key permissions
    - Verify service configuration

Context Length Exceeded:
  Symptoms: "Context too long" errors
  Diagnosis: Check prompt length
  Solutions:
    - Truncate prompts
    - Use summarization
    - Switch to model with larger context
```

**Troubleshooting Commands**:
```bash
# Test Anthropic connectivity
curl -H "Authorization: Bearer $ANTHROPIC_API_KEY" -H "Content-Type: application/json" -d '{"model":"claude-3-sonnet-20240229","messages":[{"role":"user","content":"Hello"}],"max_tokens":100}' https://api.anthropic.com/v1/messages

# Check API key status
az keyvault secret show --vault-name sktc-prod-kv --name anthropic-api-key

# Monitor Claude usage
kubectl logs deployment/code-generation-service | grep -i "claude" | tail -20
```

### Provider Failover

**Automatic Failover Configuration**:
```bash
# Enable automatic failover
kubectl patch configmap ai-config -p '{"data":{"ENABLE_FAILOVER":"true","FAILOVER_THRESHOLD":"3","FAILOVER_TIMEOUT":"30"}}'

# Check failover status
kubectl logs deployment/code-generation-service | grep -i "failover"

# Test failover manually
kubectl patch configmap ai-config -p '{"data":{"FORCE_FAILOVER":"true"}}'

# Monitor provider health
kubectl exec deployment/code-generation-service -- curl -s http://localhost:8080/health/ai-providers
```

---

## Security and Authentication Issues

### Token Validation Failures

**Symptoms**:
- "Invalid token" errors
- 401 Unauthorized responses
- Token expiration issues

**Diagnosis**:
```bash
# Check token validation logs
kubectl logs deployment/auth-service | grep -i "token" | tail -20

# Verify JWT configuration
kubectl get configmap auth-config -o yaml | grep -A 10 JWT

# Test token validation
curl -H "Authorization: Bearer {test-token}" -v https://api.screenshot-to-code.com/api/v1/user/profile
```

**Solutions**:
```bash
# Refresh JWT signing keys
az keyvault secret set --vault-name sktc-prod-kv --name jwt-signing-key --value "new-signing-key"

# Update token validation settings
kubectl patch configmap auth-config -p '{"data":{"TOKEN_EXPIRY":"3600","REFRESH_TOKEN_EXPIRY":"86400"}}'

# Restart authentication service
kubectl rollout restart deployment/auth-service

# Clear authentication cache
redis-cli -h sktc-prod-cache.redis.cache.windows.net DEL "auth:tokens:*"
```

### Azure AD Integration Issues

**Symptoms**:
- Login redirects failing
- "Invalid client" errors
- Consent issues

**Diagnosis**:
```bash
# Check Azure AD configuration
az ad app show --id {app-id} --query "{displayName: displayName, replyUrls: replyUrls, identifierUris: identifierUris}"

# Review authentication logs
az monitor log-analytics query --workspace {workspace-id} --analytics-query "
SigninLogs
| where TimeGenerated > ago(1h)
| where AppDisplayName == 'Screenshot-to-Code'
| project TimeGenerated, UserPrincipalName, ResultType, ResultDescription"

# Check service principal permissions
az ad sp show --id {service-principal-id} --query "appRoles"
```

**Solutions**:
```bash
# Update redirect URIs
az ad app update --id {app-id} --reply-urls "https://api.screenshot-to-code.com/auth/callback"

# Refresh client secret
az ad app credential reset --id {app-id} --append

# Update service configuration
kubectl create secret generic azure-ad-config \
    --from-literal=client-id="new-client-id" \
    --from-literal=client-secret="new-client-secret" \
    --from-literal=tenant-id="tenant-id" \
    --dry-run=client -o yaml | kubectl apply -f -
```

### API Key Management Issues

**Symptoms**:
- "Invalid API key" errors
- Key rotation failures
- Unauthorized access

**Diagnosis**:
```bash
# Check API key usage
az monitor log-analytics query --workspace {workspace-id} --analytics-query "
AppRequests
| where TimeGenerated > ago(1h)
| extend ApiKey = tostring(customDimensions.ApiKey)
| summarize RequestCount = count() by ApiKey
| order by RequestCount desc"

# Verify key vault access
az keyvault secret list --vault-name sktc-prod-kv --query "[].name"

# Check key rotation status
kubectl logs job/key-rotation-job | tail -20
```

**Solutions**:
```bash
# Rotate API keys
python scripts/rotate_api_keys.py --rotate-all

# Update key references
kubectl patch configmap api-config -p '{"data":{"API_KEY_REF":"kv://sktc-prod-kv/new-api-key"}}'

# Revoke compromised keys
az keyvault secret set --vault-name sktc-prod-kv --name old-api-key --value "REVOKED"

# Enable key usage monitoring
kubectl apply -f monitoring/api-key-monitoring.yaml
```

---

## Network and Connectivity Issues

### DNS Resolution Problems

**Symptoms**:
- Service discovery failures
- "Name not found" errors
- Intermittent connectivity

**Diagnosis**:
```bash
# Test DNS resolution
kubectl exec deployment/api-gateway -- nslookup code-generation-service
kubectl exec deployment/api-gateway -- nslookup sktc-prod-cosmos.documents.azure.com

# Check DNS configuration
kubectl get configmap coredns -n kube-system -o yaml

# Test external DNS
kubectl exec deployment/api-gateway -- nslookup google.com
```

**Solutions**:
```bash
# Restart DNS pods
kubectl delete pods -n kube-system -l k8s-app=kube-dns

# Update DNS configuration
kubectl patch configmap coredns -n kube-system -p '{"data":{"Corefile":"# DNS configuration here"}}'

# Flush DNS cache
kubectl exec deployment/api-gateway -- systemd-resolve --flush-caches

# Add custom DNS entries
kubectl patch configmap coredns -n kube-system -p '{"data":{"hosts":"custom-host.example.com 1.2.3.4"}}'
```

### Load Balancer Issues

**Symptoms**:
- Uneven traffic distribution
- Health check failures
- Connection timeouts

**Diagnosis**:
```bash
# Check load balancer status
az network lb show --name sktc-prod-lb --resource-group sktc-prod-rg --query "provisioningState"

# Check backend pool health
az network lb show --name sktc-prod-lb --resource-group sktc-prod-rg --query "backendAddressPools[0].backendIpConfigurations"

# Test load balancer endpoints
for i in {1..10}; do curl -s https://api.screenshot-to-code.com/health | jq '.hostname'; done
```

**Solutions**:
```bash
# Update health probe configuration
az network lb probe update \
    --resource-group sktc-prod-rg \
    --lb-name sktc-prod-lb \
    --name health-probe \
    --path /health \
    --interval 30

# Add backend pool members
az network lb address-pool address add \
    --resource-group sktc-prod-rg \
    --lb-name sktc-prod-lb \
    --pool-name backend-pool \
    --name new-backend \
    --ip-address 10.0.1.10

# Update load balancing rules
az network lb rule update \
    --resource-group sktc-prod-rg \
    --lb-name sktc-prod-lb \
    --name http-rule \
    --load-distribution SourceIP
```

### Network Security Group Issues

**Symptoms**:
- Connection refused errors
- Blocked traffic
- Timeout on specific ports

**Diagnosis**:
```bash
# Check NSG rules
az network nsg list --resource-group sktc-prod-rg

# Review effective security rules
az network nic list-effective-nsg --ids {nic-id}

# Test port connectivity
kubectl exec deployment/api-gateway -- nc -zv sktc-prod-cosmos.documents.azure.com 443
```

**Solutions**:
```bash
# Add allow rule for required ports
az network nsg rule create \
    --resource-group sktc-prod-rg \
    --nsg-name sktc-prod-nsg \
    --name allow-https \
    --priority 1000 \
    --access Allow \
    --protocol Tcp \
    --destination-port-ranges 443

# Update existing rule
az network nsg rule update \
    --resource-group sktc-prod-rg \
    --nsg-name sktc-prod-nsg \
    --name existing-rule \
    --access Allow

# Check rule effectiveness
az network watcher next-hop \
    --resource-group sktc-prod-rg \
    --vm {vm-name} \
    --source-ip 10.0.1.4 \
    --dest-ip 10.0.2.4
```

---

## Monitoring and Logging

### Log Analysis

**Common Log Patterns**:
```bash
# Error pattern analysis
az monitor log-analytics query --workspace {workspace-id} --analytics-query "
union AppExceptions, AppTraces
| where TimeGenerated > ago(1h)
| where SeverityLevel >= 3
| summarize ErrorCount = count() by tostring(Message), SeverityLevel
| order by ErrorCount desc"

# Performance pattern analysis
az monitor log-analytics query --workspace {workspace-id} --analytics-query "
AppRequests
| where TimeGenerated > ago(1h)
| summarize 
    AvgDuration = avg(DurationMs),
    MaxDuration = max(DurationMs),
    RequestCount = count()
by Name
| order by AvgDuration desc"

# User activity analysis
az monitor log-analytics query --workspace {workspace-id} --analytics-query "
AppRequests
| where TimeGenerated > ago(1h)
| extend UserId = tostring(customDimensions.UserId)
| summarize UniqueUsers = dcount(UserId), TotalRequests = count()
| project UniqueUsers, TotalRequests, AvgRequestsPerUser = TotalRequests/UniqueUsers"
```

### Metric Collection Issues

**Symptoms**:
- Missing metrics in dashboards
- Incomplete monitoring data
- Alert delays

**Diagnosis**:
```bash
# Check monitoring agent status
kubectl get pods -n kube-system | grep monitoring

# Verify metric collection
az monitor metrics list --resource {resource-id} --metric "CpuPercentage" | head -10

# Check Application Insights connection
az monitor app-insights component show --app sktc-prod-insights --resource-group sktc-prod-rg
```

**Solutions**:
```bash
# Restart monitoring agents
kubectl rollout restart daemonset/monitoring-agent -n kube-system

# Update monitoring configuration
kubectl patch configmap monitoring-config -p '{"data":{"collection_interval":"30s"}}'

# Verify instrumentation keys
az keyvault secret show --vault-name sktc-prod-kv --name app-insights-key

# Restart services to refresh telemetry
kubectl rollout restart deployment/api-gateway
```

### Alert Configuration Issues

**Symptoms**:
- Missing alerts during incidents
- False positive alerts
- Alert fatigue

**Diagnosis**:
```bash
# Check alert rules
az monitor metrics alert list --resource-group sktc-prod-rg

# Review alert history
az monitor activity-log list --start-time $(date -u -d '24 hours ago' '+%Y-%m-%dT%H:%M:%SZ') --select EventName,Status

# Test alert conditions
az monitor metrics alert show --name "High CPU Alert" --resource-group sktc-prod-rg
```

**Solutions**:
```bash
# Update alert thresholds
az monitor metrics alert update \
    --name "High CPU Alert" \
    --resource-group sktc-prod-rg \
    --threshold 80 \
    --evaluation-frequency 5m

# Add missing alerts
az monitor metrics alert create \
    --name "Database High RU" \
    --resource-group sktc-prod-rg \
    --resource sktc-prod-cosmos \
    --metric "TotalRequestUnits" \
    --operator GreaterThan \
    --threshold 800 \
    --action-group operations-team

# Configure alert correlation
az monitor action-group create \
    --name operations-team \
    --resource-group sktc-prod-rg \
    --email ops-team@company.com \
    --sms +1-555-0101
```

---

## Emergency Response Procedures

### Critical System Outage

**Immediate Actions (0-5 minutes)**:
```bash
# 1. Acknowledge the incident
echo "Incident acknowledged at $(date)" | tee -a incident.log

# 2. Check overall system status
curl -s https://api.screenshot-to-code.com/health || echo "API DOWN"
kubectl get pods --all-namespaces | grep -v Running

# 3. Identify scope of outage
python scripts/outage_assessment.py --quick-check

# 4. Activate incident response team
# Send alert to ops-team@company.com
# Update status page: https://status.screenshot-to-code.com
```

**Investigation Actions (5-15 minutes)**:
```bash
# 1. Check recent deployments
kubectl rollout history deployment/api-gateway
kubectl rollout history deployment/code-generation-service

# 2. Review error logs
az monitor log-analytics query --workspace {workspace-id} --analytics-query "
union AppExceptions, AppTraces
| where TimeGenerated > ago(30m)
| where SeverityLevel >= 3
| order by TimeGenerated desc
| take 20"

# 3. Check infrastructure status
az resource list --resource-group sktc-prod-rg --query "[].{name:name,state:properties.provisioningState}"

# 4. Identify root cause
python scripts/root_cause_analysis.py --incident-time "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
```

**Recovery Actions (15-60 minutes)**:
```bash
# Based on root cause, execute appropriate recovery:

# If deployment issue:
kubectl rollout undo deployment/api-gateway
kubectl rollout undo deployment/code-generation-service

# If infrastructure issue:
az vm restart --ids {vm-ids}
az webapp restart --name sktc-prod-app --resource-group sktc-prod-rg

# If database issue:
az cosmosdb failover --name sktc-prod-cosmos --resource-group sktc-prod-rg --failover-region "West US 2"

# If cache issue:
redis-cli -h sktc-prod-cache.redis.cache.windows.net FLUSHALL
kubectl rollout restart deployment/api-gateway
```

### Escalation Procedures

**When to Escalate**:
- No progress after 30 minutes
- Customer-facing impact continues
- Multiple failed recovery attempts
- Security incident suspected

**Escalation Steps**:
```bash
# 1. Contact next level support
echo "Escalating to Level 2 at $(date)" | tee -a incident.log
# Call: +1-555-0201 (Senior Engineer)

# 2. Provide incident summary
python scripts/incident_summary.py --incident-id {incident-id} --send-email

# 3. Continue monitoring and documentation
tail -f incident.log &
kubectl logs --all-containers=true --follow --selector=app=api-gateway &

# 4. Prepare for stakeholder communication
python scripts/stakeholder_update.py --incident-id {incident-id} --status "escalated"
```

---

## Conclusion

This troubleshooting guide provides systematic approaches to diagnose and resolve common issues in the Screenshot-to-Code system. Key points to remember:

1. **Follow the systematic troubleshooting methodology**
2. **Collect comprehensive information before making changes**
3. **Document all actions and results**
4. **Escalate appropriately when needed**
5. **Update this guide with new solutions discovered**

### Additional Resources

- **System Architecture**: `/docs/knowledge-transfer/system-architecture.md`
- **Operations Runbook**: `/docs/knowledge-transfer/operations-runbook.md`
- **API Documentation**: `https://api.screenshot-to-code.com/docs`
- **Monitoring Dashboards**: Azure Portal Workbooks
- **Status Page**: `https://status.screenshot-to-code.com`

---

**Document Prepared By**: Technical Support Team  
**Review Schedule**: Monthly  
**Next Review Date**: February 15, 2025  
**Document Owner**: Lead Support Engineer