# Git Deployment for Azure App Service Linux

## 🔧 Setup Git Deployment (Không cần GitHub Actions)

### Bước 1: Enable Local Git trong Azure Portal
1. **Azure Portal** → **App Services** → **SC-TO-CODE-BACKEND**
2. **Deployment** → **Deployment Center**
3. **Source**: Chọn **"Local Git"**
4. **Save**

### Bước 2: Tạo deployment credentials
1. **Deployment** → **Deployment Center** → **FTPS Credentials**
2. Set **username** và **password**
3. Copy **Git Clone Uri**

### Bước 3: Setup pre-deployment script
Tạo file `.deployment` trong root project:

```ini
[config]
command = deploy.sh
```

Tạo file `deploy.sh`:
```bash
#!/bin/bash

echo "🚀 Starting deployment..."

# Build frontend
echo "📦 Building frontend..."
cd frontend
npm install
npm run build
cd ..

# Copy files to deployment target
echo "📋 Copying files..."
cp -r backend/* $DEPLOYMENT_TARGET/
cp -r frontend/dist $DEPLOYMENT_TARGET/frontend/
cp startup.sh $DEPLOYMENT_TARGET/
cp startup.py $DEPLOYMENT_TARGET/
cp web.config $DEPLOYMENT_TARGET/

echo "✅ Deployment completed!"
```

### Bước 4: Deploy
```bash
# Add Azure remote
git remote add azure <GIT_CLONE_URI>

# Build locally first
./create-deployment-package.ps1

# Commit deployment files
git add .
git commit -m "Deploy to Azure"

# Push to Azure
git push azure main
```

## 🔄 Auto-sync từ GitHub (Alternative)

### Bước 1: Connect GitHub
1. **Deployment Center** → **Source**: **GitHub**
2. Authorize và chọn repository
3. **Branch**: main
4. **Save**

### Bước 2: Tạo build script
Tạo file `build.sh` trong root:
```bash
#!/bin/bash
echo "Building application..."

# Install Node.js if not available
if ! command -v node &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi

# Build frontend
cd frontend
npm install
npm run build
cd ..

# Setup backend
cd backend
pip install -r requirements.txt
cd ..

echo "Build completed!"
```

### Bước 3: Configure startup
**App Service** → **Configuration** → **General Settings**:
- **Startup Command**: `bash startup.sh`