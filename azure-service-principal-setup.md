# Azure Service Principal Setup

## 🔑 Tạo lại Service Principal cho GitHub Actions

Nếu deployment vẫn fail, có thể cần tạo lại service principal:

### 1. Login Azure CLI
```bash
az login
```

### 2. Lấy thông tin subscription
```bash
az account show
```

### 3. Tạo service principal mới
```bash
# Thay YOUR_SUBSCRIPTION_ID và YOUR_RESOURCE_GROUP
az ad sp create-for-rbac \
  --name "github-actions-sc-to-code" \
  --role "Contributor" \
  --scopes "/subscriptions/YOUR_SUBSCRIPTION_ID/resourceGroups/YOUR_RESOURCE_GROUP" \
  --sdk-auth
```

### 4. Output sẽ như này:
```json
{
  "clientId": "xxxx-xxxx-xxxx-xxxx",
  "clientSecret": "xxxx-xxxx-xxxx-xxxx",
  "subscriptionId": "xxxx-xxxx-xxxx-xxxx",
  "tenantId": "xxxx-xxxx-xxxx-xxxx"
}
```

### 5. Cập nhật GitHub Secrets
Vào GitHub Repository → Settings → Secrets and variables → Actions

Update các secrets:
- `AZUREAPPSERVICE_CLIENTID_*` = clientId
- `AZUREAPPSERVICE_TENANTID_*` = tenantId
- `AZUREAPPSERVICE_SUBSCRIPTIONID_*` = subscriptionId

### 6. Thêm client secret (nếu cần)
Một số workflows cần thêm:
- `AZURE_CREDENTIALS` = toàn bộ JSON output

## 🔧 Alternative: Sử dụng Managed Identity

Hoặc enable Managed Identity trong Azure App Service:

1. Azure Portal → App Service → Identity
2. Enable "System assigned"
3. Cấp quyền deploy cho identity này
4. Update workflow để sử dụng OIDC thay vì service principal

## 🚀 Test deployment
Sau khi update secrets, test lại workflow deployment.