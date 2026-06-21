"""模板审批 MCP 工具。"""

import os
from pathlib import Path
from typing import Any


from core.model import ConfigTemplate
from core.template import save_approved_template


DEFAULT_DATA_DIR = ".deer-flow/config-audit"


def register(mcp: Any):
    @mcp.tool()
    def config_audit_review_template(
        template: dict,
        reviewed_by: str,
    ) -> dict:
        """保存人工复核后的 approved 模板。

        模板只描述审查事实基线，不代表配置脚本可自动下发。
        """
        model = ConfigTemplate(**template)
        base_dir = (
            Path(os.getenv("CONFIG_AUDIT_DATA_DIR", DEFAULT_DATA_DIR))
            / "templates"
            / "approved"
        )
        path = save_approved_template(model, base_dir, reviewed_by)
        return {"ok": True, "path": str(path)}
