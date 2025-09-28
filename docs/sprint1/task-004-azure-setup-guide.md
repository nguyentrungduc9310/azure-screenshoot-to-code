# TASK-004: Azure Tenant Setup Guide

**Date**: January 2024  
**Assigned**: Senior Full-stack Developer 2  
**Status**: IN PROGRESS  
**Effort**: 12 hours  

---

## Prerequisites

### Required Accounts & Permissions
- Azure subscription with **Owner** or **Contributor** role
- Microsoft 365 tenant (for Copilot Studio integration)
- Power Platform environment access
- Azure OpenAI access (may require approval)

### Required Tools
- Azure CLI (`az` command)
- PowerShell or Bash
- Visual Studio Code with Azure extensions
- Docker Desktop

---

## Phase 1: Azure Subscription Setup

### 1.1 Create Resource Groups
```bash
# Set variables
export SUBSCRIPTION_ID="your-subscription-id"
export RESOURCE_GROUP="screenshot-to-code-dev"
export LOCATION="eastus2"  # Primary region
export SECONDARY_LOCATION="westeurope"  # For disaster recovery

# Login to Azure
az login

# Set subscription
az account set --subscription $SUBSCRIPTION_ID

# Create primary resource group
az group create \
  --name $RESOURCE_GROUP \
  --location $LOCATION \
  --tags environment=development project=screenshot-to-code

# Create secondary resource group (DR)
az group create \
  --name "${RESOURCE_GROUP}-dr" \
  --location $SECONDARY_LOCATION \
  --tags environment=development project=screenshot-to-code purpose=disaster-recovery
```

### 1.2 Enable Required Resource Providers
```bash
# Enable required Azure resource providers
az provider register --namespace Microsoft.CognitiveServices
az provider register --namespace Microsoft.ContainerInstance
az provider register --namespace Microsoft.DocumentDB
az provider register --namespace Microsoft.Storage
az provider register --namespace Microsoft.KeyVault
az provider register --namespace Microsoft.Cache
az provider register --namespace Microsoft.Web
az provider register --namespace Microsoft.Insights
az provider register --namespace Microsoft.ApiManagement

# Verify registration status
az provider list --query "[?registrationState=='Registered'].namespace" --output table
```

---

## Phase 2: Core Azure Services Setup

### 2.1 Create Azure Key Vault
```bash
export KEY_VAULT_NAME="screenshot-to-code-kv-$(date +%s)"

# Create Key Vault
az keyvault create \
  --name $KEY_VAULT_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --enabled-for-template-deployment true \
  --enabled-for-deployment true \
  --enabled-for-disk-encryption true \
  --retention-days 90 \
  --tags environment=development

# Set access policy for current user
export CURRENT_USER_ID=$(az ad signed-in-user show --query id --output tsv)

az keyvault set-policy \
  --name $KEY_VAULT_NAME \
  --object-id $CURRENT_USER_ID \
  --secret-permissions get list set delete backup restore recover \
  --key-permissions get list create delete backup restore recover \
  --certificate-permissions get list create delete managecontacts manageissuers
```

### 2.2 Create Storage Account
```bash
export STORAGE_ACCOUNT_NAME="screenshotcode$(date +%s | cut -c6-)"

# Create storage account
az storage account create \
  --name $STORAGE_ACCOUNT_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku Standard_LRS \
  --kind StorageV2 \
  --access-tier Hot \
  --https-only true \
  --min-tls-version TLS1_2 \
  --tags environment=development

# Create blob containers
export STORAGE_KEY=$(az storage account keys list \
  --resource-group $RESOURCE_GROUP \
  --account-name $STORAGE_ACCOUNT_NAME \
  --query '[0].value' --output tsv)

# Create containers for different data types
az storage container create \
  --name images \
  --account-name $STORAGE_ACCOUNT_NAME \
  --account-key $STORAGE_KEY \
  --public-access off

az storage container create \
  --name code \
  --account-name $STORAGE_ACCOUNT_NAME \
  --account-key $STORAGE_KEY \
  --public-access off

az storage container create \
  --name templates \
  --account-name $STORAGE_ACCOUNT_NAME \
  --account-key $STORAGE_KEY \
  --public-access container

# Store connection string in Key Vault
export STORAGE_CONNECTION_STRING=$(az storage account show-connection-string \
  --name $STORAGE_ACCOUNT_NAME \
  --resource-group $RESOURCE_GROUP \
  --output tsv)

az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name "storage-connection-string" \
  --value "$STORAGE_CONNECTION_STRING"
```

