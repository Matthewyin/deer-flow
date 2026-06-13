import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP

from config import get_config
from db.bandwidth_lines_client import BandwidthLinesClient


_client: Optional[BandwidthLinesClient] = None

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_CARRIER_COLORS = {
    "电信": "#5470C6",
    "联通": "#EE6666",
    "移动": "#91CC75",
}


def _get_client() -> BandwidthLinesClient:
    global _client
    if _client is None:
        config = get_config()
        _client = BandwidthLinesClient(config.sqlite.db_path)
    return _client


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return _PROJECT_ROOT / path


def _safe_output_filename(filename: str) -> str:
    cfg = get_config()
    name = Path((filename or "").strip()).name
    if not name:
        name = cfg.bandwidth_report_default_output_filename
    if not name.endswith(".html"):
        name += ".html"
    return name


def _split_terms(value: str) -> list[str]:
    return [term.strip() for term in re.split(r"[\s,，;；]+", value or "") if term.strip()]


def _matches_terms(value: str | None, terms: list[str]) -> bool:
    if not terms:
        return True
    text = value or ""
    return any(term in text for term in terms)


def _to_float(value) -> float:
    if value is None:
        return 0.0
    return round(float(value), 2)


def _to_int(value) -> int:
    if value is None:
        return 0
    return int(value)


def _resolve_period(days: int, start_date: str, end_date: str, available_dates: list[str]):
    if not available_dates:
        return "", "", []

    end = end_date or max(available_dates)
    if start_date:
        start = start_date
    else:
        safe_days = max(1, min(days or 7, 31))
        end_dt = datetime.strptime(end, "%Y-%m-%d")
        start = (end_dt - timedelta(days=safe_days - 1)).strftime("%Y-%m-%d")

    dates = [d for d in available_dates if start <= d <= end]
    return start, end, dates


def _line_key(row: dict) -> str:
    line_no = row.get("line_no") or "unknown"
    ldn = row.get("long_distance_no") or ""
    return f"line_{line_no}_{ldn}".replace(" ", "_")


def _line_name(row: dict) -> str:
    line_no = row.get("line_no")
    carrier = row.get("carrier") or ""
    ldn = row.get("long_distance_no") or ""
    prefix = f"#{line_no}" if line_no is not None else ldn
    return f"{prefix} {carrier}".strip()


def _build_report_config(
    rows: list[dict],
    dates: list[str],
    start: str,
    end: str,
    report_type: str,
) -> dict:
    rows_by_line_date: dict[str, dict[str, dict]] = {}
    first_row_by_line: dict[str, dict] = {}

    for row in rows:
        key = _line_key(row)
        first_row_by_line.setdefault(key, row)
        rows_by_line_date.setdefault(key, {})[row["report_date"]] = row

    lines = {}
    for key in sorted(first_row_by_line, key=lambda k: first_row_by_line[k].get("line_no") or 0):
        first = first_row_by_line[key]
        last_seen = None
        line_dates = rows_by_line_date[key]

        ip = []
        op = []
        ia = []
        oa = []
        lat = []
        bpbl = []
        latbl = []
        bws = []

        for day in dates:
            data_row = line_dates.get(day)
            if data_row:
                last_seen = data_row
            baseline_row = data_row or last_seen or first
            ip.append(_to_float(data_row.get("in_peak_mbps") if data_row else None))
            op.append(_to_float(data_row.get("out_peak_mbps") if data_row else None))
            ia.append(_to_float(data_row.get("in_avg_mbps") if data_row else None))
            oa.append(_to_float(data_row.get("out_avg_mbps") if data_row else None))
            lat.append(_to_float(data_row.get("latency_avg_ms") if data_row else None))
            bpbl.append(_to_float(baseline_row.get("bw_peak_baseline_mbps")))
            latbl.append(_to_float(baseline_row.get("latency_baseline_ms")))
            bws.append(_to_int(baseline_row.get("bandwidth_mbps")))

        carrier = first.get("carrier") or ""
        lines[key] = {
            "name": _line_name(first),
            "color": _CARRIER_COLORS.get(carrier, "#5470C6"),
            "carrier": carrier,
            "bw": bws[-1] if bws else _to_int(first.get("bandwidth_mbps")),
            "ip": ip,
            "op": op,
            "ia": ia,
            "oa": oa,
            "lat": lat,
            "bpbl": bpbl,
            "latbl": latbl,
            "bws": bws,
            "usage": first.get("usage") or first.get("line_group") or "未分组",
        }

    grouped: dict[str, list[str]] = {}
    for key, line in lines.items():
        grouped.setdefault(line["usage"], []).append(key)

    groups = [
        {"title": f"{index}、{usage}（{len(keys)}条）", "lines": keys}
        for index, (usage, keys) in enumerate(grouped.items(), start=1)
    ]

    period = f"{start} ~ {end}"
    day_count = len(dates)
    title_type = report_type or ("日报" if day_count <= 3 else "周报")
    return {
        "dates": [datetime.strptime(day, "%Y-%m-%d").strftime("%m-%d") for day in dates],
        "report_title": f"各线路组 {day_count}天 带宽峰值/均值 & 利用率 & 延迟 趋势{title_type}",
        "report_period": period,
        "report_type": title_type,
        "report_date": datetime.now().strftime("%Y-%m-%d"),
        "lines": lines,
        "groups": groups,
    }


