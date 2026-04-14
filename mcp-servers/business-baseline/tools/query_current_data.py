import logging
from typing import Optional

from config import get_config
from db.database import get_connection, init_db
from db.models import get_metrics_by_date, get_latest_report_date

logger = logging.getLogger(__name__)


def query_current_data_impl(
    report_date: Optional[str] = None, metric_key: Optional[str] = None
) -> dict:
    cfg = get_config()
    init_db(cfg.sqlite.db_path)
    conn = get_connection(cfg.sqlite.db_path)

    if not report_date:
        report_date = get_latest_report_date(conn)

    if not report_date:
        conn.close()
        return {"error": "No data found in database", "report_date": None}

    metrics = get_metrics_by_date(conn, report_date, metric_key)
    conn.close()

    return {
        "report_date": report_date,
        "metric_count": len(metrics),
        "metrics": metrics,
    }


def register(mcp):
    @mcp.tool()
    def query_current_data(
        report_date: Optional[str] = None, metric_key: Optional[str] = None
    ) -> dict:
        """查询指定日期（默认最新日期）的业务指标数据。

        Args:
            report_date: 报告日期 (YYYY-MM-DD)，为空则查询最新日期
            metric_key: 指标键名，为空则返回全部指标

        Returns:
            dict: {report_date, metric_count, metrics: [{metric_key, metric_name, sub_name, ...}]}
        """
        return query_current_data_impl(report_date, metric_key)
