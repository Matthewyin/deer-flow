import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def beijing_now() -> datetime:
    return datetime.now(BEIJING_TZ)


def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: str) -> None:
    with connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS world_cup_uploads (
                upload_id TEXT PRIMARY KEY,
                source_filename TEXT NOT NULL,
                file_hash TEXT NOT NULL UNIQUE,
                uploaded_at TEXT NOT NULL,
                parsed_json_path TEXT NOT NULL,
                raw_file_path TEXT NOT NULL,
                sheet_count INTEGER NOT NULL,
                record_count INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS world_cup_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                upload_id TEXT NOT NULL,
                sheet_name TEXT NOT NULL,
                sheet_slug TEXT NOT NULL,
                granularity TEXT NOT NULL,
                period_key TEXT NOT NULL,
                date TEXT,
                week_label TEXT,
                hour_range TEXT NOT NULL DEFAULT '',
                metric_group TEXT NOT NULL DEFAULT '',
                metric_key TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                value_role TEXT NOT NULL,
                value_numeric REAL,
                value_text TEXT,
                unit TEXT NOT NULL DEFAULT '',
                source_column TEXT NOT NULL,
                row_no INTEGER NOT NULL,
                FOREIGN KEY(upload_id) REFERENCES world_cup_uploads(upload_id) ON DELETE CASCADE,
                UNIQUE(upload_id, sheet_name, period_key, hour_range, metric_key, value_role, row_no, source_column)
            );

            CREATE TABLE IF NOT EXISTS world_cup_import_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                upload_id TEXT NOT NULL,
                sheet_name TEXT,
                row_no INTEGER,
                field_name TEXT,
                error_message TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY(upload_id) REFERENCES world_cup_uploads(upload_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_wc_metrics_date ON world_cup_metrics(date);
            CREATE INDEX IF NOT EXISTS idx_wc_metrics_key ON world_cup_metrics(metric_key);
            CREATE INDEX IF NOT EXISTS idx_wc_metrics_period ON world_cup_metrics(period_key);
            CREATE INDEX IF NOT EXISTS idx_wc_metrics_upload ON world_cup_metrics(upload_id);
            """
        )


def get_upload_by_hash(db_path: str, file_hash: str) -> dict | None:
    init_db(db_path)
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM world_cup_uploads WHERE file_hash = ?",
            (file_hash,),
        ).fetchone()
        return dict(row) if row else None


def delete_upload(db_path: str, upload_id: str) -> dict:
    init_db(db_path)
    with connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        row = conn.execute(
            "SELECT * FROM world_cup_uploads WHERE upload_id = ?",
            (upload_id,),
        ).fetchone()
        if row is None:
            return {"deleted": False, "upload_id": upload_id, "message": "upload_id 不存在"}
        upload = dict(row)
        conn.execute("DELETE FROM world_cup_uploads WHERE upload_id = ?", (upload_id,))
        conn.commit()

    for key in ("raw_file_path", "parsed_json_path"):
        path = upload.get(key)
        if path:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
    return {"deleted": True, "upload_id": upload_id}


def clear_all_data(db_path: str) -> dict:
    init_db(db_path)
    with connect(db_path) as conn:
        upload_count = conn.execute("SELECT COUNT(*) FROM world_cup_uploads").fetchone()[0]
        metric_count = conn.execute("SELECT COUNT(*) FROM world_cup_metrics").fetchone()[0]
        error_count = conn.execute("SELECT COUNT(*) FROM world_cup_import_errors").fetchone()[0]
        conn.execute("DELETE FROM world_cup_import_errors")
        conn.execute("DELETE FROM world_cup_metrics")
        conn.execute("DELETE FROM world_cup_uploads")
        conn.commit()
    return {
        "cleared_uploads": upload_count,
        "cleared_metrics": metric_count,
        "cleared_errors": error_count,
    }


def import_parsed_data(
    db_path: str,
    parsed: dict,
    *,
    source_filename: str,
    file_hash: str,
    raw_file_path: str,
    parsed_json_path: str,
) -> dict:
    init_db(db_path)
    upload_id = parsed["upload_id"]
    uploaded_at = beijing_now().isoformat(timespec="seconds")
    records = parsed.get("records", [])
    errors = parsed.get("errors", [])

    with connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(
            """
            INSERT INTO world_cup_uploads (
                upload_id, source_filename, file_hash, uploaded_at,
                parsed_json_path, raw_file_path, sheet_count, record_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                upload_id,
                source_filename,
                file_hash,
                uploaded_at,
                parsed_json_path,
                raw_file_path,
                parsed.get("sheet_count", 0),
                len(records),
            ),
        )

        metric_columns = [
            "upload_id",
            "sheet_name",
            "sheet_slug",
            "granularity",
            "period_key",
            "date",
            "week_label",
            "hour_range",
            "metric_group",
            "metric_key",
            "metric_name",
            "value_role",
            "value_numeric",
            "value_text",
            "unit",
            "source_column",
            "row_no",
        ]
        placeholders = ", ".join(["?"] * len(metric_columns))
        columns_sql = ", ".join(metric_columns)
        update_sql = ", ".join(
            f"{col}=excluded.{col}"
            for col in ("value_numeric", "value_text", "unit", "source_column", "row_no")
        )
        sql = (
            f"INSERT INTO world_cup_metrics ({columns_sql}) VALUES ({placeholders}) "
            f"ON CONFLICT(upload_id, sheet_name, period_key, hour_range, metric_key, value_role, row_no, source_column) "
            f"DO UPDATE SET {update_sql}"
        )
        for record in records:
            conn.execute(sql, tuple(record.get(col) for col in metric_columns))

        for error in errors:
            conn.execute(
                """
                INSERT INTO world_cup_import_errors (
                    upload_id, sheet_name, row_no, field_name, error_message
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    upload_id,
                    error.get("sheet_name"),
                    error.get("row_no"),
                    error.get("field_name"),
                    error.get("error_message", ""),
                ),
            )
        conn.commit()

    return {
        "upload_id": upload_id,
        "sheet_count": parsed.get("sheet_count", 0),
        "record_count": len(records),
        "error_count": len(errors),
        "uploaded_at": uploaded_at,
    }


def status(db_path: str) -> dict:
    init_db(db_path)
    with connect(db_path) as conn:
        latest = conn.execute(
            "SELECT * FROM world_cup_uploads ORDER BY uploaded_at DESC LIMIT 1"
        ).fetchone()
        upload_count = conn.execute("SELECT COUNT(*) FROM world_cup_uploads").fetchone()[0]
        metric_count = conn.execute("SELECT COUNT(*) FROM world_cup_metrics").fetchone()[0]
        dates = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT date FROM world_cup_metrics WHERE date IS NOT NULL ORDER BY date"
            ).fetchall()
        ]
        sheets = [
            dict(r)
            for r in conn.execute(
                "SELECT sheet_name, granularity, COUNT(*) AS record_count "
                "FROM world_cup_metrics GROUP BY sheet_name, granularity ORDER BY sheet_name"
            ).fetchall()
        ]
        uploads = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM world_cup_uploads ORDER BY uploaded_at DESC LIMIT 20"
            ).fetchall()
        ]
    return {
        "latest_upload": dict(latest) if latest else None,
        "upload_count": upload_count,
        "metric_count": metric_count,
        "available_dates": dates,
        "date_range": {"start": dates[0], "end": dates[-1]} if dates else None,
        "sheets": sheets,
        "uploads": uploads,
    }


def query_records(
    db_path: str,
    *,
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
    init_db(db_path)
    where = []
    params: list[Any] = []
    if date:
        where.append("date = ?")
        params.append(date)
    else:
        if start_date:
            where.append("date >= ?")
            params.append(start_date)
        if end_date:
            where.append("date <= ?")
            params.append(end_date)
    if sheet_name:
        where.append("(sheet_name = ? OR sheet_slug = ?)")
        params.extend([sheet_name, sheet_name])
    if granularity:
        where.append("granularity = ?")
        params.append(granularity)
    if hour_range:
        where.append("hour_range = ?")
        params.append(hour_range)
    if metric_key:
        where.append("metric_key = ?")
        params.append(metric_key)
    if metric:
        where.append("(metric_key = ? OR metric_name LIKE ?)")
        params.extend([metric, f"%{metric}%"])

    where_sql = "WHERE " + " AND ".join(where) if where else ""
    safe_limit = max(1, min(limit, 2000))
    with connect(db_path) as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                f"""
                SELECT * FROM world_cup_metrics
                {where_sql}
                ORDER BY date, week_label, hour_range, sheet_name, row_no, source_column
                LIMIT ?
                """,
                (*params, safe_limit),
            ).fetchall()
        ]
        total = conn.execute(
            f"SELECT COUNT(*) FROM world_cup_metrics {where_sql}",
            params,
        ).fetchone()[0]
    return {
        "query": {
            "date": date,
            "start_date": start_date,
            "end_date": end_date,
            "sheet_name": sheet_name,
            "granularity": granularity,
            "metric_key": metric_key,
            "metric": metric,
            "hour_range": hour_range,
            "limit": safe_limit,
        },
        "total_matched": total,
        "returned": len(rows),
        "records": rows,
    }


def metric_catalog(db_path: str) -> dict:
    init_db(db_path)
    with connect(db_path) as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT metric_key, metric_name, sheet_name, granularity, unit,
                       COUNT(*) AS sample_count
                FROM world_cup_metrics
                GROUP BY metric_key, metric_name, sheet_name, granularity, unit
                ORDER BY sheet_name, metric_name
                """
            ).fetchall()
        ]
    return {"metrics": rows, "metric_count": len(rows)}


