# Cập nhật CORS sau khi deploy

Sau khi deploy Static Web App thành công, bạn sẽ nhận được URL dạng: 
`https://your-app-name.azurestaticapps.net`

## Bước 1: Cập nhật CORS trong backend/main.py

Thay thế dòng comment trong `allowed_origins`:

```python
allowed_origins = [
    "http://localhost:5173",  # Local development
    "https://localhost:5173",
    "https://your-actual-static-web-app-url.azurestaticapps.net"  # Thay thế URL thật
]
```

## Bước 2: Commit và push code

```bash
git add .
git commit -m "Update CORS for production deployment"
git push origin master
```

Backend sẽ tự động redeploy với CORS mới.

## Bước 3: Test kết nối

1. Truy cập Static Web App URL
2. Kiểm tra WebSocket connection trong Developer Tools
3. Test upload screenshot và generate code