# Config Audit Agent 运行态创建说明

`config-audit` 的可版本化能力包括 MCP server、custom skill 和扩展配置示例。

DeerFlow 自定义 Agent 的运行态文件位于 `backend/.deer-flow/agents/`，该目录不提交到 Git。实施验证时创建：

```text
backend/.deer-flow/agents/config-audit/
  config.yaml
  SOUL.md
```

## config.yaml 示例

```yaml
name: config-audit
description: 防火墙配置审查 Agent
skills:
  - config-audit
mcp_servers:
  - config-audit
```

## SOUL.md 示例

```markdown
# 防火墙配置审查 Agent

你负责防火墙完整配置梳理、标准模板反推、事后标准化检查和配置脚本片段事前检查。

你必须先调用 config-audit MCP 工具获取结构化事实，再进行 LLM 分析。

你不能自动下发配置命令。所有整改建议必须以审查建议形式输出。
```

## 本地启用 MCP 示例

`extensions_config.example.json` 已包含默认关闭的 `config-audit` MCP server。实际验证时在本地 `extensions_config.json` 中启用该 server，并确保容器内路径与 Docker 挂载一致：

```json
{
  "enabled": true,
  "type": "stdio",
  "command": "/opt/venv/bin/python",
  "args": ["/app/mcp-servers/config-audit/server.py"],
  "env": {
    "CONFIG_AUDIT_DATA_DIR": "/app/backend/.deer-flow/config-audit",
    "CONFIG_AUDIT_OUTPUT_DIR": "/app/backend/.deer-flow/mcp-outputs/config-audit",
    "CONFIG_AUDIT_IMPORT_DIR": "/app/.deer-flow/device-configs"
  }
}
```

如果不在 Docker 容器内运行，而是在 `backend/` 目录直接启动服务，可以使用相对路径：

```json
{
  "CONFIG_AUDIT_DATA_DIR": ".deer-flow/config-audit",
  "CONFIG_AUDIT_OUTPUT_DIR": ".deer-flow/mcp-outputs/config-audit",
  "CONFIG_AUDIT_IMPORT_DIR": ".deer-flow/device-configs"
}
```

## 配置资产导入链路

防火墙配置文件先通过 data-manager 导入，不建议让 Agent 直接处理浏览器上传文件。

导入入口：

```text
http://localhost:2026/data-manager/
```

进入“设备配置”选项卡后，选择厂商、设备类型，并批量上传 `.txt` 配置文件。data-manager 会把文件保存到共享目录：

```text
/app/.deer-flow/device-configs/{device_type}/{vendor}/{import_id}/
```

该目录来自 data-manager 的 `DEVICE_CONFIG_IMPORT_DIR`，默认值为 `/app/.deer-flow/device-configs`。langgraph 容器内的 config-audit MCP 通过 `CONFIG_AUDIT_IMPORT_DIR` 读取同一目录。

当前导入页支持的元数据：

- 厂商：华为、华三、山石、F5、深信服
- 设备类型：防火墙、路由器、交换机、负载均衡
- 批次名称、标准区域、设备角色、站点、本地网

当前 config-audit MCP 只解析 H3C、Huawei、Hillstone 防火墙。F5、深信服、路由器、交换机、负载均衡会被保存为配置资产，但解析工具会返回“暂不支持解析”。

Agent 侧建议流程：

1. 调用 `config_audit_list_import_batches` 查看 data-manager 已导入批次。
2. 调用 `config_audit_parse_import_batch` 解析目标批次。
3. 用解析结果调用 `config_audit_infer_template` 生成 draft 模板。
4. 人工复核后，再调用模板审核、配置对比或脚本片段检查工具。

data-manager 代码变更后需要重建容器：

```bash
DEER_FLOW_ROOT=/Users/matthewyin/Coding/docker/deer-flow \
docker compose -f docker/docker-compose-dev.yaml up -d --build data-manager
```

## 启用检查清单

代码合并后，界面不会自动出现 `config-audit` Agent。必须完成以下运行态操作：

1. 创建 `backend/.deer-flow/agents/config-audit/config.yaml` 和 `SOUL.md`。
2. 在实际使用的 `extensions_config.json` 中启用 `config-audit` MCP server。
3. 重启 DeerFlow 运行服务。
4. 验证 API 已能看到 Agent 和 MCP server。

Docker 开发环境可使用：

```bash
DEER_FLOW_ROOT=/Users/matthewyin/Coding/docker/deer-flow \
docker compose -f docker/docker-compose-dev.yaml restart langgraph gateway frontend nginx
```

验证命令：

```bash
curl -s http://localhost:2026/api/agents \
  | python3 -c 'import sys,json; print("\n".join(a["name"] for a in json.load(sys.stdin)["agents"]))'

curl -s http://localhost:2026/api/mcp/config \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["mcp_servers"].get("config-audit"))'
```

预期：

- Agent 列表包含 `config-audit`。
- MCP 配置中 `config-audit.enabled` 为 `true`。

## 502 排查

如果重启后浏览器出现 `502 Bad Gateway`，先判断是 API 还是前端页面：

```bash
curl -I http://localhost:2026/
curl -s http://localhost:2026/api/agents
docker logs deer-flow-nginx --tail 80
```

若 API 正常但页面 502，通常是 nginx 仍缓存了旧的 frontend upstream。单独重启 nginx：

```bash
DEER_FLOW_ROOT=/Users/matthewyin/Coding/docker/deer-flow \
docker compose -f docker/docker-compose-dev.yaml restart nginx
```

再次验证：

```bash
curl -I http://localhost:2026/
curl -I http://localhost:2026/workspace/agents
```

## 验证入口

创建运行态 Agent 后，在 DeerFlow 前端选择 `config-audit` assistant，上传或粘贴防火墙配置进行验证。

建议验证顺序：

1. 完整配置梳理：解析 H3C、Huawei 或 Hillstone 样例配置，并导出 Excel 事实表。
2. 模板反推：用认可样本生成 draft 模板，人工复核后保存 approved 模板。
3. 事后标准化检查：用 approved 模板检查完整配置。
4. 事前脚本检查：用 approved 模板检查配置片段；如有当前完整配置，一并提供给 Agent。
