#!/bin/bash

echo "🚀 Starting Screenshot to Code Full-Stack App..."

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Debug: Check structure
echo "📊 Current directory structure:"
ls -la
echo "📊 Frontend directory (if exists):"
ls -la frontend/ || echo "No frontend directory found"

# Start the FastAPI application
echo "🏃 Starting FastAPI application..."
python -m uvicorn main:app --host 0.0.0.0 --port 8000