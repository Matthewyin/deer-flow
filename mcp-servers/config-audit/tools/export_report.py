"""配置审查报告导出 MCP 工具。"""

import os
from typing import Any


from core.export import export_report
from core.model import CompareResult, NormalizedConfig


DEFAULT_OUTPUT_DIR = ".deer-flow/mcp-outputs/config-audit"


def register(mcp: Any):
    @mcp.tool()
    def config_audit_export_report(
        config: dict,
        compare: dict,
        agent_analysis: str = "",
    ) -> dict:
        """导出配置审查事实表和 Markdown 报告。

        报告基于 MCP 结构化事实，LLM 只补充解释，不替代人工复核或自动下发配置。
        """
        normalized = NormalizedConfig(**config)
        compare_result = CompareResult(**compare)
        output_dir = os.getenv("CONFIG_AUDIT_OUTPUT_DIR", DEFAULT_OUTPUT_DIR)
        paths = export_report(normalized, compare_result, output_dir, agent_analysis)
        return {"ok": True, "paths": paths.model_dump()}
