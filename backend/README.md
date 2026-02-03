# DeerFlow Backend

DeerFlow is a LangGraph-based AI agent system that provides a powerful "super agent" with sandbox execution capabilities. The backend enables AI agents to execute code, browse the web, manage files, and perform complex multi-step tasks in isolated environments.

---
## Features

- **LangGraph Agent Runtime**: Built on LangGraph for robust multi-agent workflow orchestration
- **Sandbox Execution**: Safe code execution with local or Docker-based isolation
- **Multi-Model Support**: OpenAI, Anthropic Claude, DeepSeek, Doubao, Kimi, and custom LangChain-compatible models
- **MCP Integration**: Extensible tool ecosystem via Model Context Protocol
- **Skills System**: Specialized domain workflows injected into agent prompts
- **File Upload & Processing**: Multi-format document upload with automatic Markdown conversion
- **Context Summarization**: Automatic conversation summarization for long conversations
- **Plan Mode**: TodoList middleware for complex multi-step task tracking

---
## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Nginx (Port 2026)                       │
│              Unified reverse proxy entry point                   │
└─────────────────┬───────────────────────────────┬───────────────┘
                  │                               │
                  ▼                               ▼
┌─────────────────────────────┐   ┌─────────────────────────────┐
│   LangGraph Server (2024)   │   │    Gateway API (8001)       │
│   Agent runtime & workflows │   │   Models, MCP, Skills, etc. │
└─────────────────────────────┘   └─────────────────────────────┘
```

**Request Routing**:
- `/api/langgraph/*` → LangGraph Server (agent interactions, threads, streaming)
- `/api/*` (other) → Gateway API (models, MCP, skills, artifacts, uploads)
- `/` (non-API) → Frontend (web interface)

---
## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- API keys for your chosen LLM provider

### Installation

```bash
# Clone the repository (if not already)
cd deer-flow

# Copy configuration files
cp config.example.yaml config.yaml
cp extensions_config.example.json extensions_config.json

# Install backend dependencies
cd backend
make install
```

### Configuration

Edit `config.yaml` in the project root to configure your models and tools:

```yaml
models:
  - name: gpt-4
    display_name: GPT-4
    use: langchain_openai:ChatOpenAI
    model: gpt-4
    api_key: $OPENAI_API_KEY  # Set environment variable
    max_tokens: 4096
```

Set your API keys:

```bash
export OPENAI_API_KEY="your-api-key-here"
# Or other provider keys as needed
```

### Running

**Full Application** (from project root):

```bash
make dev  # Starts LangGraph + Gateway + Frontend + Nginx
```

Access at: http://localhost:2026

**Backend Only** (from backend directory):

```bash
# Terminal 1: LangGraph server
make dev

# Terminal 2: Gateway API
make gateway
```

Direct access:
- LangGraph: http://localhost:2024
- Gateway: http://localhost:8001

---
## Project Structure

```
backend/
├── src/
│   ├── agents/              # LangGraph agents and workflows
│   │   ├── lead_agent/      # Main agent implementation
│   │   └── middlewares/     # Agent middlewares
│   ├── gateway/             # FastAPI Gateway API
│   │   └── routers/         # API route handlers
│   ├── sandbox/             # Sandbox execution system
│   ├── tools/               # Agent tools (builtins)
│   ├── mcp/                 # MCP integration
│   ├── models/              # Model factory
│   ├── skills/              # Skills loader
│   ├── config/              # Configuration system
│   ├── community/           # Community tools (web search, etc.)
│   ├── reflection/          # Dynamic module loading
│   └── utils/               # Utility functions
├── docs/                    # Documentation
├── tests/                   # Test suite
├── langgraph.json           # LangGraph server configuration
├── config.yaml              # Application configuration (optional)
├── pyproject.toml           # Python dependencies
├── Makefile                 # Development commands
└── Dockerfile               # Container build
```

---
## API Reference

### LangGraph API (via `/api/langgraph/*`)

- `POST /threads` - Create new conversation thread
- `POST /threads/{thread_id}/runs` - Execute agent with input
- `GET /threads/{thread_id}/runs` - Get run history
- `GET /threads/{thread_id}/state` - Get current conversation state
- WebSocket support for streaming responses

### Gateway API (via `/api/*`)

**Models**:
- `GET /api/models` - List available LLM models
- `GET /api/models/{model_name}` - Get model details

**MCP Configuration**:
- `GET /api/mcp/config` - Get current MCP server configurations
- `PUT /api/mcp/config` - Update MCP configuration

**Skills Management**:
- `GET /api/skills` - List all skills
- `GET /api/skills/{skill_name}` - Get skill details
- `POST /api/skills/{skill_name}/enable` - Enable a skill
- `POST /api/skills/{skill_name}/disable` - Disable a skill
- `POST /api/skills/install` - Install skill from `.skill` file

**File Uploads**:
- `POST /api/threads/{thread_id}/uploads` - Upload files
- `GET /api/threads/{thread_id}/uploads/list` - List uploaded files
- `DELETE /api/threads/{thread_id}/uploads/{filename}` - Delete file

**Artifacts**:
- `GET /api/threads/{thread_id}/artifacts/{path}` - Download generated artifacts

---
## Configuration

### Main Configuration (`config.yaml`)

The application uses a YAML-based configuration file. Place it in the project root directory.

Key sections:
- `models`: LLM configurations with class paths and API keys
- `tool_groups`: Logical groupings for tools
- `tools`: Tool definitions with module paths
- `sandbox`: Execution environment settings
- `skills`: Skills directory configuration
- `title`: Auto-title generation settings
- `summarization`: Context summarization settings

See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for detailed documentation.

### Extensions Configuration (`extensions_config.json`)

MCP servers and skills are configured in `extensions_config.json`:

```json
{
  "mcpServers": {
    "github": {
      "enabled": true,
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {"GITHUB_TOKEN": "$GITHUB_TOKEN"}
    }
  },
  "skills": {
    "pdf-processing": {"enabled": true}
  }
}
```

### Environment Variables

- `DEER_FLOW_CONFIG_PATH` - Override config.yaml location
- `DEER_FLOW_EXTENSIONS_CONFIG_PATH` - Override extensions_config.json location
- Model API keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`, etc.
- Tool API keys: `TAVILY_API_KEY`, `GITHUB_TOKEN`, etc.

---
## Development

### Commands

```bash
make install    # Install dependencies
make dev        # Run LangGraph server (port 2024)
make gateway    # Run Gateway API (port 8001)
make lint       # Run linter (ruff)
make format     # Format code (ruff)
```

### Code Style

- Uses `ruff` for linting and formatting
- Line length: 240 characters
- Python 3.12+ with type hints
- Double quotes, space indentation

### Testing

```bash
uv run pytest
```

---
## Documentation

- [Configuration Guide](docs/CONFIGURATION.md) - Detailed configuration options
- [Setup Guide](docs/SETUP.md) - Quick setup instructions
- [File Upload](docs/FILE_UPLOAD.md) - File upload functionality
- [Path Examples](docs/PATH_EXAMPLES.md) - Path types and usage
- [Summarization](docs/summarization.md) - Context summarization feature
- [Plan Mode](docs/plan_mode_usage.md) - TodoList middleware usage

---
## Technology Stack

### Core Frameworks
- **LangChain** (1.2.3+) - LLM orchestration
- **LangGraph** (1.0.6+) - Multi-agent workflows
- **FastAPI** (0.115.0+) - REST API
- **Uvicorn** (0.34.0+) - ASGI server

### LLM Integrations
- `langchain-openai` - OpenAI models
- `langchain-anthropic` - Claude models
- `langchain-deepseek` - DeepSeek models

### Extensions
- `langchain-mcp-adapters` - MCP protocol support
- `agent-sandbox` - Sandboxed code execution

### Utilities
- `markitdown` - Multi-format to Markdown conversion
- `tavily-python` - Web search
- `firecrawl-py` - Web scraping
- `ddgs` - DuckDuckGo image search

---
## License

See the [LICENSE](../LICENSE) file in the project root.

---
## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.
