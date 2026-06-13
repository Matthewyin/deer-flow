from fastmcp import FastMCP
from tools.report_generate import register as register_report_generate

mcp = FastMCP(
    "network-weekly-report",
    instructions=(
        "网络专线带宽周报生成工具集：负责根据已整理的带宽记录 JSON 调用标准报告脚本生成 HTML。"
        "Agent 不应自行编写 Python/HTML 生成逻辑。"
    ),
)

register_report_generate(mcp)


if __name__ == "__main__":
    mcp.run()
