# Screenshot-to-Code Local Development Setup Guide

**Version**: 1.0  
**Last Updated**: January 2025  
**Prepared for**: Development Team  

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Backend Setup](#backend-setup)
4. [Frontend Setup](#frontend-setup)
5. [Running the Application](#running-the-application)
6. [Testing & Verification](#testing--verification)
7. [Development Commands](#development-commands)
8. [Troubleshooting](#troubleshooting)
9. [Optional: Advanced Setup](#optional-advanced-setup)

---

## Prerequisites

### Required Software

```bash
# Check if you have the required tools installed
node --version    # Required: Node.js 18+ 
python --version  # Required: Python 3.11+
npm --version     # Package manager for Node.js
git --version     # Version control
```

### Installation Commands

**macOS (using Homebrew):**
```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install required tools
brew install node python@3.11 git
brew install poetry  # Python package manager
```

**Ubuntu/Debian:**
```bash
# Update package list
sudo apt update

# Install Node.js 18+
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install Python 3.11+
sudo apt install python3.11 python3.11-venv python3-pip git

# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -
```

**Windows:**
```powershell
# Install using Chocolatey (run as Administrator)
choco install nodejs python git

# Install Poetry
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
```

### API Keys (Optional for Mock Mode)

You'll need API keys from these providers (can skip if using mock mode):
- **OpenAI**: https://platform.openai.com/api-keys
- **Anthropic**: https://console.anthropic.com/
- **Google Gemini**: https://ai.google.dev/
- **Replicate** (optional): https://replicate.com/account/api-tokens

---

## Quick Start

### 1. Clone Repository

```bash
# Clone the repository
git clone https://github.com/your-repo/screenshot-to-code.git
cd screenshot-to-code

# Check project structure
ls -la
```

### 2. One-Command Setup (Recommended)

```bash
# Run the automated setup script
chmod +x scripts/setup-local.sh
./scripts/setup-local.sh
```

**If the script doesn't exist, create it:**
```bash
#!/bin/bash
# scripts/setup-local.sh

echo "🚀 Setting up Screenshot-to-Code local development environment..."

# Backend setup
echo "📦 Setting up backend..."
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install poetry
poetry install
cp .env.example .env
echo "✅ Backend setup complete"

# Frontend setup
echo "🎨 Setting up frontend..."
cd ../frontend
npm install  # or yarn install
cp .env.example .env.local
echo "✅ Frontend setup complete"

echo "🎉 Setup complete! Run 'npm run dev:all' to start both servers"
```

### 3. Start Development Servers

```bash
# Start both backend and frontend
npm run dev:all

# Or start them separately (see detailed instructions below)
```

---

## Backend Setup

### 1. Navigate to Backend Directory

```bash
cd backend
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate

# Verify activation (should show venv path)
which python
```

### 3. Install Dependencies

```bash
# Install Poetry (if not installed globally)
pip install poetry

# Install project dependencies
poetry install

# Alternative: using pip directly
pip install -r requirements.txt
```

### 4. Environment Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit environment file
nano .env  # or code .env or vim .env
```

**Backend .env Configuration:**
```bash
# =================================================================
# Screenshot-to-Code Backend Configuration
# =================================================================

# -----------------------------------------------------------------
# Development Mode
# -----------------------------------------------------------------
# Enable mock mode to test without API costs
MOCK=true

# Development database (SQLite for local testing)
DATABASE_URL=sqlite:///./dev.db

# -----------------------------------------------------------------
# AI Provider API Keys (Optional if MOCK=true)
# -----------------------------------------------------------------
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
# OPENAI_ORG_ID=your_org_id  # Optional

# Anthropic Claude Configuration  
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Google Gemini Configuration
GEMINI_API_KEY=your_google_gemini_api_key_here

# Replicate Configuration (Optional)
REPLICATE_API_KEY=your_replicate_api_key_here

# -----------------------------------------------------------------
# Azure OpenAI (Optional Alternative)
# -----------------------------------------------------------------
# AZURE_OPENAI_API_KEY=your_azure_openai_key
# AZURE_OPENAI_RESOURCE_NAME=your_resource_name
# AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment_name
# AZURE_OPENAI_API_VERSION=2023-12-01-preview

# -----------------------------------------------------------------
# Application Settings
# -----------------------------------------------------------------
# CORS settings for local development
CORS_ORIGINS=["http://localhost:5173", "http://127.0.0.1:5173"]

# Upload settings
MAX_FILE_SIZE=10485760  # 10MB in bytes
ALLOWED_EXTENSIONS=["png", "jpg", "jpeg", "webp"]

# Rate limiting (requests per minute)
RATE_LIMIT_PER_MINUTE=60

# -----------------------------------------------------------------
# Logging Configuration
# -----------------------------------------------------------------
LOG_LEVEL=DEBUG
LOG_FILE=logs/app.log

# -----------------------------------------------------------------
# Security Settings (for production, use secure values)
# -----------------------------------------------------------------
SECRET_KEY=your-secret-key-for-jwt-signing
JWT_EXPIRY_HOURS=24
```

### 5. Database Initialization (Optional)

```bash
# If using a real database, initialize it
poetry run alembic upgrade head

# For SQLite (automatic), no action needed
```

---

## Frontend Setup

### 1. Navigate to Frontend Directory

```bash
cd frontend
```

### 2. Install Dependencies

```bash
# Using npm
npm install

# Or using yarn (if preferred)
yarn install
```

### 3. Environment Configuration

```bash
# Copy environment template
cp .env.example .env.local

# Edit environment file
nano .env.local  # or code .env.local
```

**Frontend .env.local Configuration:**
```bash
# =================================================================
# Screenshot-to-Code Frontend Configuration  
# =================================================================

# -----------------------------------------------------------------
# Backend API Configuration
# -----------------------------------------------------------------
# WebSocket URL for real-time code generation
VITE_WS_BACKEND_URL=ws://localhost:7001

# REST API base URL
VITE_API_BASE_URL=http://localhost:7001

# -----------------------------------------------------------------
# Application Settings
# -----------------------------------------------------------------
# App title and branding
VITE_APP_TITLE=Screenshot-to-Code
VITE_APP_DESCRIPTION=Convert screenshots to functional code

# Maximum file upload size (should match backend)
VITE_MAX_FILE_SIZE=10485760

# Supported image formats
VITE_SUPPORTED_FORMATS=png,jpg,jpeg,webp

# -----------------------------------------------------------------
# Development Settings
# -----------------------------------------------------------------
# Enable development features
VITE_DEV_MODE=true

# Show debug information
VITE_DEBUG=true

# Mock API responses (for testing UI without backend)
VITE_MOCK_API=false

# -----------------------------------------------------------------
# Analytics (Optional)
# -----------------------------------------------------------------
# VITE_GA_TRACKING_ID=your_google_analytics_id
# VITE_POSTHOG_KEY=your_posthog_key

# -----------------------------------------------------------------
# Feature Flags
# -----------------------------------------------------------------
# Enable experimental features
VITE_ENABLE_EXPERIMENTAL_FEATURES=true

# Enable AI model selection
VITE_ENABLE_MODEL_SELECTION=true

# Enable code export options
VITE_ENABLE_CODE_EXPORT=true
```

---

## Running the Application

### Method 1: Start Both Services Together

```bash
# From project root, add this script to package.json
npm run dev:all
```

**Add to package.json:**
```json
{
  "scripts": {
    "dev:all": "concurrently \"npm run dev:backend\" \"npm run dev:frontend\"",
    "dev:backend": "cd backend && poetry run uvicorn main:app --reload --port 7001",
    "dev:frontend": "cd frontend && npm run dev",
    "install:all": "cd backend && poetry install && cd ../frontend && npm install"
  },
  "devDependencies": {
    "concurrently": "^7.6.0"
  }
}
```

### Method 2: Start Services Separately

**Terminal 1 - Backend:**
```bash
cd backend

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Start backend server
poetry run uvicorn main:app --reload --port 7001

# Alternative using python directly
python -m uvicorn main:app --reload --port 7001
```

**Terminal 2 - Frontend:**
```bash
cd frontend

# Start frontend development server
npm run dev

# Or with yarn
yarn dev
```

### Expected Output

**Backend (Terminal 1):**
```
INFO:     Will watch for changes in these directories: ['/path/to/backend']
INFO:     Uvicorn running on http://127.0.0.1:7001 (Press CTRL+C to quit)
INFO:     Started reloader process [12345] using StatReload
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**Frontend (Terminal 2):**
```
  VITE v4.5.0  ready in 1234 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
  ➜  press h to show help
```

---

## Testing & Verification

### 1. Health Check Endpoints

```bash
# Test backend health
curl http://localhost:7001/health
# Expected: {"status": "healthy", "timestamp": "2025-01-25T10:30:00Z"}

# Test frontend accessibility
curl http://localhost:5173
# Expected: HTML response with React app
```

### 2. API Documentation

```bash
# Open interactive API documentation
open http://localhost:7001/docs

# Or access via browser
# http://localhost:7001/docs - Swagger UI
# http://localhost:7001/redoc - ReDoc UI
```

### 3. Full Application Test

1. **Open browser at `http://localhost:5173`**
2. **Upload a screenshot image (PNG, JPG, WebP)**
3. **Select target framework (React, Vue, Angular, HTML)**
4. **Click "Generate Code" button**
5. **Verify code generation works (real-time streaming)**
6. **Test code preview and download functionality**

### 4. Mock Mode Verification

If using `MOCK=true` in backend `.env`:

```bash
# Check mock responses
curl -X POST http://localhost:7001/api/screenshot \
  -F "file=@test-image.png" \
  -F "framework=react"

# Should return mock code instead of calling AI APIs
```

### 5. WebSocket Connection Test

```javascript
// Open browser console on http://localhost:5173
// Run this JavaScript to test WebSocket:

const ws = new WebSocket('ws://localhost:7001/generate-code');
ws.onopen = () => console.log('WebSocket connected');
ws.onmessage = (event) => console.log('Received:', event.data);
ws.onerror = (error) => console.error('WebSocket error:', error);
ws.onclose = () => console.log('WebSocket closed');

// Send test message
ws.send(JSON.stringify({
  type: 'generate',
  data: {
    imageUrl: 'test-image.png',
    framework: 'react'
  }
}));
```

---

## Development Commands

### Backend Commands

```bash
cd backend

# Development server
poetry run uvicorn main:app --reload --port 7001

# Run tests
poetry run pytest

# Run tests with coverage
poetry run pytest --cov=. --cov-report=html

# Type checking
poetry run pyright

# Code formatting
poetry run black .
poetry run isort .

# Linting
poetry run flake8

# Database migrations (if using Alembic)
poetry run alembic revision --autogenerate -m "Description"
poetry run alembic upgrade head

# Install new dependency
poetry add package-name
poetry add --group dev package-name  # Dev dependency
```

### Frontend Commands

```bash
cd frontend

# Development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Run tests
npm run test

# Run tests in watch mode
npm test -- --watch

# Linting
npm run lint

# Fix linting issues
npm run lint -- --fix

# Type checking
npm run type-check

# Install new dependency
npm install package-name
npm install --save-dev package-name  # Dev dependency
```

### Utility Scripts

```bash
# Check all services health
./scripts/health-check.sh

# Reset development environment  
./scripts/reset-dev.sh

# Generate test data
./scripts/generate-test-data.sh

# Backup development database
./scripts/backup-dev-db.sh
```

---

## Troubleshooting

### Common Issues and Solutions

#### 1. Backend Won't Start

**Error: `ModuleNotFoundError: No module named 'fastapi'`**
```bash
# Solution: Install dependencies
cd backend
source venv/bin/activate
poetry install
```

**Error: `Port 7001 already in use`**
```bash
# Solution: Kill process using port
lsof -ti:7001 | xargs kill -9

# Or use different port
poetry run uvicorn main:app --reload --port 7002
```

**Error: `CORS policy error`**
```bash
# Solution: Update CORS_ORIGINS in .env
CORS_ORIGINS=["http://localhost:5173", "http://127.0.0.1:5173"]
```

#### 2. Frontend Won't Start

**Error: `Module not found`**
```bash
# Solution: Clear and reinstall dependencies
cd frontend
rm -rf node_modules package-lock.json
npm install
```

**Error: `Port 5173 already in use`**
```bash
# Solution: Kill process or use different port
lsof -ti:5173 | xargs kill -9
# Or
npm run dev -- --port 5174
```

#### 3. API Connection Issues

**Error: `Failed to fetch` in browser console**
```bash
# Check backend is running
curl http://localhost:7001/health

# Check CORS configuration in backend/.env
CORS_ORIGINS=["http://localhost:5173"]

# Check frontend API URL in .env.local
VITE_API_BASE_URL=http://localhost:7001
```

#### 4. File Upload Issues

**Error: `File too large`**
```bash
# Increase file size limits in backend/.env
MAX_FILE_SIZE=20971520  # 20MB

# Check frontend limit matches
VITE_MAX_FILE_SIZE=20971520
```

**Error: `Unsupported file type`**
```bash
# Check allowed extensions in backend/.env
ALLOWED_EXTENSIONS=["png", "jpg", "jpeg", "webp", "gif"]
```

#### 5. AI Provider Issues

**Error: `Invalid API key`**
```bash
# Verify API keys in backend/.env
# Or use mock mode for testing
MOCK=true
```

**Error: `Rate limit exceeded`**
```bash
# Use mock mode or wait for rate limit reset
MOCK=true

# Or implement retry logic
```

#### 6. Database Issues

**Error: `Database connection failed`**
```bash
# For SQLite (default), check permissions
chmod 664 backend/dev.db

# For PostgreSQL, check connection
psql -h localhost -p 5432 -U postgres -d screenshot_to_code
```

### Debug Mode

Enable detailed logging for troubleshooting:

**Backend debugging:**
```bash
# In backend/.env
LOG_LEVEL=DEBUG

# Check logs
tail -f logs/app.log
```

**Frontend debugging:**
```bash
# In frontend/.env.local
VITE_DEBUG=true

# Open browser console to see debug logs
```

### Performance Issues

**Slow code generation:**
```bash
# Check if using mock mode
MOCK=true

# Monitor backend logs for bottlenecks
tail -f logs/app.log | grep -E "(ERROR|WARN|performance)"

# Check system resources
top -p $(pgrep -f uvicorn)
```

### Getting Help

If you're still having issues:

1. **Check the logs** in both backend and frontend terminals
2. **Search existing issues** in the project repository
3. **Create detailed bug report** with:
   - Operating system and version
   - Node.js and Python versions
   - Complete error messages
   - Steps to reproduce
   - Logs from both backend and frontend

---

## Optional: Advanced Setup

### 1. Docker Development Environment

```bash
# Build and run with Docker Compose
docker-compose -f docker-compose.dev.yml up --build

# Or individual services
docker build -t screenshot-backend ./backend
docker build -t screenshot-frontend ./frontend
```

**docker-compose.dev.yml:**
```yaml
version: '3.8'
services:
  backend:
    build: ./backend
    ports:
      - "7001:7001"
    environment:
      - MOCK=true
    volumes:
      - ./backend:/app
    command: uvicorn main:app --reload --host 0.0.0.0 --port 7001

  frontend:
    build: ./frontend
    ports:
      - "5173:5173"
    volumes:
      - ./frontend:/app
    command: npm run dev -- --host 0.0.0.0

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: screenshot_to_code
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### 2. VS Code Development Setup

**Install recommended extensions:**
```bash
code --install-extension ms-python.python
code --install-extension ms-python.black-formatter
code --install-extension bradlc.vscode-tailwindcss
code --install-extension esbenp.prettier-vscode
code --install-extension ms-vscode.vscode-typescript-next
```

**.vscode/settings.json:**
```json
{
  "python.defaultInterpreterPath": "./backend/venv/bin/python",
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  },
  "tailwindCSS.includeLanguages": {
    "typescript": "javascript",
    "typescriptreact": "javascript"
  }
}
```

### 3. Testing with Real AI Providers

```bash
# Get API keys from providers
# OpenAI: https://platform.openai.com/api-keys
# Anthropic: https://console.anthropic.com/
# Google: https://ai.google.dev/

# Update backend/.env with real keys
MOCK=false
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AI...

# Test with small requests first
curl -X POST http://localhost:7001/api/screenshot \
  -F "file=@small-test-image.png" \
  -F "framework=html"
```

### 4. Production-like Local Setup

```bash
# Build optimized versions
cd frontend && npm run build
cd ../backend && poetry build

# Run with production settings
cd backend
ENVIRONMENT=production poetry run uvicorn main:app --port 7001

# Serve frontend build
cd frontend
npx serve -s dist -l 5173
```

---

## Summary

You now have a complete local development environment for Screenshot-to-Code! 🎉

**Quick reminder of the startup process:**

1. **Backend**: `cd backend && poetry run uvicorn main:app --reload --port 7001`
2. **Frontend**: `cd frontend && npm run dev`  
3. **Access**: Open `http://localhost:5173` in your browser
4. **Test**: Upload an image and generate code!

**Key URLs:**
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:7001
- **API Docs**: http://localhost:7001/docs
- **Health Check**: http://localhost:7001/health

For any issues, check the troubleshooting section or the logs in your terminal windows.

Happy coding! 🚀

---

**Document Prepared By**: Development Team  
**Last Updated**: January 2025  
**Next Review**: As needed based on system updates