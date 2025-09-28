# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Frontend (React/Vite)
```bash
cd frontend
yarn                # Install dependencies
yarn dev            # Start development server (localhost:5173)
yarn build          # Build for production (includes TypeScript compilation)
yarn lint           # Run ESLint with TypeScript
yarn test           # Run Jest tests
```

### Backend (FastAPI/Python)
```bash
cd backend
poetry install      # Install dependencies  
poetry shell        # Activate virtual environment
poetry run uvicorn main:app --reload --port 7001    # Start development server

# Testing and linting
poetry run pytest   # Run tests
poetry run pyright  # TypeScript-style checking for Python

# Mock mode for development (avoids API costs)
MOCK=true poetry run uvicorn main:app --reload --port 7001
```

### Environment Setup
Required environment variables in `backend/.env`:
- `OPENAI_API_KEY` - OpenAI API access
- `ANTHROPIC_API_KEY` - Anthropic Claude API access  
- `GEMINI_API_KEY` - Google Gemini API access
- `REPLICATE_API_KEY` - Image generation (optional)

For Azure OpenAI, also need:
- `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_RESOURCE_NAME`, `AZURE_OPENAI_DEPLOYMENT_NAME`, etc.

## Architecture Overview

### High-Level Structure
This is a full-stack AI-powered screenshot-to-code generator with React frontend and FastAPI backend communicating via WebSocket for real-time code generation.

### Frontend Architecture
- **State Management**: Zustand stores split by concern:
  - `useAppStore()` - Application state (`AppState.INITIAL|CODING|CODE_READY`) and UI mode
  - `useProjectStore()` - Project data (commits, version history, reference images)
  
- **Core Data Flow**: 
  1. User uploads screenshot → `setReferenceImages()` 
  2. WebSocket connection established → `generateCode.ts`
  3. Real-time streaming updates → `appendCommitCode()` 
  4. Version history stored as commit tree → `commits` object

- **Component Organization**:
  - `components/preview/` - Code rendering and preview system
  - `components/evals/` - Model evaluation and comparison tools  
  - `components/settings/` - AI model and framework configuration
  - `store/` - Zustand state management

### Backend Architecture
- **FastAPI Application**: `main.py` loads environment variables first, then sets up CORS and routes
- **Route Structure**:
  - `/generate-code` (WebSocket) - Real-time code generation streaming
  - `/api/screenshot` - Screenshot processing and validation  
  - `/evals` - Model evaluation endpoints
  
- **AI Integration**: `llm.py` handles multiple providers:
  - OpenAI GPT-4 Vision via `stream_openai_response()`
  - Anthropic Claude via `stream_claude_response()` 
  - Google Gemini via `stream_gemini_response()`

- **Prompt System**: `prompts/__init__.py` orchestrates prompt assembly:
  - `create_prompt()` - Main entry point, handles imported vs new code
  - `assemble_prompt()` - Screenshot-based prompts
  - `assemble_imported_code_prompt()` - Code modification prompts
  - Stack-specific system prompts in `SYSTEM_PROMPTS` mapping

### Key Integration Points

**WebSocket Communication**: 
- Frontend `generateCode.ts` manages WebSocket lifecycle
- Backend `routes/generate_code.py` handles streaming responses
- Real-time updates flow through `appendCommitCode()` to UI

**Version Control System**:
- Commits stored as tree structure with parent/child relationships
- Each commit contains variants (usually 2) for A/B comparison  
- `head` pointer tracks current active version

**Multi-AI Provider Support**:
- Provider selection in frontend settings
- Backend routes requests to appropriate `stream_*_response()` function
- Consistent message format across all providers

**Framework Code Generation**:
- `Stack` enum defines supported frameworks (HTML+Tailwind, React+Tailwind, etc.)
- Stack-specific prompts and templates in `prompts/` directory
- Generated code validated and formatted per framework

## Environment Configuration

Backend port: 7001 (update `VITE_WS_BACKEND_URL` in `frontend/.env.local` if changed)
Frontend port: 5173 (standard Vite)

Mock mode available via `MOCK=true` environment variable to avoid API costs during development.