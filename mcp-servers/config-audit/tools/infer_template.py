"""模板反推 MCP 工具。"""

from fastmcp import FastMCP

from core.model import NormalizedConfig
from core.template import infer_template


def register(mcp: FastMCP):
    @mcp.tool()
    def config_audit_infer_template(
        configs: list[dict],
        standard_zone: str,
        role: str,
    ) -> dict:
        """从已认可配置事实反推草稿模板。

        MCP 只基于结构化事实归纳 security zones、对象、服务和 inter-zone policy 基线，
        LLM 只负责解释，不生成可自动下发脚本。
        """
        normalized = [NormalizedConfig(**config) for config in configs]
        template = infer_template(normalized, standard_zone, role)
        return {"ok": True, "template": template.model_dump()}
