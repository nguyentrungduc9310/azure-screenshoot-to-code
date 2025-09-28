#!/bin/bash

# Screenshot-to-Code Local Development Setup Script
# Version: 1.0
# Usage: ./scripts/setup-local.sh

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local missing_tools=()
    
    if ! command_exists node; then
        missing_tools+=("node")
    else
        NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
        if [ "$NODE_VERSION" -lt 18 ]; then
            log_warning "Node.js version $NODE_VERSION detected. Version 18+ recommended."
        else
            log_success "Node.js $(node --version) found"
        fi
    fi
    
    if ! command_exists python3; then
        missing_tools+=("python3")
    else
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
        log_success "Python $(python3 --version | cut -d' ' -f2) found"
    fi
    
    if ! command_exists git; then
        missing_tools+=("git")
    else
        log_success "Git $(git --version | cut -d' ' -f3) found"
    fi
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        log_info "Please install the missing tools and run this script again."
        log_info "Installation commands:"
        echo "  macOS: brew install ${missing_tools[*]}"
        echo "  Ubuntu: sudo apt install ${missing_tools[*]}"
        echo "  Windows: choco install ${missing_tools[*]}"
        exit 1
    fi
}

# Setup backend
setup_backend() {
    log_info "Setting up backend environment..."
    
    cd backend || {
        log_error "Backend directory not found. Are you in the project root?"
        exit 1
    }
    
    # Create virtual environment
    if [ ! -d "venv" ]; then
        log_info "Creating Python virtual environment..."
        python3 -m venv venv
        log_success "Virtual environment created"
    else
        log_success "Virtual environment already exists"
    fi
    
    # Activate virtual environment
    log_info "Activating virtual environment..."
    source venv/bin/activate
    
    # Install Poetry if not available
    if ! command_exists poetry; then
        log_info "Installing Poetry..."
        pip install poetry
        log_success "Poetry installed"
    else
        log_success "Poetry already installed"
    fi
    
    # Install dependencies
    log_info "Installing backend dependencies..."
    poetry install
    log_success "Backend dependencies installed"
    
    # Setup environment file
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            log_info "Creating .env file from template..."
            cp .env.example .env
            log_success ".env file created"
            log_warning "Please edit backend/.env with your API keys or use MOCK=true for testing"
        else
            log_info "Creating default .env file..."
            cat > .env << 'EOF'
# Screenshot-to-Code Backend Configuration

# Development Mode - Set to true to avoid API costs
MOCK=true

# Database
DATABASE_URL=sqlite:///./dev.db

# AI Provider API Keys (Optional if MOCK=true)
# OPENAI_API_KEY=your_openai_api_key_here
# ANTHROPIC_API_KEY=your_anthropic_api_key_here
# GEMINI_API_KEY=your_google_gemini_api_key_here

# CORS Settings
CORS_ORIGINS=["http://localhost:5173", "http://127.0.0.1:5173"]

# Upload Settings
MAX_FILE_SIZE=10485760
ALLOWED_EXTENSIONS=["png", "jpg", "jpeg", "webp"]

# Logging
LOG_LEVEL=DEBUG
EOF
            log_success "Default .env file created with MOCK=true"
        fi
    else
        log_success ".env file already exists"
    fi
    
    # Create logs directory
    mkdir -p logs
    
    cd ..
}

# Setup frontend
setup_frontend() {
    log_info "Setting up frontend environment..."
    
    cd frontend || {
        log_error "Frontend directory not found. Are you in the project root?"
        exit 1
    }
    
    # Install dependencies
    log_info "Installing frontend dependencies..."
    if command_exists yarn; then
        yarn install
        log_success "Frontend dependencies installed with Yarn"
    else
        npm install
        log_success "Frontend dependencies installed with npm"
    fi
    
    # Setup environment file
    if [ ! -f ".env.local" ]; then
        if [ -f ".env.example" ]; then
            log_info "Creating .env.local file from template..."
            cp .env.example .env.local
        else
            log_info "Creating default .env.local file..."
            cat > .env.local << 'EOF'
# Screenshot-to-Code Frontend Configuration

# Backend URLs
VITE_WS_BACKEND_URL=ws://localhost:7001
VITE_API_BASE_URL=http://localhost:7001

# App Settings
VITE_APP_TITLE=Screenshot-to-Code
VITE_MAX_FILE_SIZE=10485760
VITE_SUPPORTED_FORMATS=png,jpg,jpeg,webp

# Development Settings
VITE_DEV_MODE=true
VITE_DEBUG=true
EOF
        fi
        log_success ".env.local file created"
    else
        log_success ".env.local file already exists"
    fi
    
    cd ..
}

