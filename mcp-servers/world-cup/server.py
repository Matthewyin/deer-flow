from fastmcp import FastMCP

mcp = FastMCP(
    "world-cup",
    instructions=(
        "世界杯保障数据分析工具集：只负责查询、汇总和生成报告。"
        "Excel 上传、解析和入库由 data-manager 负责，MCP 工具必须读取同一个 world_cup.db。"
    ),
)

from tools.world_cup_metric_catalog import register as register_metric_catalog
from tools.world_cup_records_query import register as register_records_query
from tools.world_cup_report import register as register_report
from tools.world_cup_status import register as register_status
from tools.world_cup_summary import register as register_summary

register_status(mcp)
register_records_query(mcp)
register_summary(mcp)
register_report(mcp)
register_metric_catalog(mcp)


if __name__ == "__main__":
    mcp.run()
