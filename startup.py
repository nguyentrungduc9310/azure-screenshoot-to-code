#!/usr/bin/env python3
"""
Startup script for Azure App Service deployment
"""

import os
import sys
import subprocess

# Add the backend directory to Python path
backend_path = os.path.join(os.path.dirname(__file__), 'backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Change to backend directory
os.chdir(backend_path)

# Import and run the FastAPI app
if __name__ == "__main__":
    # Get port from environment variable (Azure sets this)
    port = int(os.environ.get("PORT", 8000))

    # Run uvicorn server
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "main:app",
        "--host", "0.0.0.0",
        "--port", str(port)
    ])