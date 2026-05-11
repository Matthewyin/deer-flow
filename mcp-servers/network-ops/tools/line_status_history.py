import logging
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


def register(mcp: FastMCP):
    @mcp.tool()
    async def line_status_history(
        line_name: str,
        line_category: Optional[str] = None,
        days: int = 30,
    ) -> dict:
        """查询指定线路的历史趋势数据，含每日实际值和对应基线值。"""
        client = _get_client()
        rows = client.get_history(line_name, line_category, days)

        history = []
        for row in rows:
            history.append({
                "date": row["report_date"],
                "traffic_peak_kbps": row.get("traffic_peak_kbps"),
                "traffic_avg_kbps": row.get("traffic_avg_kbps"),
                "util_peak_pct": row.get("util_peak_pct"),
                "util_avg_pct": row.get("util_avg_pct"),
                "latency_peak_ms": row.get("latency_peak_ms"),
                "baseline_traffic_peak_kbps": row.get("avg_traffic_peak_kbps"),
                "baseline_util_peak_pct": row.get("avg_util_peak_pct"),
            })

        return {
            "line_name": line_name,
            "line_category": line_category,
            "days_requested": days,
            "days_available": len(history),
            "history": history,
        }
