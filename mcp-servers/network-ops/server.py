"""Network Operations MCP Server.

Provides tools for bandwidth policy analysis, line information queries,
and email template generation for network operations.
"""

from fastmcp import FastMCP

mcp = FastMCP(
    "network-ops",
    instructions=(
        "网络运维工具集：提供线路查询、带宽策略评估、统计查询和邮件生成能力。"
        "带宽、P95、扩容、缩容、峰值利用率超过40%的问题，必须优先使用 "
        "ensure_bandwidth_data。查询某日原始记录、返回所有字段、筛选峰值利用率阈值时，使用 "
        "bandwidth_records_query；做 P95 扩缩容评估时，使用 bandwidth_check。line_status_* 工具只用于线路状态日报的"
        "实际值与基线对比，不用于带宽 P95 或扩缩容判断。"
    ),
)


from tools.line_query import register as register_line_query
from tools.bandwidth_assess import register as register_bandwidth_assess
from tools.policy_search import register as register_policy_search
from tools.bandwidth_stats import register as register_bandwidth_stats
from tools.email_generate import register as register_email_generate
from tools.line_status_ingest import register as register_line_status_ingest
from tools.line_status_compare import register as register_line_status_compare
from tools.line_status_history import register as register_line_status_history
from tools.bandwidth_ingest import register as register_bandwidth_ingest
from tools.bandwidth_check import register as register_bandwidth_check
from tools.bandwidth_records_query import register as register_bandwidth_records_query

register_line_query(mcp)
register_bandwidth_assess(mcp)
register_policy_search(mcp)
register_bandwidth_stats(mcp)
register_email_generate(mcp)
register_line_status_ingest(mcp)
register_line_status_compare(mcp)
register_line_status_history(mcp)
register_bandwidth_ingest(mcp)
register_bandwidth_check(mcp)
register_bandwidth_records_query(mcp)


if __name__ == "__main__":
    mcp.run()
