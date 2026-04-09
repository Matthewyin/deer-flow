"""Network Operations MCP Server.

Provides tools for bandwidth policy analysis, line information queries,
and email template generation for network operations.
"""

from fastmcp import FastMCP

mcp = FastMCP(
    "network-ops",
    instructions="网络运维工具集：提供线路查询、带宽策略评估、统计查询和邮件生成能力。",
)


from tools.line_query import register as register_line_query
from tools.bandwidth_assess import register as register_bandwidth_assess
from tools.policy_search import register as register_policy_search
from tools.bandwidth_stats import register as register_bandwidth_stats
from tools.email_generate import register as register_email_generate

register_line_query(mcp)
register_bandwidth_assess(mcp)
register_policy_search(mcp)
register_bandwidth_stats(mcp)
register_email_generate(mcp)


if __name__ == "__main__":
    mcp.run()
