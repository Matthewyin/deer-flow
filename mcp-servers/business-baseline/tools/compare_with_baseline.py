import logging
from typing import Optional

from config import get_config
from db.database import get_connection, init_db
from db.models import get_metrics_by_date, get_all_baselines, get_latest_report_date

logger = logging.getLogger(__name__)

DEVIATION_FIELDS = [
    "request_count",
    "tech_failures",
    "biz_failures",
    "peak_tps",
    "avg_response_ms",
    "max_response_ms",
    "median_response_ms",
    "extra_value",
]

BASELINE_PREFIX = "avg_"


def compare_with_baseline_impl(
    report_date: Optional[str] = None,
    metric_key: Optional[str] = None,
) -> dict:
    cfg = get_config()
    init_db(cfg.sqlite.db_path)
    conn = get_connection(cfg.sqlite.db_path)

    if not report_date:
        report_date = get_latest_report_date(conn)
    if not report_date:
        conn.close()
        return {"error": "No data found in database"}

    metrics = get_metrics_by_date(conn, report_date, metric_key)
    if not metrics:
        conn.close()
        return {"report_date": report_date, "status": "no_data", "comparisons": []}

    baselines_raw = get_all_baselines(conn, metric_key)
    baselines_map = {}
    for b in baselines_raw:
        key = f"{b['metric_key']}|{b['sub_name'] or ''}"
        baselines_map[key] = b
    conn.close()

    comparisons = []
    for m in metrics:
        lookup_key = f"{m['metric_key']}|{m.get('sub_name') or ''}"
        bl = baselines_map.get(lookup_key)

        entry = {
            "metric_key": m["metric_key"],
            "metric_name": m["metric_name"],
            "sub_name": m.get("sub_name"),
            "current": {},
            "baseline": {},
            "deviations": {},
        }

        for field in DEVIATION_FIELDS:
            val = m.get(field)
            if val is not None:
                entry["current"][field] = val

            bl_field = f"{BASELINE_PREFIX}{field}"
            bl_val = bl.get(bl_field) if bl else None
            if bl_val is not None:
                entry["baseline"][field] = bl_val

            if val is not None and bl_val is not None and bl_val != 0:
                dev_pct = round(abs(val - bl_val) / bl_val * 100, 2)
                entry["deviations"][field] = {
                    "current": val,
                    "baseline": bl_val,
                    "deviation_pct": dev_pct,
                }

        comparisons.append(entry)

    return {
        "report_date": report_date,
        "metric_count": len(metrics),
        "comparisons": comparisons,
    }


def register(mcp):
    @mcp.tool()
    def compare_with_baseline(
        report_date: Optional[str] = None, metric_key: Optional[str] = None
    ) -> dict:
        """将指定日期的指标与基线（全历史平均）进行偏差分析。
        计算每个数值字段的偏差百分比。

        Args:
            report_date: 报告日期 (YYYY-MM-DD)，为空则用最新日期
            metric_key: 指标键名，为空则对比全部

        Returns:
            dict: {report_date, metric_count, comparisons: [{current, baseline, deviations}]}
        """
        return compare_with_baseline_impl(report_date, metric_key)
