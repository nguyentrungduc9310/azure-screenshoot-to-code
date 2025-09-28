# Create Deployment Package for Azure Portal Upload
# Run this script to create deployment.zip for manual upload

Write-Host "🚀 Creating deployment package..." -ForegroundColor Green

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

Set-Location ..

# Step 2: Create deployment folder
Write-Host "📋 Creating deployment folder..." -ForegroundColor Yellow

$deployPath = "deployment"
if (Test-Path $deployPath) {
    Remove-Item $deployPath -Recurse -Force
}
New-Item -ItemType Directory -Path $deployPath | Out-Null

# Copy backend files
Write-Host "📂 Copying backend files..." -ForegroundColor Blue
robocopy backend "$deployPath\backend" /E /NFL /NDL /NJH /NJS

# Copy built frontend
Write-Host "📂 Copying frontend build..." -ForegroundColor Blue
if (Test-Path "frontend\dist") {
    New-Item -ItemType Directory -Path "$deployPath\frontend" -Force | Out-Null
    robocopy "frontend\dist" "$deployPath\frontend\dist" /E /NFL /NDL /NJH /NJS
    Write-Host "✅ Frontend build copied successfully!" -ForegroundColor Green
} else {
    Write-Host "⚠️ Frontend dist folder not found. Please run 'cd frontend && yarn build' first." -ForegroundColor Yellow
}

# Copy deployment files
Write-Host "📂 Copying deployment files..." -ForegroundColor Blue
Copy-Item "startup.sh" "$deployPath\"
Copy-Item "startup.py" "$deployPath\"
Copy-Item "web.config" "$deployPath\"

# Copy requirements.txt to root (Azure expects it there)
Copy-Item "backend\requirements.txt" "$deployPath\"

# Step 3: Create ZIP file
Write-Host "🗜️ Creating ZIP package..." -ForegroundColor Yellow
$zipFile = "deployment.zip"
if (Test-Path $zipFile) {
    Remove-Item $zipFile -Force
}

Compress-Archive -Path "$deployPath\*" -DestinationPath $zipFile -Force

# Cleanup
Remove-Item $deployPath -Recurse -Force

# Show results
Write-Host "✅ Deployment package created successfully!" -ForegroundColor Green
Write-Host "📦 File: deployment.zip" -ForegroundColor Cyan
Write-Host "📊 Size: $([math]::Round((Get-Item $zipFile).Length / 1MB, 2)) MB" -ForegroundColor Cyan

Write-Host "`n🌐 Next steps:" -ForegroundColor Yellow
Write-Host "1. Go to Azure Portal → App Services → SC-TO-CODE-BACKEND"
Write-Host "2. Development Tools → Advanced Tools → Go (Kudu)"
Write-Host "3. Debug console → CMD → cd site/wwwroot"
Write-Host "4. Drag & drop deployment.zip to Kudu"
Write-Host "5. Run: unzip deployment.zip"
Write-Host "6. Restart App Service"

Write-Host "`n✨ Ready to deploy!" -ForegroundColor Green