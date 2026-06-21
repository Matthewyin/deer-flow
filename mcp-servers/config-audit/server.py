"""设备配置审查 MCP Server。"""

from fastmcp import FastMCP

from tools.check_snippet import register as register_check_snippet
from tools.compare_config import register as register_compare_config
from tools.export_report import register as register_export_report
from tools.import_batches import register as register_import_batches
from tools.infer_template import register as register_infer_template
from tools.parse_config import register as register_parse_config
from tools.parse_snippet import register as register_parse_snippet
from tools.review_template import register as register_review_template


mcp = FastMCP(
    "config-audit",
    instructions=(
        "设备配置审查工具集：解析防火墙完整配置和配置片段，"
        "读取 data-manager 导入批次，反推标准模板，执行标准化对比，并导出 Excel 与 Markdown 报告。"
        "MCP 工具只产出 security zones、inter-zone policy、least privilege、default deny、logging "
        "等结构化事实和报告文件，LLM 只负责解释这些事实。配置脚本片段不能自动下发，"
        "所有整改必须经过人工复核。"
    ),
)

register_parse_config(mcp)
register_parse_snippet(mcp)
register_import_batches(mcp)
register_infer_template(mcp)
register_review_template(mcp)
register_compare_config(mcp)
register_check_snippet(mcp)
register_export_report(mcp)


if __name__ == "__main__":
    mcp.run()
