# Manual Deployment Guide

## 🚨 Khi GitHub Actions bị disabled

Nếu GitHub Actions hosted runners bị disabled, bạn có thể deploy thủ công bằng các cách sau:

## 🔧 Option 1: Enable GitHub Actions (Recommended)

1. Vào repository **Settings** → **Actions** → **General**
2. Trong "Actions permissions":
   - ✅ Chọn "Allow all actions and reusable workflows"
3. Trong "Workflow permissions":
   - ✅ Chọn "Read and write permissions"

## 🖥️ Option 2: Manual Deployment Scripts

Tôi đã tạo 2 scripts để deploy thủ công:

### Windows (PowerShell):
```powershell
.\deploy-to-azure.ps1
```

### Linux/Mac (Bash):
```bash
chmod +x deploy-to-azure.sh
./deploy-to-azure.sh
```

## 📋 Yêu cầu cho Manual Deployment

### 1. Cài đặt Azure CLI
```bash
# Windows (PowerShell)
winget install Microsoft.AzureCLI

# Mac
brew install azure-cli

# Linux
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

### 2. Cài đặt Node.js và Yarn
```bash
# Install Node.js 18+
# Install Yarn
npm install -g yarn
```

### 3. Cập nhật thông tin Azure trong scripts

Sửa các giá trị sau trong `deploy-to-azure.ps1` hoặc `deploy-to-azure.sh`:

```bash
APP_NAME="SC-TO-CODE-BACKEND"                    # Tên App Service của bạn
RESOURCE_GROUP="your-resource-group-name"        # Tên Resource Group
SUBSCRIPTION="your-subscription-id"              # Azure Subscription ID
```

**Cách lấy thông tin Azure:**

```bash
# Login Azure CLI
az login

# Lấy subscription ID
az account show --query id -o tsv

# Lấy resource group (nếu không nhớ)
az group list --query "[].name" -o table

# Lấy app service info
az webapp list --query "[].{name:name, resourceGroup:resourceGroup}" -o table
```

## 🚀 Các bước Deploy Manual

### Bước 1: Chuẩn bị
```bash
# Clone/pull latest code
git pull origin main

# Cập nhật thông tin Azure trong deployment script
```

### Bước 2: Chạy deployment script
```bash
# Windows
.\deploy-to-azure.ps1

# Linux/Mac
./deploy-to-azure.sh
```

### Bước 3: Kiểm tra deployment
- Script sẽ tự động:
  1. Build frontend (React/Vite)
  2. Chuẩn bị deployment package
  3. Deploy lên Azure App Service
  4. Cleanup temporary files

## 📊 Deployment Process

Script sẽ thực hiện:

```
1. 📦 Build Frontend
   ├── yarn install (nếu cần)
   └── yarn build

2. 📋 Prepare Package
   ├── Copy backend files
   ├── Copy startup scripts
   ├── Copy built frontend
   └── Create deployment folder

3. 🌐 Deploy to Azure
   ├── Check Azure CLI
   ├── Login (nếu cần)
   ├── Create zip package
   ├── Deploy via az webapp deploy
   └── Cleanup
```

## 🐛 Troubleshooting

### "Azure CLI not found"
- Cài đặt Azure CLI theo hướng dẫn trên
- Restart terminal sau khi cài

### "az command not recognized"
- Thêm Azure CLI vào PATH
- Hoặc sử dụng full path: `C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd`

### "Deployment failed"
- Kiểm tra Resource Group và App Service name
- Đảm bảo có quyền deploy
- Kiểm tra Azure subscription

### "Frontend build failed"
- Chạy `yarn install` trong thư mục frontend
- Kiểm tra Node.js version (cần 18+)

## 🔄 Alternative: Azure DevOps

Nếu không thể dùng GitHub Actions, có thể setup Azure DevOps Pipelines:

1. Tạo Azure DevOps project
2. Connect với GitHub repository
3. Tạo Pipeline với Azure DevOps hosted agents
4. Deploy từ Azure DevOps thay vì GitHub Actions

---

**Lưu ý**: Manual deployment mất thời gian hơn GitHub Actions, nhưng đảm bảo hoạt động khi Actions bị disabled.