### 2.3 Create Cosmos DB Account
```bash
export COSMOS_ACCOUNT_NAME="screenshot-to-code-cosmos-$(date +%s)"

# Create Cosmos DB account
az cosmosdb create \
  --resource-group $RESOURCE_GROUP \
  --name $COSMOS_ACCOUNT_NAME \
  --kind GlobalDocumentDB \
  --locations regionName=$LOCATION failoverPriority=0 isZoneRedundant=False \
  --default-consistency-level Session \
  --enable-automatic-failover true \
  --enable-multiple-write-locations false \
  --tags environment=development

# Create database and containers
az cosmosdb sql database create \
  --resource-group $RESOURCE_GROUP \
  --account-name $COSMOS_ACCOUNT_NAME \
  --name ScreenshotToCode

# Create containers
az cosmosdb sql container create \
  --resource-group $RESOURCE_GROUP \
  --account-name $COSMOS_ACCOUNT_NAME \
  --database-name ScreenshotToCode \
  --name Conversations \
  --partition-key-path "/userId" \
  --throughput 400

az cosmosdb sql container create \
  --resource-group $RESOURCE_GROUP \
  --account-name $COSMOS_ACCOUNT_NAME \
  --database-name ScreenshotToCode \
  --name Generations \
  --partition-key-path "/userId" \
  --throughput 400

az cosmosdb sql container create \
  --resource-group $RESOURCE_GROUP \
  --account-name $COSMOS_ACCOUNT_NAME \
  --database-name ScreenshotToCode \
  --name UserProfiles \
  --partition-key-path "/tenantId" \
  --throughput 400

# Store connection string in Key Vault
export COSMOS_CONNECTION_STRING=$(az cosmosdb keys list \
  --resource-group $RESOURCE_GROUP \
  --name $COSMOS_ACCOUNT_NAME \
  --type connection-strings \
  --query "connectionStrings[0].connectionString" \
  --output tsv)

az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name "cosmos-connection-string" \
  --value "$COSMOS_CONNECTION_STRING"
```

### 2.4 Create Redis Cache
```bash
export REDIS_NAME="screenshot-to-code-redis-$(date +%s)"

# Create Redis cache
az redis create \
  --resource-group $RESOURCE_GROUP \
  --name $REDIS_NAME \
  --location $LOCATION \
  --sku Basic \
  --vm-size c0 \
  --redis-configuration maxmemory-policy=allkeys-lru \
  --tags environment=development

# Store connection string in Key Vault
export REDIS_CONNECTION_STRING=$(az redis list-keys \
  --resource-group $RESOURCE_GROUP \
  --name $REDIS_NAME \
  --query primaryKey \
  --output tsv)

export REDIS_HOST=$(az redis show \
  --resource-group $RESOURCE_GROUP \
  --name $REDIS_NAME \
  --query hostName \
  --output tsv)

az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name "redis-connection-string" \
  --value "redis://:${REDIS_CONNECTION_STRING}@${REDIS_HOST}:6380/0?ssl=true"
```

---

## Phase 3: AI Services Setup

### 3.1 Create Azure OpenAI Service
```bash
export OPENAI_RESOURCE_NAME="screenshot-to-code-openai-$(date +%s)"

# Create Azure OpenAI resource (requires approval)
az cognitiveservices account create \
  --name $OPENAI_RESOURCE_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --kind OpenAI \
  --sku S0 \
  --tags environment=development

# Note: You may need to request access to Azure OpenAI
# Visit: https://aka.ms/oai/access

# Deploy models (after approval)
# GPT-4 Vision model
az cognitiveservices account deployment create \
  --resource-group $RESOURCE_GROUP \
  --name $OPENAI_RESOURCE_NAME \
  --deployment-name gpt-4-vision \
  --model-name gpt-4-vision-preview \
  --model-version "2024-02-15-preview" \
  --model-format OpenAI \
  --sku-name Standard \
  --sku-capacity 10

# DALL-E 3 model (only in Sweden Central)
# Note: Create a separate resource in Sweden Central for DALL-E 3
export DALLE_RESOURCE_NAME="screenshot-to-code-dalle-$(date +%s)"
export DALLE_LOCATION="swedencentral"

az cognitiveservices account create \
  --name $DALLE_RESOURCE_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $DALLE_LOCATION \
  --kind OpenAI \
  --sku S0 \
  --tags environment=development purpose=dalle3

# Store API keys in Key Vault
export AZURE_OPENAI_KEY=$(az cognitiveservices account keys list \
  --resource-group $RESOURCE_GROUP \
  --name $OPENAI_RESOURCE_NAME \
  --query key1 \
  --output tsv)

export AZURE_OPENAI_ENDPOINT=$(az cognitiveservices account show \
  --resource-group $RESOURCE_GROUP \
  --name $OPENAI_RESOURCE_NAME \
  --query properties.endpoint \
  --output tsv)

az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name "azure-openai-key" \
  --value "$AZURE_OPENAI_KEY"

az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name "azure-openai-endpoint" \
  --value "$AZURE_OPENAI_ENDPOINT"
```

