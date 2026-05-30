import logging
from typing import Optional

from fastmcp import FastMCP

from config import get_config
from db.bandwidth_lines_client import BandwidthLinesClient

logger = logging.getLogger(__name__)

_client: Optional[BandwidthLinesClient] = None


def _get_client() -> BandwidthLinesClient:
    global _client
    if _client is None:
        config = get_config()
        _client = BandwidthLinesClient(config.sqlite.db_path)
    return _client


def _max_peak_util(row: dict) -> tuple[float | None, str | None]:
    in_util = row.get("in_peak_util_pct")
    out_util = row.get("out_peak_util_pct")

    candidates = []
    if in_util is not None:
        candidates.append((float(in_util), "in"))
    if out_util is not None:
        candidates.append((float(out_util), "out"))

    if not candidates:
        return None, None

    return max(candidates, key=lambda item: item[0])


def register(mcp: FastMCP):
    @mcp.tool()
    def bandwidth_records_query(
        date: str = "",
        start_date: str = "",
        end_date: str = "",
        line_group: str = "",
        long_distance_no: str = "",
        min_peak_util_pct: float = 0,
        limit: int = 200,
    ) -> dict:
        """查询 bandwidth_lines 原始记录，保留数据库全字段。

        Args:
            date: 单日查询日期（YYYY-MM-DD）。传入后优先于 start_date/end_date。
            start_date: 开始日期（YYYY-MM-DD）。
            end_date: 结束日期（YYYY-MM-DD）。
            line_group: 线路组过滤，空则不过滤。
            long_distance_no: 线路编号过滤，支持短编号模糊匹配；多个编号可用空格、逗号或分号分隔。
            min_peak_util_pct: 峰值利用率下限，按 in/out 较大值过滤。
            limit: 返回记录上限，默认 200。

        Returns:
            dict: records 中每条记录包含 bandwidth_lines 原始字段，并额外包含
            max_peak_util_pct 和 max_peak_direction 两个计算字段。
        """
        client = _get_client()
        available_dates = client.get_available_dates()

        if not available_dates:
            return {
                "query": {
                    "date": date,
                    "start_date": start_date,
                    "end_date": end_date,
                    "line_group": line_group,
                    "long_distance_no": long_distance_no,
                    "min_peak_util_pct": min_peak_util_pct,
                    "limit": limit,
                },
                "total_matched": 0,
                "returned": 0,
                "records": [],
                "message": "数据库中没有线路带宽数据",
            }

        if date:
            start = date
            end = date
        elif not start_date and not end_date:
            start = min(available_dates)
            end = max(available_dates)
        else:
            latest = max(available_dates)
            end = end_date or latest
            start = start_date or end

        rows = client.query_records(
            start,
            end,
            line_group=line_group or None,
            long_distance_no=long_distance_no or None,
        )

        records = []
        for row in rows:
            max_util, direction = _max_peak_util(row)
            if min_peak_util_pct and (
                max_util is None or max_util < min_peak_util_pct
            ):
                continue

            records.append(
                {
                    **row,
                    "max_peak_util_pct": max_util,
                    "max_peak_direction": direction,
                }
            )

        safe_limit = max(1, min(limit, 1000))
        limited_records = records[:safe_limit]

        return {
            "query": {
                "date": date,
                "start_date": start,
                "end_date": end,
                "line_group": line_group,
                "long_distance_no": long_distance_no,
                "min_peak_util_pct": min_peak_util_pct,
                "limit": safe_limit,
            },
            "available_dates": available_dates,
            "total_matched": len(records),
            "returned": len(limited_records),
            "records": limited_records,
        }