def _render_html(report_config: dict, output_filename: str) -> dict:
    cfg = get_config()
    script_path = _resolve_path(cfg.bandwidth_report_script_path)
    if not script_path.exists():
        return {"ok": False, "error": f"report script not found: {script_path}"}

    filename = _safe_output_filename(output_filename)
    with tempfile.TemporaryDirectory(prefix="network-ops-bandwidth-report-") as tmpdir:
        tmp_path = Path(tmpdir)
        input_path = tmp_path / "report_input.json"
        output_path = tmp_path / filename
        payload = dict(report_config)
        payload["output_path"] = str(output_path)
        input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--input",
                str(input_path),
                "--output",
                str(output_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            return {
                "ok": False,
                "error": "report script failed",
                "returncode": result.returncode,
                "stdout": result.stdout[-2000:],
                "stderr": result.stderr[-4000:],
            }

        if not output_path.exists():
            return {
                "ok": False,
                "error": "report script did not create output file",
                "stdout": result.stdout[-2000:],
                "stderr": result.stderr[-4000:],
            }

        html = output_path.read_text(encoding="utf-8")

    return {
        "ok": True,
        "html": html,
        "output_filename": filename,
        "suggested_output_path": f"/mnt/user-data/outputs/{filename}",
        "stdout": result.stdout[-2000:],
    }


def generate_bandwidth_report(
    days: int = 7,
    start_date: str = "",
    end_date: str = "",
    line_group: str = "",
    usage_keyword: str = "",
    long_distance_no: str = "",
    report_type: str = "",
    output_filename: str = "",
) -> dict:
    client = _get_client()
    available_dates = client.get_available_dates()
    start, end, period_dates = _resolve_period(days, start_date, end_date, available_dates)
    if not period_dates:
        return {
            "ok": False,
            "error": "数据库中没有指定周期的线路带宽数据",
            "period": {"start": start, "end": end},
        }

    rows = client.query_records(
        start,
        end,
        long_distance_no=long_distance_no or None,
    )

    line_group_terms = _split_terms(line_group)
    usage_terms = _split_terms(usage_keyword)
    rows = [
        row
        for row in rows
        if _matches_terms(row.get("line_group"), line_group_terms)
        and _matches_terms(row.get("usage"), usage_terms)
    ]

    if not rows:
        return {
            "ok": False,
            "error": "指定条件下没有线路带宽数据",
            "period": {"start": start, "end": end},
            "filters": {
                "line_group": line_group,
                "usage_keyword": usage_keyword,
                "long_distance_no": long_distance_no,
            },
        }

    report_config = _build_report_config(rows, period_dates, start, end, report_type)
    result = _render_html(report_config, output_filename)
    if not result.get("ok"):
        return result

    result.update(
        {
            "period": {"start": start, "end": end},
            "date_count": len(period_dates),
            "line_count": len(report_config["lines"]),
            "group_count": len(report_config["groups"]),
            "filters": {
                "line_group": line_group,
                "usage_keyword": usage_keyword,
                "long_distance_no": long_distance_no,
            },
        }
    )
    return result


def register(mcp: FastMCP):
    @mcp.tool()
    def bandwidth_report_generate(
        days: int = 7,
        start_date: str = "",
        end_date: str = "",
        line_group: str = "",
        usage_keyword: str = "",
        long_distance_no: str = "",
        report_type: str = "",
        output_filename: str = "",
    ) -> dict:
        """直接查询带宽数据并生成 HTML 趋势报告。

        Args:
            days: 统计天数，默认 7。仅在未提供 start_date 时生效。
            start_date: 开始日期（YYYY-MM-DD），空则根据 days 自动计算。
            end_date: 结束日期（YYYY-MM-DD），空则取最新可用日期。
            line_group: 线路组关键词，支持模糊匹配；空则不过滤。
            usage_keyword: 用途关键词，支持模糊匹配；空则不过滤。
            long_distance_no: 线路编号过滤，支持多个编号。
            report_type: 展示类型，通常为“周报”或“日报”；空则按天数自动判断。
            output_filename: 建议保存给用户的 HTML 文件名。

        Returns:
            dict: 成功时返回 html、suggested_output_path、line_count、group_count。
        """
        return generate_bandwidth_report(
            days=days,
            start_date=start_date,
            end_date=end_date,
            line_group=line_group,
            usage_keyword=usage_keyword,
            long_distance_no=long_distance_no,
            report_type=report_type,
            output_filename=output_filename,
        )