# Create utility scripts
create_scripts() {
    log_info "Creating utility scripts..."
    
    # Create scripts directory if it doesn't exist
    mkdir -p scripts
    
    # Create health check script
    cat > scripts/health-check.sh << 'EOF'
#!/bin/bash
echo "🏥 Health Check - Screenshot-to-Code"
echo "===================================="

# Check backend
echo -n "Backend (http://localhost:7001): "
if curl -s http://localhost:7001/health > /dev/null 2>&1; then
    echo "✅ Healthy"
else
    echo "❌ Not responding"
fi

# Check frontend
echo -n "Frontend (http://localhost:5173): "
if curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo "✅ Healthy"
else
    echo "❌ Not responding"
fi

# Check API docs
echo -n "API Docs (http://localhost:7001/docs): "
if curl -s http://localhost:7001/docs > /dev/null 2>&1; then
    echo "✅ Available"
else
    echo "❌ Not available"
fi
EOF

    # Create reset development environment script
    cat > scripts/reset-dev.sh << 'EOF'
#!/bin/bash
echo "🔄 Resetting development environment..."

# Stop any running processes
pkill -f "uvicorn main:app"
pkill -f "npm run dev"
pkill -f "yarn dev"

# Backend reset
cd backend
if [ -d "venv" ]; then
    rm -rf venv
    echo "✅ Removed backend virtual environment"
fi
if [ -f "dev.db" ]; then
    rm dev.db
    echo "✅ Removed development database"
fi
cd ..

# Frontend reset
cd frontend
if [ -d "node_modules" ]; then
    rm -rf node_modules
    echo "✅ Removed frontend node_modules"
fi
if [ -f "package-lock.json" ]; then
    rm package-lock.json
    echo "✅ Removed package-lock.json"
fi
cd ..

echo "🎉 Development environment reset complete!"
echo "Run './scripts/setup-local.sh' to setup again."
EOF

    # Create start all services script
    cat > scripts/start-dev.sh << 'EOF'
#!/bin/bash
echo "🚀 Starting Screenshot-to-Code development servers..."

# Check if services are already running
if curl -s http://localhost:7001/health > /dev/null 2>&1; then
    echo "⚠️  Backend already running on port 7001"
    exit 1
fi

if curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo "⚠️  Frontend already running on port 5173"
    exit 1
fi

# Start backend in background
echo "📦 Starting backend server..."
cd backend
source venv/bin/activate
poetry run uvicorn main:app --reload --port 7001 &
BACKEND_PID=$!
cd ..

# Wait for backend to start
sleep 3

# Start frontend in background
echo "🎨 Starting frontend server..."
cd frontend
if command -v yarn >/dev/null 2>&1; then
    yarn dev &
else
    npm run dev &
fi
FRONTEND_PID=$!
cd ..

# Save PIDs for cleanup
echo $BACKEND_PID > .backend.pid
echo $FRONTEND_PID > .frontend.pid

echo ""
echo "🎉 Development servers started!"
echo "📦 Backend: http://localhost:7001"
echo "🎨 Frontend: http://localhost:5173"
echo "📚 API Docs: http://localhost:7001/docs"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for interrupt
trap 'kill $BACKEND_PID $FRONTEND_PID; rm -f .backend.pid .frontend.pid; echo "Servers stopped"; exit' INT
wait
EOF

    # Create stop all services script
    cat > scripts/stop-dev.sh << 'EOF'
#!/bin/bash
echo "🛑 Stopping development servers..."

# Kill by saved PIDs
if [ -f ".backend.pid" ]; then
    kill $(cat .backend.pid) 2>/dev/null
    rm .backend.pid
    echo "✅ Backend stopped"
fi

if [ -f ".frontend.pid" ]; then
    kill $(cat .frontend.pid) 2>/dev/null
    rm .frontend.pid
    echo "✅ Frontend stopped"
fi

# Kill by process name as backup
pkill -f "uvicorn main:app" 2>/dev/null
pkill -f "npm run dev" 2>/dev/null
pkill -f "yarn dev" 2>/dev/null

echo "🎉 All development servers stopped"
EOF

    # Make scripts executable
    chmod +x scripts/*.sh
    
    log_success "Utility scripts created in scripts/ directory"
}

# Update package.json with dev scripts
update_package_json() {
    if [ -f "package.json" ]; then
        log_info "Updating package.json with development scripts..."
        
        # Create a temporary file with updated package.json
        python3 -c "
import json
import sys

try:
    with open('package.json', 'r') as f:
        data = json.load(f)
except FileNotFoundError:
    data = {}

if 'scripts' not in data:
    data['scripts'] = {}

data['scripts'].update({
    'dev:all': './scripts/start-dev.sh',
    'dev:backend': 'cd backend && source venv/bin/activate && poetry run uvicorn main:app --reload --port 7001',
    'dev:frontend': 'cd frontend && npm run dev',
    'install:all': 'cd backend && poetry install && cd ../frontend && npm install',
    'health': './scripts/health-check.sh',
    'reset': './scripts/reset-dev.sh',
    'stop': './scripts/stop-dev.sh'
})

if 'devDependencies' not in data:
    data['devDependencies'] = {}

with open('package.json', 'w') as f:
    json.dump(data, f, indent=2)

print('Package.json updated successfully')
" && log_success "Package.json updated with development scripts"
    else
        log_info "Creating package.json with development scripts..."
        cat > package.json << 'EOF'
{
  "name": "screenshot-to-code",
  "version": "1.0.0",
  "description": "Convert screenshots to functional code",
  "scripts": {
    "dev:all": "./scripts/start-dev.sh",
    "dev:backend": "cd backend && source venv/bin/activate && poetry run uvicorn main:app --reload --port 7001",
    "dev:frontend": "cd frontend && npm run dev",
    "install:all": "cd backend && poetry install && cd ../frontend && npm install",
    "health": "./scripts/health-check.sh",
    "reset": "./scripts/reset-dev.sh",
    "stop": "./scripts/stop-dev.sh"
  }
}
EOF
        log_success "Package.json created with development scripts"
    fi
}

# Test setup
test_setup() {
    log_info "Testing setup..."
    
    # Test backend virtual environment
    if [ -f "backend/venv/bin/activate" ]; then
        log_success "Backend virtual environment created"
    else
        log_error "Backend virtual environment not found"
        return 1
    fi
    
    # Test frontend dependencies
    if [ -d "frontend/node_modules" ]; then
        log_success "Frontend dependencies installed"
    else
        log_error "Frontend dependencies not installed"
        return 1
    fi
    
    # Test configuration files
    if [ -f "backend/.env" ] && [ -f "frontend/.env.local" ]; then
        log_success "Configuration files created"
    else
        log_error "Configuration files missing"
        return 1
    fi
    
    log_success "Setup test completed successfully"
}

# Main execution
main() {
    echo ""
    echo "🚀 Screenshot-to-Code Local Development Setup"
    echo "============================================="
    echo ""
    
    # Check if we're in the project root
    if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
        log_error "This script must be run from the project root directory"
        log_info "Current directory: $(pwd)"
        log_info "Expected structure:"
        echo "  - backend/"
        echo "  - frontend/"
        echo "  - scripts/"
        exit 1
    fi
    
    check_prerequisites
    setup_backend
    setup_frontend
    create_scripts
    update_package_json
    test_setup
    
    echo ""
    echo "🎉 Setup completed successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Edit backend/.env with your API keys (or keep MOCK=true for testing)"
    echo "2. Start development servers:"
    echo "   npm run dev:all"
    echo "   OR"
    echo "   ./scripts/start-dev.sh"
    echo ""
    echo "Available commands:"
    echo "  npm run dev:all      - Start both servers"
    echo "  npm run health       - Check server health"
    echo "  npm run stop         - Stop all servers"
    echo "  npm run reset        - Reset development environment"
    echo ""
    echo "URLs:"
    echo "  Frontend:  http://localhost:5173"
    echo "  Backend:   http://localhost:7001"
    echo "  API Docs:  http://localhost:7001/docs"
    echo ""
    echo "For troubleshooting, see LOCAL_SETUP_GUIDE.md"
    echo ""
}

# Run main function
main "$@"