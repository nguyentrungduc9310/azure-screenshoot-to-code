# Load environment variables first
from dotenv import load_dotenv

load_dotenv()


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from routes import screenshot, generate_code, home, evals
import os

app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)

# Configure CORS settings
import os

# Allow all origins in production for Azure App Service
if os.environ.get("AZURE_OPENAI_API_KEY") or os.environ.get("WEBSITE_SITE_NAME"):
    # Production environment (Azure)
    allowed_origins = ["*"]
else:
    # Development environment
    allowed_origins = [
        "http://localhost:5173",  # Local development
        "https://localhost:5173",
        # Add your Azure Static Web App URL here after deployment
        # "https://your-static-web-app-name.azurestaticapps.net"
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Add API routes with /api prefix
app.include_router(generate_code.router, prefix="/api")
app.include_router(screenshot.router, prefix="/api")
app.include_router(home.router, prefix="/api")
app.include_router(evals.router, prefix="/api")

# Serve frontend static files (if available)
# In Azure deployment, frontend/dist is at same level as main.py
frontend_dist_path = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if not os.path.exists(frontend_dist_path):
    # Fallback to local development path
    frontend_dist_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

if os.path.exists(frontend_dist_path):
    # Mount static files
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist_path, "assets")), name="assets")

    # Mount locales for i18n
    locales_path = os.path.join(os.path.dirname(frontend_dist_path), "locales")
    if os.path.exists(locales_path):
        app.mount("/locales", StaticFiles(directory=locales_path), name="locales")

    # Serve index.html for all non-API routes (SPA routing)
    from fastapi.responses import FileResponse

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Don't serve frontend for API routes
        if full_path.startswith("api/"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="API route not found")

        # Serve index.html for SPA routing
        index_path = os.path.join(frontend_dist_path, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)

        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Frontend not found")
