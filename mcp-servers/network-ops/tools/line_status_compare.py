import logging
import sqlite3
from typing import Optional

from fastmcp import FastMCP

from db.line_status_client import LineStatusClient

logger = logging.getLogger(__name__)

_client: Optional[LineStatusClient] = None


def _get_client() -> LineStatusClient:
    global _client
    if _client is None:
        from config import get_config
        config = get_config()
        _client = LineStatusClient(config.sqlite.db_path)
    return _client


def _calc_deviation(actual, baseline):
    if actual is None or baseline is None or baseline == 0:
        return None
    return round((actual - baseline) / baseline * 100, 2)


def _judge(row: dict) -> tuple:
    """返回 (recommendation, reason)。"""
    util_peak = row.get("util_peak_pct")
    util_avg = row.get("util_avg_pct")
    latency = row.get("latency_peak_ms")
    avg_util_peak = row.get("avg_util_peak_pct")
    avg_util_avg = row.get("avg_util_avg_pct")
    avg_latency = row.get("avg_latency_peak_ms")

    util_peak_dev = _calc_deviation(util_peak, avg_util_peak)
    util_avg_dev = _calc_deviation(util_avg, avg_util_avg)
    latency_dev = _calc_deviation(latency, avg_latency)

    if util_peak_dev is not None and util_peak_dev > 20 and util_peak is not None and util_peak > 40:
        return "scale_up", f"利用率峰值较基线高 {util_peak_dev}%，已达 {util_peak}%"

    if util_avg_dev is not None and util_avg_dev < -30 and util_avg is not None and util_avg < 15:
        return "scale_down", f"利用率均值较基线低 {abs(util_avg_dev)}%，仅 {util_avg}%"

    if latency_dev is not None and latency_dev > 50:
        return "attention", f"延迟峰值较基线高 {latency_dev}%，达 {latency}ms"

    return "normal", "在正常范围内"


def register(mcp: FastMCP):
    @mcp.tool()
    async def line_status_compare(
        date: Optional[str] = None,
        line_category: Optional[str] = None,
        line_name: Optional[str] = None,
    ) -> dict:
        """对比指定日期的线路实际值与 CMA 基线值，给出扩缩容建议。"""
        client = _get_client()

        if not date:
            with sqlite3.connect(client.db_path) as conn:
                row = conn.execute(
                    "SELECT MAX(report_date) FROM line_status_daily"
                ).fetchone()
                date = row[0] if row else None
            if not date:
                return {"compare_date": None, "results": [], "summary": {"total_lines": 0}}

        rows = client.get_comparison(date, line_category, line_name)
        results = []
        summary = {"total_lines": len(rows), "scale_up": 0, "scale_down": 0, "attention": 0, "normal": 0}

        for row in rows:
            recommendation, reason = _judge(row)
            summary[recommendation] = summary.get(recommendation, 0) + 1

            actual = {
                "traffic_peak_kbps": row.get("traffic_peak_kbps"),
                "util_peak_pct": row.get("util_peak_pct"),
                "latency_peak_ms": row.get("latency_peak_ms"),
            }
            baseline = {
                "avg_traffic_peak_kbps": row.get("avg_traffic_peak_kbps"),
                "avg_util_peak_pct": row.get("avg_util_peak_pct"),
                "avg_latency_peak_ms": row.get("avg_latency_peak_ms"),
                "sample_count": row.get("sample_count"),
            }
            deviation = {
                "traffic_peak": _calc_deviation(row.get("traffic_peak_kbps"), row.get("avg_traffic_peak_kbps")),
                "util_peak": _calc_deviation(row.get("util_peak_pct"), row.get("avg_util_peak_pct")),
                "latency_peak": _calc_deviation(row.get("latency_peak_ms"), row.get("avg_latency_peak_ms")),
            }

            results.append({
                "line_category": row["line_category"],
                "line_name": row["line_name"],
                "actual": actual,
                "baseline": baseline,
                "deviation_pct": deviation,
                "recommendation": recommendation,
                "reason": reason,
            })

        return {
            "compare_date": date,
            "baseline_as_of": date,
            "results": results,
            "summary": summary,
        }
