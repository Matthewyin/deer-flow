import logging
from typing import Optional

from config import get_config
from db.database import get_connection, init_db
from db.models import get_metrics_for_key, get_report_dates

logger = logging.getLogger(__name__)


def query_history_trend_impl(
    metric_key: str, sub_name: Optional[str] = None, limit: int = 30
) -> dict:
    cfg = get_config()
    init_db(cfg.sqlite.db_path)
    conn = get_connection(cfg.sqlite.db_path)

    rows = get_metrics_for_key(conn, metric_key, limit)
    conn.close()

    if not rows:
        return {"metric_key": metric_key, "data_points": 0, "trend": []}

    trend = []
    for r in rows:
        if sub_name and r.get("sub_name") != sub_name:
            continue
        point = {
            "report_date": r["report_date"],
            "sub_name": r.get("sub_name"),
        }
        for field in [
            "request_count",
            "tech_failures",
            "biz_failures",
            "peak_tps",
            "avg_response_ms",
            "max_response_ms",
            "median_response_ms",
            "extra_value",
        ]:
            if r.get(field) is not None:
                point[field] = r[field]
        trend.append(point)

    return {
        "metric_key": metric_key,
        "sub_name": sub_name,
        "data_points": len(trend),
        "trend": trend,
    }


def register(mcp):
    @mcp.tool()
    def query_history_trend(
        metric_key: str, sub_name: Optional[str] = None, limit: int = 30
    ) -> dict:
        """查询指定指标的历史趋势数据，按日期倒序排列。

        Args:
            metric_key: 指标键名（如 lottery_sales, jingcai_sales_response）
            sub_name: 子分类名称（如 "全部", "传统终端"），为空则返回该 key 下全部
            limit: 返回数据点数量，默认30

        Returns:
            dict: {metric_key, data_points, trend: [{report_date, request_count, ...}]}
        """
        return query_history_trend_impl(metric_key, sub_name, limit)