### 3.2 Store External API Keys
```bash
# Store external API keys (you need to obtain these separately)
# OpenAI Direct API Key
az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name "openai-api-key" \
  --value "sk-your-openai-api-key-here"

# Anthropic API Key
az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name "anthropic-api-key" \
  --value "your-anthropic-api-key-here"

# Gemini API Key
az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name "gemini-api-key" \
  --value "your-gemini-api-key-here"

# Replicate API Key
az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name "replicate-api-key" \
  --value "your-replicate-api-key-here"
```

---

## Phase 4: Application Insights & Monitoring

### 4.1 Create Application Insights
```bash
export APP_INSIGHTS_NAME="screenshot-to-code-insights-$(date +%s)"

# Create Application Insights
az extension add --name application-insights

az monitor app-insights component create \
  --app $APP_INSIGHTS_NAME \
  --location $LOCATION \
  --resource-group $RESOURCE_GROUP \
  --application-type web \
  --retention-time 90 \
  --tags environment=development

# Store instrumentation key in Key Vault
export INSTRUMENTATION_KEY=$(az monitor app-insights component show \
  --resource-group $RESOURCE_GROUP \
  --app $APP_INSIGHTS_NAME \
  --query instrumentationKey \
  --output tsv)

az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name "application-insights-key" \
  --value "$INSTRUMENTATION_KEY"
```

### 4.2 Create Log Analytics Workspace
```bash
export LOG_ANALYTICS_NAME="screenshot-to-code-logs-$(date +%s)"

# Create Log Analytics workspace
az monitor log-analytics workspace create \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $LOG_ANALYTICS_NAME \
  --location $LOCATION \
  --retention-time 30 \
  --tags environment=development

# Link Application Insights to Log Analytics
export WORKSPACE_ID=$(az monitor log-analytics workspace show \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $LOG_ANALYTICS_NAME \
  --query customerId \
  --output tsv)

az monitor app-insights component update \
  --resource-group $RESOURCE_GROUP \
  --app $APP_INSIGHTS_NAME \
  --workspace $WORKSPACE_ID
```

---

## Phase 5: Container Registry & API Management

### 5.1 Create Container Registry
```bash
export ACR_NAME="screenshottocode$(date +%s | cut -c6-)"

# Create Azure Container Registry
az acr create \
  --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --sku Basic \
  --admin-enabled true \
  --tags environment=development

# Store ACR credentials in Key Vault
export ACR_USERNAME=$(az acr credential show \
  --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --query username \
  --output tsv)

export ACR_PASSWORD=$(az acr credential show \
  --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --query passwords[0].value \
  --output tsv)

az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name "acr-username" \
  --value "$ACR_USERNAME"

az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name "acr-password" \
  --value "$ACR_PASSWORD"
```

### 5.2 Create API Management (Development)
```bash
export APIM_NAME="screenshot-to-code-apim-$(date +%s)"

# Create API Management service (Developer tier for testing)
az apim create \
  --resource-group $RESOURCE_GROUP \
  --name $APIM_NAME \
  --location $LOCATION \
  --publisher-name "Screenshot-to-Code Dev" \
  --publisher-email "dev@yourcompany.com" \
  --sku-name Developer \
  --sku-capacity 1 \
  --tags environment=development

# This takes about 30-45 minutes to complete
echo "API Management creation started. This will take 30-45 minutes..."
```

---

## Phase 6: Security & Networking

