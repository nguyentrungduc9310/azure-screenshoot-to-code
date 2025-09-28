# Screenshot-to-Code Quick Start Guide

Get up and running in under 5 minutes! 🚀

## 🎯 Prerequisites

- **Node.js 18+**: `node --version`
- **Python 3.11+**: `python --version`  
- **Git**: `git --version`

**Don't have them?** 
- macOS: `brew install node python@3.11 git`
- Ubuntu: `sudo apt install nodejs python3.11 python3-pip git`
- Windows: `choco install nodejs python git`

## ⚡ One-Command Setup

```bash
# Clone and setup everything automatically
git clone https://github.com/your-repo/screenshot-to-code.git
cd screenshot-to-code
./scripts/setup-local.sh
```

## 🚀 Start Development Servers

```bash
# Start both backend and frontend
npm run dev:all

# Or manually:
# Terminal 1: npm run dev:backend  
# Terminal 2: npm run dev:frontend
```

## 🌐 Access the Application  

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:7001  
- **API Docs**: http://localhost:7001/docs

## 🧪 Test It Works

1. Open http://localhost:5173 in browser
2. Upload a screenshot (PNG/JPG)
3. Select framework (React/Vue/Angular/HTML)
4. Click "Generate Code" 
5. Watch real-time code generation! ✨

## 🔧 Configuration

### Mock Mode (No API Keys Needed)
```bash
# backend/.env
MOCK=true  # Already set by setup script
```

### Real AI Providers
```bash  
# backend/.env - Add your API keys
MOCK=false
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AI...
```

## 🛠️ Useful Commands

```bash
npm run health     # Check if servers are running
npm run stop       # Stop all servers
npm run reset      # Reset development environment  
```

## 🚨 Troubleshooting

**Port already in use?**
```bash
# Kill processes and restart
npm run stop
npm run dev:all
```

**Dependencies issues?**
```bash  
npm run reset      # Reset everything
./scripts/setup-local.sh  # Setup again
```

**Still having issues?** Check the detailed [LOCAL_SETUP_GUIDE.md](./LOCAL_SETUP_GUIDE.md)

## 🎉 You're Ready!

That's it! You now have a fully functional Screenshot-to-Code development environment.

Start uploading screenshots and generating amazing code! 🎨➡️💻