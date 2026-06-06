from fastmcp import FastMCP

from config import get_config
from core.db import summary


def register(mcp: FastMCP):
    @mcp.tool()
    def world_cup_summary(
        date: str = "",
        start_date: str = "",
        end_date: str = "",
        sheet_name: str = "",
        granularity: str = "",
        metric_key: str = "",
        metric: str = "",
        top_n: int = 10,
    ) -> dict:
        """生成世界杯数据峰值、波动排行和空值项汇总，不做故障定性。"""
        cfg = get_config()
        return summary(
            cfg.db_path,
            date=date,
            start_date=start_date,
            end_date=end_date,
            sheet_name=sheet_name,
            granularity=granularity,
            metric_key=metric_key,
            metric=metric,
            top_n=top_n,
        )
