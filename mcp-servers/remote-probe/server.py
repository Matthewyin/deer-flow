from fastmcp import FastMCP

mcp = FastMCP(
    "remote-probe",
    instructions="远程探测基线工具集：提供探测数据采集、解析入库、基线管理、对比分析、报告生成和定时调度能力。",
)

from tools.collect_probe_data import register as register_collect
from tools.parse_probe_results import register as register_parse
from tools.init_baseline import register as register_init_baseline
from tools.update_baseline import register as register_update_baseline
from tools.compare_with_baseline import register as register_compare
from tools.generate_probe_report import register as register_report
from tools.scheduler import register as register_scheduler

register_collect(mcp)
register_parse(mcp)
register_init_baseline(mcp)
register_update_baseline(mcp)
register_compare(mcp)
register_report(mcp)
register_scheduler(mcp)

from tools.scheduler import start_scheduler

start_scheduler()

if __name__ == "__main__":
    mcp.run()
