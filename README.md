# 🦌 DeerFlow

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](./backend/pyproject.toml)
[![Node.js](https://img.shields.io/badge/Node.js-22%2B-339933?logo=node.js&logoColor=white)](./Makefile)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

[English](./README_EN.md) | 中文

> 📝 本项目是基于 [bytedance/deer-flow](https://github.com/bytedance/deer-flow) 的个人学习/开发分支。

DeerFlow 是一个 **Super Agent Harness**，通过组合子代理（sub-agents）、记忆（memory）和沙箱（sandbox），配合可扩展的技能（skills），让 AI Agent 能够完成复杂的研究和自动化任务。

## 功能特性

- 🤖 **子代理系统** - 复杂任务自动拆解，多代理并行执行
- 🧠 **长期记忆** - 跨会话保留用户偏好和工作习惯
- 📦 **隔离沙箱** - 每个任务在独立 Docker 容器中运行
- 🔧 **可扩展技能** - 支持自定义技能和 MCP Server
- 🌐 **多模型支持** - 兼容 OpenAI、DeepSeek、Moonshot 等 API
- 💻 **代码执行** - 支持 Bash 命令和 Python 代码运行

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 22+
- pnpm
- Docker（用于沙箱模式）

### 安装步骤

1. **克隆仓库**

```bash
git clone https://github.com/Matthewyin/deer-flow.git
cd deer-flow
```

2. **生成配置文件**

```bash
make config
```

3. **配置环境变量**

复制示例环境文件并填写你的 API 密钥：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入至少一个 LLM API 密钥：

```bash
# 必需：搜索 API
TAVILY_API_KEY=your-tavily-api-key

# 选择其一：LLM API
OPENAI_API_KEY=your-openai-api-key
DEEPSEEK_API_KEY=your-deepseek-api-key
MOONSHOT_API_KEY=your-moonshot-api-key
VOLCENGINE_API_KEY=your-volcengine-api-key
```

4. **配置模型**

编辑 `config.yaml`，添加你要使用的模型：

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

### 运行应用

**Docker 模式（推荐）：**

```bash
# 首次运行或更新镜像后执行
make docker-init

# 启动服务
make docker-start
```

**本地开发模式：**

```bash
# 检查依赖
make check

# 安装依赖
make install

# 启动开发服务器
make dev
```

访问地址：http://localhost:2026

## 使用示例

### 示例 1：深度研究

在对话框中输入：

```
研究一下量子计算的最新进展，生成一份详细报告
```

DeerFlow 会自动：
1. 搜索最新资料
2. 分析关键信息
3. 生成结构化报告
4. 保存到工作目录

### 示例 2：数据分析

上传 CSV 文件，然后输入：

```
分析这个数据集，生成可视化图表并总结关键趋势
```

Agent 会在沙箱中：
1. 读取上传的文件
2. 执行 Python 数据分析代码
3. 生成图表
4. 返回分析结果

### 示例 3：代码生成

```
帮我写一个 Python 脚本，实现网页内容抓取，并将结果保存为 JSON
```

Agent 将：
1. 编写代码
2. 在沙箱中测试
3. 返回可运行的脚本文件

## 配置说明

### 核心配置文件

| 文件 | 说明 |
|------|------|
| `.env` | API 密钥和敏感配置 |
| `config.yaml` | 模型、渠道、功能开关配置 |
| `extensions_config.json` | MCP Server 扩展配置 |

### 常用配置项

**切换模型：**

在 `config.yaml` 的 `models` 部分添加或修改模型配置，支持多个模型并存。

**启用记忆功能：**

```yaml
memory:
  enabled: true
  backend: json_file  # 或 qdrant（需要向量数据库）
```

**配置沙箱模式：**

```yaml
sandbox:
  use: deerflow.community.aio_sandbox:DockerSandboxProvider
  image: deerflow-sandbox:latest
```

### 目录结构

```
deer-flow/
├── backend/          # Python 后端服务
├── frontend/         # Next.js 前端
├── docker/           # Docker 配置
├── skills/           # 内置技能
├── logs/             # 运行日志（本地生成）
└── config.yaml       # 主配置文件（本地生成）
```

## 安全提示

⚠️ **本工具具有执行系统命令的能力，建议仅在本地可信环境使用**

- 默认绑定 localhost，不对外暴露
- 沙箱内的文件与主机隔离
- 不要在 `.env` 中提交真实密钥（已添加到 .gitignore）

## 许可证

[MIT License](./LICENSE)

## 致谢

基于 [bytedance/deer-flow](https://github.com/bytedance/deer-flow) 构建，感谢原作者的开源贡献。