def summary(
    db_path: str,
    *,
    date: str = "",
    start_date: str = "",
    end_date: str = "",
    sheet_name: str = "",
    granularity: str = "",
    metric_key: str = "",
    metric: str = "",
    top_n: int = 10,
) -> dict:
    init_db(db_path)
    st = status(db_path)
    if not date and not start_date and not end_date and st["available_dates"]:
        date = st["available_dates"][-1]

    records = query_records(
        db_path,
        date=date,
        start_date=start_date,
        end_date=end_date,
        sheet_name=sheet_name,
        granularity=granularity,
        metric_key=metric_key,
        metric=metric,
        limit=2000,
    )["records"]
    safe_top = max(1, min(top_n, 50))
    current_records = [
        r for r in records if r["value_role"] in ("today", "current") and r["value_numeric"] is not None
    ]
    compare_records = [
        r for r in records if r["value_role"] == "compare_pct" and r["value_numeric"] is not None
    ]
    empty_value_records = [
        r
        for r in records
        if r["value_role"] in ("today", "current", "yesterday")
        and r["value_numeric"] is None
        and not r["value_text"]
    ]

    peaks_by_metric: dict[str, dict] = {}
    for r in current_records:
        key = f"{r['sheet_name']}::{r['metric_key']}::{r['metric_name']}"
        prev = peaks_by_metric.get(key)
        if prev is None or r["value_numeric"] > prev["value_numeric"]:
            peaks_by_metric[key] = r

    peaks = sorted(peaks_by_metric.values(), key=lambda r: r["value_numeric"], reverse=True)[:safe_top]
    changes = sorted(compare_records, key=lambda r: abs(r["value_numeric"]), reverse=True)[:safe_top]

    return {
        "date": date,
        "start_date": start_date,
        "end_date": end_date,
        "sheet_name": sheet_name,
        "granularity": granularity,
        "metric_key": metric_key,
        "metric": metric,
        "record_count": len(records),
        "peak_metrics": peaks,
        "top_changes": changes,
        "empty_value_count": len(empty_value_records),
        "empty_value_samples": empty_value_records[:safe_top],
        "missing_count": 0,
        "missing_samples": [],
    }