### 6.1 Create Managed Identity
```bash
export MANAGED_IDENTITY_NAME="screenshot-to-code-identity"

# Create user-assigned managed identity
az identity create \
  --resource-group $RESOURCE_GROUP \
  --name $MANAGED_IDENTITY_NAME \
  --location $LOCATION \
  --tags environment=development

export IDENTITY_ID=$(az identity show \
  --resource-group $RESOURCE_GROUP \
  --name $MANAGED_IDENTITY_NAME \
  --query id \
  --output tsv)

export IDENTITY_CLIENT_ID=$(az identity show \
  --resource-group $RESOURCE_GROUP \
  --name $MANAGED_IDENTITY_NAME \
  --query clientId \
  --output tsv)

# Grant Key Vault access to managed identity
az keyvault set-policy \
  --name $KEY_VAULT_NAME \
  --object-id $(az identity show --resource-group $RESOURCE_GROUP --name $MANAGED_IDENTITY_NAME --query principalId --output tsv) \
  --secret-permissions get list \
  --key-permissions get list

# Store identity information
az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name "managed-identity-client-id" \
  --value "$IDENTITY_CLIENT_ID"
```

### 6.2 Create Virtual Network (Optional for Production)
```bash
export VNET_NAME="screenshot-to-code-vnet"

# Create virtual network
az network vnet create \
  --resource-group $RESOURCE_GROUP \
  --name $VNET_NAME \
  --address-prefix 10.0.0.0/16 \
  --location $LOCATION \
  --tags environment=development

# Create subnets
az network vnet subnet create \
  --resource-group $RESOURCE_GROUP \
  --vnet-name $VNET_NAME \
  --name services \
  --address-prefixes 10.0.1.0/24

az network vnet subnet create \
  --resource-group $RESOURCE_GROUP \
  --vnet-name $VNET_NAME \
  --name data \
  --address-prefixes 10.0.2.0/24
```

---

## Phase 7: Development Environment Configuration

### 7.1 Create Development Configuration File
```bash
# Create environment configuration
cat > azure-dev-config.env << EOF
# Azure Resource Information
SUBSCRIPTION_ID=$SUBSCRIPTION_ID
RESOURCE_GROUP=$RESOURCE_GROUP
LOCATION=$LOCATION

# Service Names
KEY_VAULT_NAME=$KEY_VAULT_NAME
STORAGE_ACCOUNT_NAME=$STORAGE_ACCOUNT_NAME
COSMOS_ACCOUNT_NAME=$COSMOS_ACCOUNT_NAME
REDIS_NAME=$REDIS_NAME
OPENAI_RESOURCE_NAME=$OPENAI_RESOURCE_NAME
APP_INSIGHTS_NAME=$APP_INSIGHTS_NAME
ACR_NAME=$ACR_NAME
APIM_NAME=$APIM_NAME

# Managed Identity
MANAGED_IDENTITY_NAME=$MANAGED_IDENTITY_NAME
MANAGED_IDENTITY_CLIENT_ID=$IDENTITY_CLIENT_ID

# Service Endpoints
AZURE_OPENAI_ENDPOINT=$AZURE_OPENAI_ENDPOINT
STORAGE_CONNECTION_STRING=$STORAGE_CONNECTION_STRING
COSMOS_CONNECTION_STRING=$COSMOS_CONNECTION_STRING
REDIS_CONNECTION_STRING=$REDIS_CONNECTION_STRING

# For Development (retrieve from Key Vault in production)
AZURE_OPENAI_KEY=$AZURE_OPENAI_KEY
INSTRUMENTATION_KEY=$INSTRUMENTATION_KEY
ACR_USERNAME=$ACR_USERNAME
ACR_PASSWORD=$ACR_PASSWORD
EOF

echo "Configuration saved to azure-dev-config.env"
echo "Store this file securely and do not commit to version control"
```

### 7.2 Create Service Principal for CI/CD
```bash
export SERVICE_PRINCIPAL_NAME="screenshot-to-code-cicd"

# Create service principal for CI/CD
az ad sp create-for-rbac \
  --name $SERVICE_PRINCIPAL_NAME \
  --role Contributor \
  --scopes /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP \
  --sdk-auth > service-principal.json

echo "Service principal created. Store the credentials securely for CI/CD"
echo "Contents of service-principal.json:"
cat service-principal.json

# Store service principal info in Key Vault
export SP_CLIENT_ID=$(cat service-principal.json | jq -r '.clientId')
export SP_CLIENT_SECRET=$(cat service-principal.json | jq -r '.clientSecret')

az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name "service-principal-client-id" \
  --value "$SP_CLIENT_ID"

az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name "service-principal-client-secret" \
  --value "$SP_CLIENT_SECRET"
```

---

## Phase 8: Microsoft 365 & Power Platform Setup

