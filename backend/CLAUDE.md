# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DeerFlow is a LangGraph-based AI agent system with a full-stack architecture. The backend provides a "super agent" with sandbox execution capabilities that can execute code, browse the web, and manage files in isolated environments.

**Architecture**:
- **LangGraph Server** (port 2024): Agent runtime and workflow execution
- **Gateway API** (port 8001): REST API for models, MCP, skills, artifacts, and uploads
- **Frontend** (port 3000): Next.js web interface
- **Nginx** (port 2026): Unified reverse proxy entry point

**Project Structure**:
```
deer-flow/
├── Makefile                    # Root commands (check, install, dev, stop)
├── nginx.conf                  # Nginx reverse proxy configuration
├── config.yaml                 # Main application configuration
├── extensions_config.json      # MCP servers and skills configuration
├── backend/                    # Backend application (this directory)
│   ├── Makefile               # Backend-only commands (dev, gateway, lint)
│   ├── src/
│   │   ├── agents/            # LangGraph agents and workflows
│   │   ├── gateway/           # FastAPI Gateway API
│   │   ├── sandbox/           # Sandbox execution system
│   │   ├── tools/             # Agent tools
│   │   ├── mcp/               # MCP integration
│   │   ├── models/            # Model factory
│   │   ├── skills/            # Skills loading and management
│   │   ├── config/            # Configuration system
│   │   ├── community/         # Community tools (web search, etc.)
│   │   ├── reflection/        # Dynamic module loading
│   │   └── utils/             # Utilities
│   └── langgraph.json         # LangGraph server configuration
├── frontend/                   # Next.js frontend application
└── skills/                     # Agent skills directory
    ├── public/                # Public skills (committed)
    └── custom/                # Custom skills (gitignored)
```

## Important Development Guidelines

### Documentation Update Policy
**CRITICAL: Always update README.md and CLAUDE.md after every code change**

When making code changes, you MUST update the relevant documentation:
- Update `README.md` for user-facing changes (features, setup, usage instructions)
- Update `CLAUDE.md` for development changes (architecture, commands, workflows, internal systems)
- Keep documentation synchronized with the codebase at all times
- Ensure accuracy and timeliness of all documentation

## Commands

**Root directory** (for full application):
```bash
# Check system requirements
make check

# Install all dependencies (frontend + backend)
make install

# Start all services (LangGraph + Gateway + Frontend + Nginx)
make dev

# Stop all services
make stop
```

**Backend directory** (for backend development only):
```bash
# Install backend dependencies
make install

# Run LangGraph server only (port 2024)
make dev

# Run Gateway API only (port 8001)
make gateway

# Lint
make lint

# Format code
make format
```

## Architecture

### Configuration System

The app uses a two-tier YAML/JSON-based configuration system.

**Main Configuration** (`config.yaml`):

Setup: Copy `config.example.yaml` to `config.yaml` in the **project root** directory.

```bash
# From project root (deer-flow/)
cp config.example.yaml config.yaml
```

Configuration priority:
1. Explicit `config_path` argument
2. `DEER_FLOW_CONFIG_PATH` environment variable
3. `config.yaml` in current directory (backend/)
4. `config.yaml` in parent directory (project root - **recommended location**)

Config values starting with `$` are resolved as environment variables (e.g., `$OPENAI_API_KEY`).

**Extensions Configuration** (`extensions_config.json`):

MCP servers and skills are configured together in `extensions_config.json` in project root:

```bash
# From project root (deer-flow/)
cp extensions_config.example.json extensions_config.json
```

Configuration priority:
1. Explicit `config_path` argument
2. `DEER_FLOW_EXTENSIONS_CONFIG_PATH` environment variable
3. `extensions_config.json` in current directory (backend/)
4. `extensions_config.json` in parent directory (project root - **recommended location**)
5. For backward compatibility: `mcp_config.json` (will be deprecated)

### Core Components

**Gateway API** (`src/gateway/`)
- FastAPI application that provides REST endpoints for frontend integration
- Endpoints:
  - `/api/models` - List available LLM models from configuration
  - `/api/mcp` - Manage MCP server configurations (GET, POST)
  - `/api/skills` - Manage skill configurations (GET, POST)
  - `/api/threads/{thread_id}/artifacts/*` - Serve agent-generated artifacts
  - `/api/threads/{thread_id}/uploads` - File upload, list, delete
