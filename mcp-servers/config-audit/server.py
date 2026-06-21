"""设备配置审查 MCP Server。"""

from fastmcp import FastMCP


mcp = FastMCP(
    "config-audit",
    instructions=(
        "设备配置审查工具集：解析防火墙完整配置和配置片段，"
        "反推标准模板，执行标准化对比，并导出 Excel 与 Markdown 报告。"
    ),
)


if __name__ == "__main__":
    mcp.run()
