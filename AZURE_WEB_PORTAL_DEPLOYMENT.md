# Azure Web Portal Deployment Guide

## 🌐 Deploy trực tiếp qua Azure Portal

### 📦 Bước 1: Chuẩn bị files local

#### 1.1 Build Frontend
```bash
cd frontend
yarn install
yarn build
cd ..
```

#### 1.2 Tạo deployment folder
```
deployment/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── routes/
│   ├── prompts/
│   ├── llm.py
│   └── ... (tất cả files trong backend/)
├── frontend/
│   └── dist/ (copy từ frontend/dist sau yarn build)
├── startup.sh
├── startup.py
├── web.config
└── requirements.txt (copy từ backend/requirements.txt)
```

#### 1.3 Tạo file ZIP
- Select tất cả files trong thư mục deployment/
- Right-click → "Send to" → "Compressed folder"
- Đặt tên: `deployment.zip`

---

## 🚀 Phương pháp 1: Kudu Console (Recommended)

### Bước 1: Vào Kudu
1. **Azure Portal** → **App Services** → **SC-TO-CODE-BACKEND**
2. **Development Tools** → **Advanced Tools** → **Go**
3. Sẽ mở tab mới với Kudu interface

### Bước 2: Upload và Deploy
1. **Debug console** → **CMD**
2. Navigate: `cd site/wwwroot`
3. **Drag & drop** file `deployment.zip` vào file browser
4. Extract: `unzip deployment.zip`
5. Clean up: `del deployment.zip`

### Bước 3: Restart App
- Quay lại Azure Portal → **Overview** → **Restart**

---

## 🔄 Phương pháp 2: ZIP Deploy API

### Bước 1: Lấy publish profile
1. **Azure Portal** → **App Service** → **Get publish profile**
2. Download file `.PublishSettings`

### Bước 2: Upload ZIP via API
```bash
# Sử dụng curl hoặc PowerShell
curl -X POST \
  -H "Content-Type: application/zip" \
  --data-binary @deployment.zip \
  "https://SC-TO-CODE-BACKEND.scm.azurewebsites.net/api/zipdeploy"
```

**PowerShell:**
```powershell
$username = '$SC-TO-CODE-BACKEND'  # Từ publish profile
$password = 'your-password'        # Từ publish profile
$base64AuthInfo = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes(("$username`:$password")))

Invoke-RestMethod -Uri "https://SC-TO-CODE-BACKEND.scm.azurewebsites.net/api/zipdeploy" `
  -Method Post `
  -InFile "deployment.zip" `
  -ContentType "application/zip" `
  -Headers @{Authorization=("Basic {0}" -f $base64AuthInfo)}
```

---

## 🔧 Phương pháp 3: FTP Upload

### Bước 1: Lấy FTP credentials
1. **Azure Portal** → **App Service** → **Deployment Center**
2. **FTPS credentials** → Copy thông tin

### Bước 2: Upload qua FTP client
- Sử dụng FileZilla, WinSCP, hoặc built-in FTP
- Upload tất cả files trong deployment/ lên `/site/wwwroot/`

---

## 🔍 Verification Steps

### 1. Kiểm tra files đã upload
- Kudu → **Debug console** → **CMD** → `dir site/wwwroot`
- Đảm bảo có: `main.py`, `frontend/dist/`, `startup.sh`

### 2. Kiểm tra logs
- **Azure Portal** → **App Service** → **Log stream**
- Hoặc Kudu → **Tools** → **Log Files**

### 3. Test application
- Browse: `https://SC-TO-CODE-BACKEND.azurewebsites.net`
- API test: `https://SC-TO-CODE-BACKEND.azurewebsites.net/api/`

---

## 🐛 Troubleshooting

### "Application Error"
- Kiểm tra startup command đã đúng chưa
- Xem logs trong Log stream
- Đảm bảo requirements.txt có đầy đủ dependencies

### "Frontend không load"
- Kiểm tra `frontend/dist/` đã có files
- Verify static file routing trong main.py

### "API not found"
- Kiểm tra API prefix `/api/*` đã đúng
- Test backend endpoints riêng lẻ

---

## ⚡ Quick Deploy Commands

**All-in-one PowerShell script:**
```powershell
# 1. Build
cd frontend; yarn build; cd ..

# 2. Copy files
mkdir deployment
robocopy backend deployment\backend /E
robocopy frontend\dist deployment\frontend\dist /E
copy startup.sh deployment\
copy startup.py deployment\
copy web.config deployment\

# 3. Create ZIP
Compress-Archive -Path deployment\* -DestinationPath deployment.zip -Force

# 4. Clean up
rmdir deployment /s /q

Write-Host "✅ deployment.zip ready for upload!"
```

Sau đó upload `deployment.zip` qua Kudu console.