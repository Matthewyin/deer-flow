# AGENTS.md — DeerFlow 开发指南

> 本文件是实际开发经验沉淀，覆盖上游文档未提及或已过时的部分。
> 上游 `backend/CLAUDE.md` 是原始 deerflow 仓库的文件，`docs/` 中的架构文档不一定是最新的，不建议作为主要参考。
> 已验证的命令序列和基础布局见 `.github/copilot-instructions.md`。

## 仓库定位

基于 [bytedance/deer-flow](https://github.com/bytedance/deer-flow) 的个人开发分支，增加了定制子系统和 Docker 生产部署。

**核心架构**：LangGraph Agent + FastAPI Gateway + Next.js Frontend + Nginx 反代，通过 Docker Compose 编排。

## Docker 部署架构（主要运行模式）

所有服务通过 `docker/docker-compose-dev.yaml` 编排，统一入口 `http://localhost:2026`（nginx 反代）。

### 服务清单

| 服务 | 容器名 | 端口 | 职责 |
|------|--------|------|------|
| nginx | deer-flow-nginx | 2026 | 统一反代入口 |
| frontend | deer-flow-frontend | 3000 | Next.js Web UI |
| gateway | deer-flow-gateway | 8001 | FastAPI REST API |
| langgraph | deer-flow-langgraph | 2024 | Agent 运行时 + MCP servers |
| data-manager | deer-flow-data-manager | 8003 | 数据采集管理 UI + 定时任务 |

### 关键命令

```bash
# Docker 开发环境（主要使用方式）
make docker-init       # 初始化（构建镜像、安装依赖）
make docker-start      # 启动所有服务
make docker-stop       # 停止
make docker-logs       # 查看日志

# 本地开发（不使用 Docker 时）
make dev               # 启动 LangGraph + Gateway + Frontend + Nginx
make stop              # 停止

# 后端验证（在 backend/ 目录下）
make lint && make test  # CI 等价检查
```

### Volume 挂载拓扑（改错会丢数据，务必理解）

```
宿主机路径                                    容器内路径                  服务
─────────────────────────────────────────────────────────────────────────
docker/volumes/deer-flow-data/              → /app/.deer-flow         langgraph, data-manager
backend/.deer-flow/                         → /app/backend/.deer-flow data-manager (仅 db/)
backend/                                    → /app/backend/           langgraph, gateway
config.yaml                                 → /app/config.yaml        langgraph, gateway
extensions_config.json                      → /app/extensions_config.json  langgraph, gateway
docs/                                       → /app/docs               langgraph, data-manager
mcp-servers/                                → /app/mcp-servers:ro     langgraph, gateway
skills/                                     → /app/skills             langgraph, gateway
.ssh/                                       → /root/.ssh:ro           langgraph, data-manager
```

**数据文件约定**：
- **数据文件**（probe raw、line-status JSON、bandwidth-lines JSON、vectors、email）→ `docker/volumes/deer-flow-data/`
- **数据库文件**（remote_probe.db、business_baseline.db、ops_knowledge.db）→ `backend/.deer-flow/db/`
- **配置文件**（extensions_config.json、config.yaml）→ 仓库根目录，`.gitignore` 排除

## 定制子系统

### MCP Servers（`mcp-servers/`）

独立的 MCP server 进程，通过 stdio 与 LangGraph Agent 通信。运行在 **langgraph 容器**内，使用 `backend/.venv` 的 Python。

| Server | 入口 | 数据库 | 职责 |
|--------|------|--------|------|
| remote-probe | `server.py` | `remote_probe.db` | 网络探针数据采集、解析、基线管理、报告生成 |
| business-baseline | `server.py` | `business_baseline.db` | 每日运营报告解析、基线对比、趋势分析 |
| ops-knowledge | `server.py` | `ops_knowledge.db` | 运维知识库入库与检索 |
| network-ops | `server.py` | `network_ops.db` | 网络运维工具集 |

**MCP server 的环境变量**来自 `extensions_config.json` 中的 `env` 字段。路径使用**相对路径**（基于 langgraph 进程 CWD 解析），不是绝对路径。

### Data Manager（`docker/data-manager/`）

独立的 FastAPI 应用，有自己的 Dockerfile 和 Python 环境（不共享 backend 的 venv）。

**职责划分（已重构，务必遵守）**：
- **data-manager**：负责数据采集/上传/解析/保存到共享 volume，不直接承担 Agent 侧分析决策
  - Probe：定时 SSH 采集 → 保存 raw JSON 文件到磁盘（`ingested=0`），不做入库
  - Line Status：上传 HTML 日报 → 解析 ECharts 图表 → 保存 `line-status/{YYYY-MM-DD}.json`
  - Bandwidth Lines：同一 HTML 日报中解析 21 列“线路”表格 → 保存 `bandwidth-lines/{YYYY-MM-DD}.json`
  - Bandwidth Policy：上传 `bandwidth.md` → 覆盖策略文档 → 触发 Gateway 重建带宽 RAG
  - EveryBusiness / Emergency：提供每日运营文本、应急预案文件的管理入口
- **MCP server**：负责入库、查询、基线计算、P95 计算和业务判断。Probe 由 `remote-probe` 处理；带宽、线路状态、运维知识库由 `network-ops` / `ops-knowledge` 处理

**定时采集**：APScheduler，北京时间 11:00 和 17:00。配置了 `misfire_grace_time=None` + `coalesce=True` 确保错过的时间点不会丢失。

**data-manager 代码变更后需要**：`docker build` + 重建容器（不共享 backend venv）。

### Skills（`skills/`）

```
skills/
├── public/    # 内置技能（git 跟踪）
└── custom/    # 自定义技能（.gitignore 排除部分）
    ├── bandwidth-management/
    ├── business-baseline/
    ├── emergency-plan/
    └── probe-baseline/
```

### 带宽线路分析链路（当前主流程）

```
用户通过 data-manager 上传 HTML 日报
  → data-manager 解析“线路”21 列表格
  → 保存 docker/volumes/deer-flow-data/bandwidth-lines/{YYYY-MM-DD}.json
  → Agent 调用 network-ops.ensure_bandwidth_data 入库 network_ops.db.bandwidth_lines
  → Agent 调用 bandwidth_check 计算 15 天 P95 并判断 expand / shrink / stable
  → 如需操作，调用 bandwidth_report 生成扩容、应急扩容或缩容邮件
```

## 配置文件约定

| 文件 | 位置 | 是否 git 跟踪 | 说明 |
|------|------|---------------|------|
| `config.yaml` | 仓库根目录 | ❌ | 主配置（模型、工具、沙箱） |
| `extensions_config.json` | 仓库根目录 | ❌ | MCP servers + skills 启用状态 |
| `config.example.yaml` | 仓库根目录 | ✅ | 配置模板 |
| `extensions_config.example.json` | 仓库根目录 | ✅ | MCP 配置模板 |
| `.env` | 仓库根目录 | ❌ | API 密钥等敏感配置 |

**配置值以 `$` 开头**时解析为环境变量（如 `$OPENAI_API_KEY`）。

**`extensions_config.json` 中的路径**：MCP server 的 `env` 字段中的路径是**相对路径**，由 langgraph 进程的 CWD（`/app/backend/`）解析。例如：
- `REMOTE_PROBE_DB_PATH=.deer-flow/db/remote_probe.db` → 实际 `/app/backend/.deer-flow/db/remote_probe.db`
- `PROBE_RAW_DIR` 的值由 `extensions_config.json` 的 `env` 字段覆盖，当前设为 `/app/.deer-flow/probe/raw`（绝对路径，指向 volume 挂载点）

## 探针数据系统（最易出错的子系统）

### 数据流

```
定时任务 (data-manager, 北京时间 11:00/17:00)
  → SSH 到 6 个 ECS 节点下载 probe JSON
  → 保存到 docker/volumes/deer-flow-data/probe/raw/
  → 写入 raw_files 表 (ingested=0)

Agent 调用 MCP ensure_probe_data
  → 检查数据新鲜度（5 小时阈值）
  → 如需采集：HTTP 触发 data-manager 立即采集
  → 解析新 JSON → 写入 probe_metrics 表
  → 标记 raw_files (ingested=1)
  → 更新基线
```

### 6 个探测节点

| 代码 | 城市 | IP |
|------|------|-----|
| hhht | 呼和浩特 | 39.104.209.139 |
| wh | 武汉 | 47.122.115.139 |
| hz | 杭州 | 116.62.131.213 |
| wlcb | 乌兰察布 | 8.130.82.52 |
| qd | 青岛 | 120.27.112.200 |
| cd | 成都 | 47.108.239.135 |

### 数据库

- `remote_probe.db`：`raw_files` 表（含 `ingested`/`ingested_at` 列）、`probe_metrics` 表
- 路径：`backend/.deer-flow/db/remote_probe.db`（宿主机）→ `/app/backend/.deer-flow/db/remote_probe.db`（容器内）

### 常见陷阱

1. **路径不一致**：langgraph 和 data-manager 必须看到同一份 raw JSON 文件。当前通过 `docker/volumes/deer-flow-data` volume 共享。
2. **`ingested` 标记**：`parse_probe_results.py` 在解析后标记。不要在采集时标记。
3. **data-manager 不入库**：如果 data-manager 代码中出现入库逻辑，那是 bug。
4. **Docker Desktop 休眠**：macOS 上 Docker Desktop 可能休眠导致定时任务错过，`misfire_grace_time=None` 会补偿执行。

## 前端注意事项

- `pnpm build` 需要 `BETTER_AUTH_SECRET` 环境变量，否则会报 env validation 错误
- `pnpm check` 不可靠，改用 `pnpm lint && pnpm typecheck`
- 前端环境变量：`DEER_FLOW_INTERNAL_GATEWAY_BASE_URL`、`DEER_FLOW_INTERNAL_LANGGRAPH_BASE_URL`（Docker 内部通信用）

## Nginx 路由

- `/api/langgraph/*` → langgraph:2024
- `/api/*`（其他）→ gateway:8001
- `/`（非 API）→ frontend:3000
- `/data-manager/` → data-manager:8003

## 开发验证流程

```bash
# 1. 后端检查
cd backend && make lint && make test

# 2. 前端检查（如有改动）
cd frontend && pnpm lint && pnpm typecheck

# 3. Docker 环境验证
make docker-stop && make docker-start
# 确认所有容器 healthy

# 4. 提交前检查
git status  # 确认没有 config.yaml / extensions_config.json / .env 泄露
```

## Git 注意事项

- **绝不提交**：`config.yaml`、`extensions_config.json`、`.env`、`backend/.deer-flow/`、`docker/volumes/`、`.ssh/`
- `.github/copilot-instructions.md` 是已验证的命令参考，可以信赖
- CI 跑 `.github/workflows/backend-unit-tests.yml`：`uv sync --group dev` → `make lint` → `make test`