- Works alongside LangGraph server, handling non-agent HTTP operations
- Proxied through nginx under `/api/*` routes (except `/api/langgraph/*`)

**Agent Graph** (`src/agents/`)
- `lead_agent` is the main entry point registered in `langgraph.json`
- Uses `ThreadState` which extends `AgentState` with:
  - `sandbox`: Sandbox environment info
  - `artifacts`: Generated file paths
  - `thread_data`: Workspace/uploads/outputs paths
  - `title`: Auto-generated conversation title
  - `todos`: Task tracking (plan mode)
  - `viewed_images`: Vision model image data
- Agent is created via `make_lead_agent(config)` with model, tools, middleware, and system prompt

**Sandbox System** (`src/sandbox/`)
- Abstract `Sandbox` base class defines interface: `execute_command`, `read_file`, `write_file`, `list_dir`
- `SandboxProvider` manages sandbox lifecycle: `acquire`, `get`, `release`
- `SandboxMiddleware` automatically acquires sandbox on agent start and injects into state
- `LocalSandboxProvider` is a singleton implementation for local execution
- `AioSandboxProvider` provides Docker-based isolation (in `src/community/`)
- Sandbox tools (`bash`, `ls`, `read_file`, `write_file`, `str_replace`) extract sandbox from tool runtime

**Virtual Path System**:
- Paths map between virtual and physical locations
- Virtual: `/mnt/user-data/{workspace,uploads,outputs}` - used by agent
- Physical: `backend/.deer-flow/threads/{thread_id}/user-data/{workspace,uploads,outputs}`
- Skills path: `/mnt/skills` maps to `deer-flow/skills/`

**Model Factory** (`src/models/factory.py`)
- `create_chat_model()` instantiates LLM from config using reflection
- Supports `thinking_enabled` flag with per-model `when_thinking_enabled` overrides
- Supports `supports_vision` flag for image understanding models

**Tool System** (`src/tools/`)
- Tools defined in config with `use` path (e.g., `src.sandbox.tools:bash_tool`)
- `get_available_tools()` resolves tool paths via reflection
- Built-in tools in `src/tools/builtins/`:
  - `present_file_tool` - Display files to users
  - `ask_clarification_tool` - Request clarification
  - `view_image_tool` - Vision model integration (conditional on model capability)
- Community tools in `src/community/`: Jina AI (web fetch), Tavily (web search), Firecrawl (scraping)
- Supports MCP (Model Context Protocol) for pluggable external tools

**MCP System** (`src/mcp/`)
- Integrates with MCP servers to provide pluggable external tools using `langchain-mcp-adapters`
- Uses `MultiServerMCPClient` from langchain-mcp-adapters for multi-server management
- **Automatic initialization**: Tools are loaded on first use with lazy initialization
- Supports both eager loading (FastAPI startup) and lazy loading (LangGraph Studio)
- `initialize_mcp_tools()` can be called in FastAPI lifespan handler for eager loading
- `get_cached_mcp_tools()` automatically initializes tools if not already loaded
- Each server can be enabled/disabled independently via `enabled` flag
- Support types: stdio (command-based), SSE, HTTP
- Built on top of langchain-ai/langchain-mcp-adapters for seamless integration

**Reflection System** (`src/reflection/`)
- `resolve_variable()` imports module and returns variable (e.g., `module:variable`)
- `resolve_class()` imports and validates class against base class

**Skills System** (`src/skills/`)
- Skills provide specialized workflows for specific tasks (e.g., PDF processing, frontend design)
- Located in `deer-flow/skills/{public,custom}` directory structure
- Each skill has a `SKILL.md` file with YAML front matter (name, description, license, allowed-tools)
- Skills are automatically discovered and loaded at runtime
- `load_skills()` scans directories and parses SKILL.md files
- Skills are injected into agent's system prompt with paths (only enabled skills)
- Path mapping system allows seamless access in both local and Docker sandbox
- Each skill can be enabled/disabled independently via `enabled` flag in extensions config

**Middleware System** (`src/agents/middlewares/`)
- Custom middlewares handle cross-cutting concerns
- Middlewares are registered in `src/agents/lead_agent/agent.py` with execution order:
  1. `ThreadDataMiddleware` - Initializes thread context (workspace, uploads, outputs paths)
  2. `UploadsMiddleware` - Processes uploaded files, injects file list into state
  3. `SandboxMiddleware` - Manages sandbox lifecycle, acquires on start
  4. `SummarizationMiddleware` - Reduces context when token limits approached (if enabled)
  5. `TitleMiddleware` - Generates conversation titles
  6. `TodoListMiddleware` - Tracks multi-step tasks (if plan_mode enabled)
  7. `ViewImageMiddleware` - Injects image details for vision models
  8. `MemoryMiddleware` - Automatic context retention and personalization (if enabled)
  9. `ClarificationMiddleware` - Handles clarification requests (must be last)

