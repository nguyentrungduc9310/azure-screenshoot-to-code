# Upload deployment package to Azure using ZIP Deploy
# Run this after create-deployment-package.ps1

param(
    [string]$AppName = "SC-TO-CODE-BACKEND"
)

Write-Host "🚀 Uploading to Azure App Service: $AppName" -ForegroundColor Green

# Check if deployment.zip exists
if (!(Test-Path "deployment.zip")) {
    Write-Host "❌ deployment.zip not found! Run create-deployment-package.ps1 first." -ForegroundColor Red
    exit 1
}

# Get publish profile credentials
Write-Host "📋 You need to get publish profile credentials:" -ForegroundColor Yellow
Write-Host "1. Go to Azure Portal → App Service → Get publish profile" -ForegroundColor Blue
Write-Host "2. Download the .PublishSettings file" -ForegroundColor Blue
Write-Host "3. Open it and find the userPWD value" -ForegroundColor Blue

$username = Read-Host "Enter username (usually starts with $)"
$password = Read-Host "Enter password (from publish profile)" -AsSecureString

# Convert secure string to plain text for API call
$plainPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto([System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($password))

# Create base64 auth string
$base64AuthInfo = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("$username`:$plainPassword"))

# Upload via ZIP Deploy API
Write-Host "📤 Uploading deployment package..." -ForegroundColor Yellow

try {
    $uri = "https://$AppName.scm.azurewebsites.net/api/zipdeploy"
    $headers = @{
        Authorization = "Basic $base64AuthInfo"
    }

    Write-Host "Uploading to: $uri" -ForegroundColor Blue

    Invoke-RestMethod -Uri $uri -Method Post -InFile "deployment.zip" -ContentType "application/zip" -Headers $headers

    Write-Host "✅ Upload successful!" -ForegroundColor Green
    Write-Host "🌐 App URL: https://$AppName.azurewebsites.net" -ForegroundColor Cyan
    Write-Host "⏱️ Deployment may take 1-2 minutes to complete" -ForegroundColor Yellow

} catch {
    Write-Host "❌ Upload failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "💡 Try using Azure Portal ZIP Deploy instead" -ForegroundColor Yellow
}

# Cleanup password from memory
$plainPassword = $null