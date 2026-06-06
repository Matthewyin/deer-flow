from fastmcp import FastMCP

from config import get_config
from core.db import query_records


def register(mcp: FastMCP):
    @mcp.tool()
    def world_cup_records_query(
        date: str = "",
        start_date: str = "",
        end_date: str = "",
        sheet_name: str = "",
        granularity: str = "",
        metric_key: str = "",
        metric: str = "",
        hour_range: str = "",
        limit: int = 500,
    ) -> dict:
        """查询世界杯标准化原始记录。

        Args:
            date: 单日日期，格式 YYYY-MM-DD。
            start_date: 开始日期，格式 YYYY-MM-DD。
            end_date: 结束日期，格式 YYYY-MM-DD。
            sheet_name: sheet 中文名或 sheet_slug。
            granularity: hourly、daily 或 weekly。
            metric_key: 标准指标 key。
            metric: metric_key 或中文指标名关键词。
            hour_range: 小时时段，例如 20:00-21:00。
            limit: 返回上限，最大 2000。
        """
        cfg = get_config()
        return query_records(
            cfg.db_path,
            date=date,
            start_date=start_date,
            end_date=end_date,
            sheet_name=sheet_name,
            granularity=granularity,
            metric_key=metric_key,
            metric=metric,
            hour_range=hour_range,
            limit=limit,
        )
