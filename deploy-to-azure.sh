#!/bin/bash
# Manual Azure Deployment Script (Bash)
# Run this script to manually deploy to Azure App Service

echo "🚀 Starting manual deployment to Azure App Service..."

# Configuration - UPDATE THESE VALUES
APP_NAME="SC-TO-CODE-BACKEND"
RESOURCE_GROUP="your-resource-group-name"  # Update this
SUBSCRIPTION="your-subscription-id"        # Update this

# Step 1: Build Frontend
echo "📦 Building frontend..."
cd frontend

if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    yarn install
fi

echo "Building React app..."
yarn build

if [ $? -ne 0 ]; then
    echo "❌ Frontend build failed!"
    exit 1
fi

# Step 2: Prepare deployment package
echo "📋 Preparing deployment package..."
cd ..

# Create deployment folder
DEPLOY_PATH="deploy-temp"
rm -rf $DEPLOY_PATH
mkdir -p $DEPLOY_PATH

# Copy backend files
cp -r backend/* $DEPLOY_PATH/
cp startup.sh $DEPLOY_PATH/
cp startup.py $DEPLOY_PATH/
cp web.config $DEPLOY_PATH/

# Copy built frontend
mkdir -p $DEPLOY_PATH/frontend
cp -r frontend/dist $DEPLOY_PATH/frontend/

echo "✅ Deployment package prepared!"

# Step 3: Deploy to Azure
echo "🌐 Deploying to Azure App Service..."

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI not found! Please install Azure CLI first."
    echo "Install guide: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Login to Azure (if not already logged in)
echo "🔐 Checking Azure login..."
if ! az account show &> /dev/null; then
    echo "Please login to Azure..."
    az login
fi

# Set subscription
echo "📋 Setting subscription..."
az account set --subscription $SUBSCRIPTION

# Deploy to App Service
echo "🚀 Deploying to App Service: $APP_NAME..."
cd $DEPLOY_PATH

# Create zip file for deployment
zip -r deployment.zip . -x "*.git*" "node_modules/*" "__pycache__/*" "*.pyc"

# Deploy using Azure CLI
az webapp deploy --resource-group $RESOURCE_GROUP --name $APP_NAME --src-path deployment.zip --type zip

if [ $? -eq 0 ]; then
    echo "✅ Deployment successful!"
    echo "🌐 App URL: https://$APP_NAME.azurewebsites.net"
else
    echo "❌ Deployment failed!"
fi

# Cleanup
cd ..
rm -rf $DEPLOY_PATH

echo "🧹 Cleanup completed!"