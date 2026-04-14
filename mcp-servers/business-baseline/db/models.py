import sqlite3
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def insert_daily_report(
    conn,
    report_date: str,
    report_time: str,
    period_start: str,
    period_end: str,
    raw_text: str,
) -> bool:
    cursor = conn.execute(
        "INSERT OR IGNORE INTO daily_reports "
        "(report_date, report_time, period_start, period_end, raw_text) "
        "VALUES (?, ?, ?, ?, ?)",
        (report_date, report_time, period_start, period_end, raw_text),
    )
    conn.commit()
    return cursor.rowcount > 0


def insert_metric(conn, m: dict) -> bool:
    keys = [
        "report_date",
        "category",
        "metric_key",
        "metric_name",
        "sub_name",
        "request_count",
        "tech_failures",
        "biz_failures",
        "peak_tps",
        "avg_response_ms",
        "max_response_ms",
        "median_response_ms",
        "extra_value",
        "extra_value_2",
        "unit",
    ]
    values = [m.get(k) for k in keys]
    placeholders = ", ".join(["?"] * len(keys))
    cols = ", ".join(keys)
    cursor = conn.execute(
        f"INSERT OR IGNORE INTO metrics ({cols}) VALUES ({placeholders})",
        values,
    )
    conn.commit()
    return cursor.rowcount > 0


def get_latest_report_date(conn) -> Optional[str]:
    row = conn.execute(
        "SELECT report_date FROM daily_reports ORDER BY report_date DESC LIMIT 1"
    ).fetchone()
    return row["report_date"] if row else None


def get_metrics_by_date(
    conn, report_date: str, metric_key: Optional[str] = None
) -> list[dict]:
    if metric_key:
        rows = conn.execute(
            "SELECT * FROM metrics WHERE report_date = ? AND metric_key = ? "
            "ORDER BY category, metric_key, sub_name",
            (report_date, metric_key),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM metrics WHERE report_date = ? "
            "ORDER BY category, metric_key, sub_name",
            (report_date,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_baselines(conn, metric_key: Optional[str] = None) -> list[dict]:
    if metric_key:
        rows = conn.execute(
            "SELECT * FROM baseline WHERE metric_key = ? ORDER BY metric_key, sub_name",
            (metric_key,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM baseline ORDER BY metric_key, sub_name"
        ).fetchall()
    return [dict(r) for r in rows]


def get_metrics_for_key(conn, metric_key: str, limit: int = 30) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM metrics WHERE metric_key = ? ORDER BY report_date DESC LIMIT ?",
        (metric_key, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def upsert_baseline(conn, b: dict) -> bool:
    keys = [
        "metric_key",
        "sub_name",
        "baseline_type",
        "avg_request_count",
        "avg_tech_failures",
        "avg_biz_failures",
        "avg_peak_tps",
        "avg_response_ms",
        "avg_max_response_ms",
        "avg_median_response_ms",
        "avg_extra_value",
        "sample_count",
    ]
    values = [b.get(k) for k in keys]
    placeholders = ", ".join(["?"] * len(keys))
    cols = ", ".join(keys)

    update_cols = [k for k in keys if k not in ("metric_key", "sub_name")]
    update_clause = ", ".join(f"{k} = excluded.{k}" for k in update_cols)

    cursor = conn.execute(
        f"INSERT INTO baseline ({cols}) VALUES ({placeholders}) "
        f"ON CONFLICT(metric_key, sub_name) DO UPDATE SET {update_clause}",
        values,
    )
    conn.commit()
    return cursor.rowcount > 0


def calculate_and_update_baselines(conn) -> dict:
    """核心函数：对所有 metric_key + sub_name 计算全历史平均并更新 baseline 表。"""
    rows = conn.execute("SELECT DISTINCT metric_key, sub_name FROM metrics").fetchall()

    updated = 0
    errors = 0

    for row in rows:
        mk = row["metric_key"]
        sn = row["sub_name"]

        if sn is not None:
            stats = conn.execute(
                "SELECT "
                "  COUNT(*) as sample_count, "
                "  AVG(request_count) as avg_request_count, "
                "  AVG(tech_failures) as avg_tech_failures, "
                "  AVG(biz_failures) as avg_biz_failures, "
                "  AVG(peak_tps) as avg_peak_tps, "
                "  AVG(avg_response_ms) as avg_response_ms, "
                "  AVG(max_response_ms) as avg_max_response_ms, "
                "  AVG(median_response_ms) as avg_median_response_ms, "
                "  AVG(extra_value) as avg_extra_value "
                "FROM metrics WHERE metric_key = ? AND sub_name = ?",
                (mk, sn),
            ).fetchone()
        else:
            stats = conn.execute(
                "SELECT "
                "  COUNT(*) as sample_count, "
                "  AVG(request_count) as avg_request_count, "
                "  AVG(tech_failures) as avg_tech_failures, "
                "  AVG(biz_failures) as avg_biz_failures, "
                "  AVG(peak_tps) as avg_peak_tps, "
                "  AVG(avg_response_ms) as avg_response_ms, "
                "  AVG(max_response_ms) as avg_max_response_ms, "
                "  AVG(median_response_ms) as avg_median_response_ms, "
                "  AVG(extra_value) as avg_extra_value "
                "FROM metrics WHERE metric_key = ? AND sub_name IS NULL",
                (mk,),
            ).fetchone()

        if not stats or stats["sample_count"] == 0:
            errors += 1
            continue

        baseline_data = {
            "metric_key": mk,
            "sub_name": sn,
            "baseline_type": "full_history",
            "avg_request_count": round(stats["avg_request_count"], 2)
            if stats["avg_request_count"] is not None
            else None,
            "avg_tech_failures": round(stats["avg_tech_failures"], 4)
            if stats["avg_tech_failures"] is not None
            else None,
            "avg_biz_failures": round(stats["avg_biz_failures"], 2)
            if stats["avg_biz_failures"] is not None
            else None,
            "avg_peak_tps": round(stats["avg_peak_tps"], 2)
            if stats["avg_peak_tps"] is not None
            else None,
            "avg_response_ms": round(stats["avg_response_ms"], 2)
            if stats["avg_response_ms"] is not None
            else None,
            "avg_max_response_ms": round(stats["avg_max_response_ms"], 2)
            if stats["avg_max_response_ms"] is not None
            else None,
            "avg_median_response_ms": round(stats["avg_median_response_ms"], 2)
            if stats["avg_median_response_ms"] is not None
            else None,
            "avg_extra_value": round(stats["avg_extra_value"], 2)
            if stats["avg_extra_value"] is not None
            else None,
            "sample_count": stats["sample_count"],
        }

        try:
            upsert_baseline(conn, baseline_data)
            updated += 1
        except Exception as e:
            logger.error(f"Failed to upsert baseline for {mk}/{sn}: {e}")
            errors += 1

    return {"updated": updated, "errors": errors}


def get_metric_keys(conn) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT metric_key FROM metrics ORDER BY metric_key"
    ).fetchall()
    return [r["metric_key"] for r in rows]


def get_report_dates(conn, limit: int = 30) -> list[str]:
    rows = conn.execute(
        "SELECT report_date FROM daily_reports ORDER BY report_date DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [r["report_date"] for r in rows]