def report(db_path: str, *, date: str = "") -> dict:
    data = summary(db_path, date=date, top_n=8)
    title_date = data["date"] or data["end_date"] or "最新"
    lines = [
        f"## 世界杯保障数据日报 — {title_date}",
        "",
        "### 总览",
        f"- 记录数：{data['record_count']}",
        f"- 空值项：{data['empty_value_count']}",
        "",
        "### 峰值指标",
        "| 指标 | 日期 | 时段 | 数值 | 单位 | 来源 |",
        "|---|---|---|---:|---|---|",
    ]
    for r in data["peak_metrics"]:
        lines.append(
            f"| {r['metric_name']} | {r['date'] or r['week_label'] or ''} | "
            f"{r['hour_range'] or '-'} | {r['value_numeric']} | {r['unit']} | {r['sheet_name']} |"
        )
    lines.extend(["", "### 波动排行", "| 指标 | 日期 | 时段 | 波动% | 来源 |", "|---|---|---|---:|---|"])
    for r in data["top_changes"]:
        lines.append(
            f"| {r['metric_name']} | {r['date'] or r['week_label'] or ''} | "
            f"{r['hour_range'] or '-'} | {r['value_numeric']} | {r['sheet_name']} |"
        )
    lines.append("")
    lines.append("> 本报告只展示数据波动、峰值和空值情况，不直接定性为故障或异常。")
    return {"date": title_date, "markdown": "\n".join(lines), "summary": data}
