# Manual Azure Deployment Script (PowerShell)
# Run this script to manually deploy to Azure App Service

Write-Host "🚀 Starting manual deployment to Azure App Service..." -ForegroundColor Green

# Configuration
$APP_NAME = "SC-TO-CODE-BACKEND"
$RESOURCE_GROUP = "your-resource-group-name"  # Update this
$SUBSCRIPTION = "your-subscription-id"        # Update this

# Step 1: Build Frontend
Write-Host "📦 Building frontend..." -ForegroundColor Yellow
Set-Location frontend
if (!(Test-Path "node_modules")) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Blue
    yarn install
}
Write-Host "Building React app..." -ForegroundColor Blue
yarn build

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Frontend build failed!" -ForegroundColor Red
    exit 1
}

# Step 2: Prepare deployment package
Write-Host "📋 Preparing deployment package..." -ForegroundColor Yellow
Set-Location ..

# Create deployment folder
$deployPath = "deploy-temp"
if (Test-Path $deployPath) {
    Remove-Item $deployPath -Recurse -Force
}
New-Item -ItemType Directory -Path $deployPath

# Copy backend files
Copy-Item "backend\*" "$deployPath\" -Recurse
Copy-Item "startup.sh" "$deployPath\"
Copy-Item "startup.py" "$deployPath\"
Copy-Item "web.config" "$deployPath\"

# Copy built frontend
Copy-Item "frontend\dist" "$deployPath\frontend\dist" -Recurse

Write-Host "✅ Deployment package prepared!" -ForegroundColor Green

# Step 3: Deploy to Azure
Write-Host "🌐 Deploying to Azure App Service..." -ForegroundColor Yellow

# Check if Azure CLI is installed
try {
    az --version | Out-Null
} catch {
    Write-Host "❌ Azure CLI not found! Please install Azure CLI first." -ForegroundColor Red
    Write-Host "Download from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli" -ForegroundColor Blue
    exit 1
}

# Login to Azure (if not already logged in)
Write-Host "🔐 Checking Azure login..." -ForegroundColor Blue
$loginCheck = az account show 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Please login to Azure..." -ForegroundColor Yellow
    az login
}

# Set subscription
Write-Host "📋 Setting subscription..." -ForegroundColor Blue
az account set --subscription $SUBSCRIPTION

# Deploy to App Service
Write-Host "🚀 Deploying to App Service: $APP_NAME..." -ForegroundColor Blue
Set-Location $deployPath

# Create zip file for deployment
$zipFile = "deployment.zip"
Compress-Archive -Path "." -DestinationPath $zipFile -Force

# Deploy using Azure CLI
az webapp deploy --resource-group $RESOURCE_GROUP --name $APP_NAME --src-path $zipFile --type zip

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Deployment successful!" -ForegroundColor Green
    Write-Host "🌐 App URL: https://$APP_NAME.azurewebsites.net" -ForegroundColor Cyan
} else {
    Write-Host "❌ Deployment failed!" -ForegroundColor Red
}

# Cleanup
Set-Location ..
Remove-Item $deployPath -Recurse -Force

Write-Host "🧹 Cleanup completed!" -ForegroundColor Green