**Memory System** (`src/agents/memory/`)
- LLM-powered personalization layer that automatically extracts and stores user context across conversations
- Components:
  - `updater.py` - LLM-based memory updates with fact extraction and file I/O
  - `queue.py` - Debounced update queue for batching and performance optimization
  - `prompt.py` - Prompt templates and formatting utilities for memory updates
- `MemoryMiddleware` (`src/agents/middlewares/memory_middleware.py`) - Queues conversations for memory updates
- Gateway API (`src/gateway/routers/memory.py`) - REST endpoints for memory management
- Storage: JSON file at `backend/.deer-flow/memory.json`

**Memory Data Structure**:
- **User Context** (current state):
  - `workContext` - Work-related information (job, projects, technologies)
  - `personalContext` - Preferences, communication style, background
  - `topOfMind` - Current focus areas and immediate priorities
- **History** (temporal context):
  - `recentMonths` - Recent activities and discussions
  - `earlierContext` - Important historical context
  - `longTermBackground` - Persistent background information
- **Facts** (structured knowledge):
  - Discrete facts with categories: `preference`, `knowledge`, `context`, `behavior`, `goal`
  - Each fact includes: `id`, `content`, `category`, `confidence` (0-1), `createdAt`, `source` (thread ID)
  - Confidence threshold (default 0.7) filters low-quality facts
  - Max facts limit (default 100) keeps highest-confidence facts

**Memory Workflow**:
1. **Post-Interaction**: `MemoryMiddleware` filters messages (user inputs + final AI responses only) and queues conversation
2. **Debounced Processing**: Queue waits 30s (configurable), batches multiple updates, resets timer on new updates
3. **LLM-Based Update**: Background thread loads memory, formats conversation, invokes LLM to extract:
   - Updated context summaries (1-3 sentences each)
   - New facts with confidence scores and categories
   - Facts to remove (contradictions)
4. **Storage**: Applies updates atomically to `memory.json` with cache invalidation (mtime-based)
5. **Injection**: Next interaction loads memory, formats top 15 facts + context, injects into `<memory>` tags in system prompt

**Memory API Endpoints** (`/api/memory`):
- `GET /api/memory` - Retrieve current memory data
- `POST /api/memory/reload` - Force reload from file (invalidates cache)
- `GET /api/memory/config` - Get memory configuration
- `GET /api/memory/status` - Get both config and data

### Config Schema

Models, tools, sandbox providers, skills, and middleware settings are configured in `config.yaml`:
- `models[]`: LLM configurations with `use` class path, `supports_thinking`, `supports_vision`
- `tools[]`: Tool configurations with `use` variable path and `group`
- `tool_groups[]`: Logical groupings for tools
- `sandbox.use`: Sandbox provider class path
- `skills.path`: Host path to skills directory (optional, default: `../skills`)
- `skills.container_path`: Container mount path (default: `/mnt/skills`)
- `title`: Automatic thread title generation configuration
- `summarization`: Automatic conversation summarization configuration
- `subagents`: Subagent (task tool) configuration
  - `enabled`: Master switch to enable/disable subagents (boolean, default: true)
- `memory`: Memory system configuration
  - `enabled`: Master switch (boolean)
  - `storage_path`: Path to memory.json file (relative to backend/)
  - `debounce_seconds`: Wait time before processing updates (default: 30)
  - `model_name`: LLM model for memory updates (null = use default model)
  - `max_facts`: Maximum facts to store (default: 100)
  - `fact_confidence_threshold`: Minimum confidence to store fact (default: 0.7)
  - `injection_enabled`: Inject memory into system prompt (boolean)
  - `max_injection_tokens`: Token limit for memory injection (default: 2000)

**Extensions Configuration Schema** (`extensions_config.json`):
- `mcpServers`: Map of MCP server name to configuration
  - `enabled`: Whether the server is enabled (boolean)
  - `type`: Transport type (`stdio`, `sse`, `http`)
  - `command`: Command to execute (for stdio type)
  - `args`: Arguments to pass to the command (array)
  - `env`: Environment variables (object with `$VAR` support)
  - `description`: Human-readable description
