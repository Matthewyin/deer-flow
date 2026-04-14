from fastmcp import FastMCP

mcp = FastMCP(
    "business-baseline",
    instructions="业务基线监控工具集：每日数据解析入库、基线管理、全量对比分析、趋势查询。",
)

from tools.parse_daily_report import register as register_parse
from tools.query_current_data import register as register_current
from tools.query_baseline import register as register_baseline
from tools.compare_with_baseline import register as register_compare
from tools.query_history_trend import register as register_trend
from tools.get_interpretation import register as register_interpretation

register_parse(mcp)
register_current(mcp)
register_baseline(mcp)
register_compare(mcp)
register_trend(mcp)
register_interpretation(mcp)

if __name__ == "__main__":
    mcp.run()
