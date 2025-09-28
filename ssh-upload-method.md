# SSH Upload Method for Azure App Service Linux

## 📤 Upload file qua SSH Terminal

### Method 1: Base64 Upload (For small files)

#### Bước 1: Encode file locally
```powershell
# Windows PowerShell
$base64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes("deployment.zip"))
$base64 | Out-File "deployment.txt"
Write-Host "File encoded to deployment.txt"
```

#### Bước 2: Copy content trong SSH
```bash
# Trong Kudu SSH
cd /home/site/wwwroot

# Tạo file và paste base64 content
cat > deployment.txt << 'EOF'
# Paste base64 content từ deployment.txt
EOF

# Decode back to zip
base64 -d deployment.txt > deployment.zip

# Extract
unzip deployment.zip

# Clean up
rm deployment.txt deployment.zip
```

### Method 2: GitHub Release Upload (Recommended)

#### Bước 1: Create GitHub Release
```bash
# Local - create release với deployment.zip
git tag v1.0.0
git push origin v1.0.0

# Hoặc tạo release manually trên GitHub web
# Upload deployment.zip as release asset
```

#### Bước 2: Download trong SSH
```bash
# Trong Kudu SSH
cd /home/site/wwwroot

# Download từ GitHub release
wget https://github.com/YOUR_USERNAME/YOUR_REPO/releases/download/v1.0.0/deployment.zip

# Extract
unzip deployment.zip

# Clean up
rm deployment.zip
```

### Method 3: Direct File Creation (For scripts)

#### Tạo file deployment script trong SSH:
```bash
# Trong Kudu SSH
cd /home/site/wwwroot

# Tạo quick deployment script
cat > quick_deploy.sh << 'EOF'
#!/bin/bash

echo "🚀 Quick deployment starting..."

# Clean existing
rm -rf backend frontend startup.* web.config

# Create basic structure
mkdir -p backend frontend/dist

# Create basic main.py (sẽ update sau)
cat > backend/main.py << 'PYTHON'
from fastapi import FastAPI
app = FastAPI()

@app.get("/")
def root():
    return {"message": "Backend is running!"}

@app.get("/api/test")
def test():
    return {"status": "API working!"}
PYTHON

# Create requirements.txt
cat > backend/requirements.txt << 'REQ'
fastapi
uvicorn[standard]
REQ

# Create startup script
cat > startup.sh << 'START'
#!/bin/bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000
START

chmod +x startup.sh

echo "✅ Basic deployment completed!"
EOF

chmod +x quick_deploy.sh
./quick_deploy.sh
```

## 🔄 Update Strategy

### For incremental updates:
```bash
# Backup current
cp -r /home/site/wwwroot /home/site/backup

# Update specific files
# ... upload new files ...

# Test
# If failed, restore: cp -r /home/site/backup/* /home/site/wwwroot/
```