- `skills`: Map of skill name to state configuration
  - `enabled`: Whether the skill is enabled (boolean, default: true if not specified)

Both MCP servers and skills can be modified at runtime via API endpoints.

## Development Workflow

### Running the Full Application

From the **project root** directory:
```bash
make dev
```

This starts all services and makes the application available at `http://localhost:2026`.

**Nginx routing**:
- `/api/langgraph/*` → LangGraph Server (2024) - Agent interactions, threads, streaming
- `/api/*` (other) → Gateway API (8001) - Models, MCP, skills, artifacts, uploads
- `/` (non-API) → Frontend (3000) - Web interface

### Running Backend Services Separately

For backend-only development, from the **backend** directory:

```bash
# Terminal 1: LangGraph server
make dev

# Terminal 2: Gateway API
make gateway
```

Direct access (without nginx):
- LangGraph: `http://localhost:2024`
- Gateway: `http://localhost:8001`

### Frontend Configuration

The frontend uses environment variables to connect to backend services:
- `NEXT_PUBLIC_LANGGRAPH_BASE_URL` - Defaults to `/api/langgraph` (through nginx)
- `NEXT_PUBLIC_BACKEND_BASE_URL` - Defaults to empty string (through nginx)

When using `make dev` from root, the frontend automatically connects through nginx.

## Key Features

### File Upload

The backend supports multi-file upload with automatic document conversion:
- Endpoint: `POST /api/threads/{thread_id}/uploads`
- Supports: PDF, PPT, Excel, Word documents
- Auto-converts documents to Markdown using `markitdown`
- Files stored in thread-isolated directories
- Agent automatically receives uploaded file list via `UploadsMiddleware`

See [docs/FILE_UPLOAD.md](docs/FILE_UPLOAD.md) for details.

### Plan Mode

Enable TodoList middleware for complex multi-step tasks:
- Controlled via runtime config: `config.configurable.is_plan_mode = True`
- Provides `write_todos` tool for task tracking
- Agent can break down complex tasks and track progress

See [docs/plan_mode_usage.md](docs/plan_mode_usage.md) for details.

### Context Summarization

Automatic conversation summarization when approaching token limits:
- Configured in `config.yaml` under `summarization` key
- Trigger types: tokens, messages, or fraction of max input
- Keeps recent messages while summarizing older ones

See [docs/summarization.md](docs/summarization.md) for details.

### Vision Support

For models with `supports_vision: true`:
- `ViewImageMiddleware` processes images in conversation
- `view_image_tool` added to agent's toolset
- Images automatically converted and injected into state

### Memory System

Persistent context retention and personalization across conversations:
- **Automatic Extraction**: LLM analyzes conversations to extract user context, facts, and preferences
- **Structured Storage**: Maintains user context, history, and confidence-scored facts in JSON format
- **Smart Filtering**: Only processes meaningful messages (user inputs + final AI responses)
- **Debounced Updates**: Batches updates to minimize LLM calls (configurable wait time)
- **System Prompt Injection**: Automatically injects relevant memory context into agent prompts
- **Cache Optimization**: File modification time-based cache invalidation for external edits
- **Thread Safety**: Locks protect queue and cache for concurrent access
- **REST API**: Full CRUD operations via `/api/memory` endpoints
- **Frontend Integration**: Memory settings page for viewing and managing memory data

**Configuration**: Controlled via `memory` section in `config.yaml`
- Enable/disable memory system
- Configure storage path, debounce timing, fact limits
- Control system prompt injection and token limits
- Set confidence thresholds for fact storage

**Storage Location**: `backend/.deer-flow/memory.json`

See configuration section for detailed settings.

## Code Style

- Uses `ruff` for linting and formatting
- Line length: 240 characters
- Python 3.12+ with type hints
- Double quotes, space indentation

## Documentation

See `docs/` directory for detailed documentation:
- [CONFIGURATION.md](docs/CONFIGURATION.md) - Configuration options
- [SETUP.md](docs/SETUP.md) - Setup guide
- [FILE_UPLOAD.md](docs/FILE_UPLOAD.md) - File upload feature
- [PATH_EXAMPLES.md](docs/PATH_EXAMPLES.md) - Path types and usage
- [summarization.md](docs/summarization.md) - Context summarization
- [plan_mode_usage.md](docs/plan_mode_usage.md) - Plan mode with TodoList
