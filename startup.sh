#!/bin/bash

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r backend/requirements.txt

# Change to backend directory
cd backend

# Start the FastAPI application with uvicorn
echo "Starting FastAPI application..."
python -m uvicorn main:app --host 0.0.0.0 --port 8000