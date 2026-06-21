"""配置片段检查 MCP 工具。"""

from typing import Any

from core.compare import check_snippet_against_template
from core.model import ConfigTemplate, NormalizedConfig


def register(mcp: Any):
    @mcp.tool()
    def config_audit_check_snippet(
        snippet_config: dict,
        template: dict,
        current_config: dict | None = None,
    ) -> dict:
        """检查配置脚本片段是否偏离 approved 模板。

        片段缺少完整上下文，不能自动下发，必须由人工结合当前配置复核。
        """
        snippet = NormalizedConfig(**snippet_config)
        model = ConfigTemplate(**template)
        current = NormalizedConfig(**current_config) if current_config else None
        result = check_snippet_against_template(snippet, model, current)
        return {"ok": True, "compare": result.model_dump()}
