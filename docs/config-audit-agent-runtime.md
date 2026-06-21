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
    "CONFIG_AUDIT_DATA_DIR": ".deer-flow/config-audit",
    "CONFIG_AUDIT_OUTPUT_DIR": ".deer-flow/mcp-outputs/config-audit"
  }
}
```

## 验证入口

创建运行态 Agent 后，在 DeerFlow 前端选择 `config-audit` assistant，上传或粘贴防火墙配置进行验证。

建议验证顺序：

1. 完整配置梳理：解析 H3C、Huawei 或 Hillstone 样例配置，并导出 Excel 事实表。
2. 模板反推：用认可样本生成 draft 模板，人工复核后保存 approved 模板。
3. 事后标准化检查：用 approved 模板检查完整配置。
4. 事前脚本检查：用 approved 模板检查配置片段；如有当前完整配置，一并提供给 Agent。