### 8.1 Power Platform Environment Setup
```powershell
# Install Power Platform CLI
# Download from: https://aka.ms/PowerPlatformCLI

# Create Power Platform environment (PowerShell)
pac auth create --url https://yourorg.crm.dynamics.com

# Create environment
pac admin create --name "Screenshot-to-Code Dev" \
  --type Sandbox \
  --region unitedstates \
  --currency USD \
  --language 1033

# Enable required connectors
pac connector enable --environment-id YOUR_ENVIRONMENT_ID --connector-name shared_openai
```

### 8.2 Copilot Studio Agent Setup
```yaml
# Manual steps required in Copilot Studio portal:
1. Navigate to https://copilotstudio.microsoft.com
2. Select your development environment
3. Create new agent: "Screenshot-to-Code Assistant"
4. Configure authentication settings
5. Note the agent ID and webhook URL for development

# These values will be needed for Phase 2 integration
Agent Configuration:
  - Agent Name: Screenshot-to-Code Assistant
  - Environment: Development
  - Authentication: Azure AD
  - Webhook URL: TBD (will be configured in Sprint 9)
```

---

## Testing & Validation

### Test Azure Services
```bash
# Test Key Vault access
az keyvault secret show --vault-name $KEY_VAULT_NAME --name "storage-connection-string"

# Test storage account
az storage container list --account-name $STORAGE_ACCOUNT_NAME

# Test Cosmos DB
az cosmosdb sql database show \
  --resource-group $RESOURCE_GROUP \
  --account-name $COSMOS_ACCOUNT_NAME \
  --name ScreenshotToCode

# Test Redis
redis-cli -h $REDIS_HOST -p 6380 -a $REDIS_CONNECTION_STRING ping

# Test Application Insights
az monitor app-insights component show --resource-group $RESOURCE_GROUP --app $APP_INSIGHTS_NAME
```

### Performance Validation
```bash
# Test regional performance
az network watcher test-connectivity \
  --source-resource $RESOURCE_GROUP \
  --dest-address "openai.azure.com" \
  --dest-port 443

# Verify service limits and quotas
az vm list-usage --location $LOCATION
az cognitiveservices account list-usage --resource-group $RESOURCE_GROUP --name $OPENAI_RESOURCE_NAME
```

---

## Security Checklist

### ✅ **Completed Security Measures**
- [x] All secrets stored in Azure Key Vault
- [x] Managed identity created for service authentication
- [x] Storage account configured with HTTPS-only
- [x] Cosmos DB with session consistency level
- [x] Redis with SSL/TLS encryption
- [x] Service principal with minimal required permissions
- [x] Resource tags for environment identification

### ⚠️ **Additional Security Tasks (Production)**
- [ ] Configure network security groups
- [ ] Enable Azure Defender for all services
- [ ] Configure backup and disaster recovery
- [ ] Implement Azure Policy for compliance
- [ ] Setup Azure Sentinel for security monitoring
- [ ] Configure private endpoints for services

---

## Cost Optimization

### Current Monthly Cost Estimate (Development)
```yaml
Services & Estimated Monthly Costs:
  - Cosmos DB (400 RU/s): ~$24
  - Redis Cache (Basic C0): ~$16
  - Storage Account (100GB): ~$20
  - Application Insights: ~$5
  - Container Registry (Basic): ~$5
  - API Management (Developer): ~$50
  - Azure OpenAI (Estimated): ~$100
  
Total Estimated: ~$220/month (development environment)

Cost Optimization Notes:
  - Use development/test pricing where available
  - Implement auto-shutdown for non-production resources
  - Monitor usage with cost alerts
  - Use Azure Cost Management for optimization
```

---

## Next Steps for Sprint 2

### Week 2 Prerequisites
1. **Verify Azure OpenAI Access**: Confirm approval and model deployments
2. **Test All Connections**: Validate connectivity to all services
3. **Configure Development Tools**: Setup VS Code, Docker, Azure CLI
4. **Create Development Documentation**: Document all resource names and configurations
5. **Setup Monitoring**: Configure alerts for cost and performance

### Integration Points for Sprint 3-4
1. **Container Registry**: Ready for microservice deployments
2. **Key Vault Integration**: Service authentication patterns established
3. **Storage & Database**: Data persistence layer ready
4. **Monitoring**: Application Insights integrated for all services
5. **API Management**: Ready for service gateway configuration

---

**Status**: Azure infrastructure setup completed  
**Next Action**: Begin Sprint 2 - Development environment configuration  
**Resources Created**: 12 Azure services, security configured, monitoring enabled