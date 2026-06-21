"""配置对比 MCP 工具。"""

from typing import Any

from core.compare import compare_config_to_template
from core.model import ConfigTemplate, NormalizedConfig


def register(mcp: Any):
    @mcp.tool()
    def config_audit_compare_config(
        config: dict,
        template: dict,
    ) -> dict:
        """将完整配置事实与 approved 模板对比。

        围绕 security zones、inter-zone policy、least privilege、default deny、logging
        返回结构化发现；LLM 只负责解释，不直接下发整改。
        """
        normalized = NormalizedConfig(**config)
        model = ConfigTemplate(**template)
        result = compare_config_to_template(normalized, model)
        return {"ok": True, "compare": result.model_dump()}
