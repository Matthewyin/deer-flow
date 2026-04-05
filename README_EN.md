# 🦌 DeerFlow

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](./backend/pyproject.toml)
[![Node.js](https://img.shields.io/badge/Node.js-22%2B-339933?logo=node.js&logoColor=white)](./Makefile)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

English | [中文](./README.md)

> 📝 This is a personal fork of [bytedance/deer-flow](https://github.com/bytedance/deer-flow) for learning and development purposes.

DeerFlow is a **Super Agent Harness** that combines sub-agents, memory, and sandbox environments with extensible skills to enable AI agents to complete complex research and automation tasks.

## Features

- 🤖 **Sub-Agent System** - Automatically breaks down complex tasks with parallel execution
- 🧠 **Long-term Memory** - Retains user preferences and work habits across sessions
- 📦 **Isolated Sandbox** - Each task runs in an independent Docker container
- 🔧 **Extensible Skills** - Supports custom skills and MCP Servers
- 🌐 **Multi-Model Support** - Compatible with OpenAI, DeepSeek, Moonshot, and more
- 💻 **Code Execution** - Supports Bash commands and Python code execution

## Quick Start

### Requirements

- Python 3.12+
- Node.js 22+
- pnpm
- Docker (for sandbox mode)

### Installation

1. **Clone the repository**

```bash
git clone https://github.com/Matthewyin/deer-flow.git
cd deer-flow
```

2. **Generate config files**

```bash
make config
```

3. **Configure environment variables**

Copy the example env file and add your API keys:

```bash
cp .env.example .env
```

Edit `.env` with at least one LLM API key:

```bash
# Required: Search API
TAVILY_API_KEY=your-tavily-api-key

# Choose one: LLM API
OPENAI_API_KEY=your-openai-api-key
DEEPSEEK_API_KEY=your-deepseek-api-key
MOONSHOT_API_KEY=your-moonshot-api-key
VOLCENGINE_API_KEY=your-volcengine-api-key
```

4. **Configure models**

Edit `config.yaml` to add your preferred models:

```yaml
models:
  - name: deepseek-chat
    display_name: DeepSeek Chat
    use: langchain_openai:ChatOpenAI
    model: deepseek-chat
    api_key: $DEEPSEEK_API_KEY
    base_url: https://api.deepseek.com/v1
    max_tokens: 4096
    temperature: 0.7
```

### Run the Application

**Docker Mode (Recommended):**

```bash
# Run after first setup or image updates
make docker-init

# Start services
make docker-start
```

**Local Development Mode:**

```bash
# Check dependencies
make check

# Install dependencies
make install

# Start dev server
make dev
```

Access at: http://localhost:2026

## Usage Examples

### Example 1: Deep Research

Type in the chat:

```
Research the latest advances in quantum computing and generate a detailed report
```

DeerFlow will automatically:
1. Search for latest information
2. Analyze key findings
3. Generate a structured report
4. Save to workspace

### Example 2: Data Analysis

Upload a CSV file, then type:

```
Analyze this dataset, create visualizations, and summarize key trends
```

The agent will:
1. Read the uploaded file
2. Execute Python data analysis code
3. Generate charts
4. Return analysis results

### Example 3: Code Generation

```
Write a Python script to scrape web content and save results as JSON
```

The agent will:
1. Write the code
2. Test it in the sandbox
3. Return the executable script file

## Configuration

### Core Config Files

| File | Description |
|------|-------------|
| `.env` | API keys and sensitive settings |
| `config.yaml` | Models, channels, feature toggles |
| `extensions_config.json` | MCP Server extensions |

### Common Settings

**Switch Models:**

Add or modify models in the `models` section of `config.yaml`. Multiple models are supported.

**Enable Memory:**

```yaml
memory:
  enabled: true
  backend: json_file  # or qdrant (requires vector DB)
```

**Configure Sandbox:**

```yaml
sandbox:
  use: deerflow.community.aio_sandbox:DockerSandboxProvider
  image: deerflow-sandbox:latest
```

### Directory Structure

```
deer-flow/
├── backend/          # Python backend service
├── frontend/         # Next.js frontend
├── docker/           # Docker configurations
├── skills/           # Built-in skills
├── logs/             # Runtime logs (generated locally)
└── config.yaml       # Main config (generated locally)
```

## Security Notes

⚠️ **This tool can execute system commands. Use only in trusted local environments.**

- Binds to localhost by default, not exposed externally
- Sandbox files are isolated from host
- Never commit real API keys to git (added to .gitignore)

## License

[MIT License](./LICENSE)

## Credits

Based on [bytedance/deer-flow](https://github.com/bytedance/deer-flow). Thanks to the original authors for their open-source contribution.
