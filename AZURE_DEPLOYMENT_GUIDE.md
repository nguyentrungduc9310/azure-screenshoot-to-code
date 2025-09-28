# Azure App Service Full-Stack Deployment Guide

## 🚀 Hướng dẫn triển khai Screenshot-to-Code Full-Stack lên Azure App Service

**Cấu hình**: Single Azure App Service phục vụ cả Frontend (React) và Backend (FastAPI)

### 📋 Yêu cầu

- Azure subscription
- Azure App Service (Python 3.11+)
- GitHub repository được kết nối với Azure DevOps/GitHub Actions

### 🔧 Cấu hình Environment Variables trong Azure App Service

Vào Azure Portal → App Service → Configuration → Application settings và thêm các biến môi trường sau:

#### Azure OpenAI Configuration (Required)
```
AZURE_OPENAI_API_KEY=your-azure-openai-api-key-here
AZURE_OPENAI_RESOURCE_NAME=SC-TO-CODE-Azure-OpenAI
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-5-mini
AZURE_OPENAI_API_VERSION=2024-12-01-preview
```

#### Optional API Keys
```
OPENAI_API_KEY=your-openai-api-key-here
ANTHROPIC_API_KEY=your-anthropic-key-here
GEMINI_API_KEY=your-gemini-api-key-here
REPLICATE_API_KEY=your-replicate-api-key-here
```

#### Azure OpenAI DALL-E (Optional)
```
AZURE_OPENAI_DALLE3_DEPLOYMENT_NAME=SC-TO-CODE-Azure-OpenAI-dall-e-3
AZURE_OPENAI_DALLE3_API_VERSION=3.0
```

### 🏗️ Cấu hình App Service

#### 1. Startup Command
Trong Azure Portal → App Service → Configuration → General Settings:
```
Startup Command: bash startup.sh
```

#### 2. Python Version
- Đảm bảo Python version được set là 3.11

#### 3. CORS Settings
Trong Azure Portal → App Service → CORS:
- Allowed Origins: `*` (hoặc specific domain của frontend)
- Allow Credentials: Yes

### 📁 Cấu trúc File cho Deployment

Project đã được cấu hình với các file sau:

```
project-root/
├── .github/workflows/main_sc-to-code-backend.yml  # GitHub Actions workflow
├── startup.sh                                     # Bash startup script
├── startup.py                                     # Python startup script
├── web.config                                     # IIS configuration
├── backend/
│   ├── requirements.txt                          # Python dependencies
│   ├── main.py                                   # FastAPI application
│   └── ...
└── frontend/
    └── ...
```

### 🔄 Full-Stack Deployment Process

1. **Push code lên GitHub** - GitHub Actions sẽ tự động trigger
2. **Build process**:
   - **Frontend**: Install Node.js dependencies, build React app với Vite
   - **Backend**: Install Python dependencies từ `backend/requirements.txt`
   - Create artifact với toàn bộ source code + built frontend
3. **Deploy process**:
   - Download artifact
   - Deploy lên Azure App Service
   - FastAPI serve frontend static files từ `/frontend/dist`
   - API endpoints available tại `/api/*`

### 🐛 Troubleshooting

#### Lỗi thường gặp:

1. **"No module named 'main'"**
   - Kiểm tra startup command đã đúng chưa
   - Đảm bảo file `startup.sh` có quyền execute

2. **"ImportError: No module named..."**
   - Kiểm tra `requirements.txt` có đầy đủ dependencies
   - Rebuild và redeploy

3. **"Port binding error"**
   - Azure tự động set PORT environment variable
   - Ứng dụng sẽ tự động sử dụng port này

4. **CORS errors**
   - Cấu hình CORS trong Azure Portal
   - Hoặc update CORS settings trong FastAPI app

### 📊 Monitoring

- **Application Logs**: Azure Portal → App Service → Log stream
- **Deployment Logs**: Azure Portal → Deployment Center
- **GitHub Actions**: GitHub repository → Actions tab

### 🔄 CI/CD Pipeline

GitHub Actions workflow sẽ:
1. Trigger khi push lên branch `main`
2. Build application với Python 3.11
3. Install dependencies
4. Deploy lên Azure App Service `SC-TO-CODE-BACKEND`

### 🌐 Full-Stack Architecture

**Single Azure App Service** phục vụ:
- **Frontend**: React SPA được serve từ root `/`
- **Backend API**: FastAPI endpoints tại `/api/*`
- **Static Assets**: CSS, JS, images từ `/assets/*`

**URL Structure**:
- `https://your-app.azurewebsites.net/` → React App
- `https://your-app.azurewebsites.net/api/generate-code` → WebSocket API
- `https://your-app.azurewebsites.net/api/screenshot` → Screenshot API

---

**Lưu ý**: Đảm bảo tất cả API keys được cấu hình đúng trong Azure App Service Configuration trước khi test ứng dụng.