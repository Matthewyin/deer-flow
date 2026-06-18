"""线路带宽数据 SQLite 客户端。

负责 HTML 网络报告解析后的线路带宽数据入库与查询。
"""

import logging
import re
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _resolve_path(path_str: str) -> str:
    p = Path(path_str)
    if p.is_absolute():
        return str(p)
    return str(_PROJECT_ROOT / p)


_CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS bandwidth_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date TEXT NOT NULL,
    line_group TEXT NOT NULL,
    line_no INTEGER NOT NULL,
    province TEXT,
    carrier TEXT,
    usage TEXT,
    bandwidth_mbps INTEGER,
    long_distance_no TEXT,
    in_peak_mbps REAL,
    in_avg_mbps REAL,
    in_peak_util_pct REAL,
    in_peak_time TEXT,
    out_peak_mbps REAL,
    out_avg_mbps REAL,
    out_peak_util_pct REAL,
    out_peak_time TEXT,
    latency_avg_ms REAL,
    bw_peak_baseline_mbps REAL,
    bw_util_threshold_pct INTEGER,
    latency_baseline_ms REAL,
    latency_threshold_ms REAL,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(report_date, line_group, line_no)
);

CREATE INDEX IF NOT EXISTS idx_bl_date ON bandwidth_lines(report_date);
CREATE INDEX IF NOT EXISTS idx_bl_ldn ON bandwidth_lines(long_distance_no);
CREATE INDEX IF NOT EXISTS idx_bl_date_ldn ON bandwidth_lines(report_date, long_distance_no);
"""

_COLUMNS = [
    "report_date",
    "line_group",
    "line_no",
    "province",
    "carrier",
    "usage",
    "bandwidth_mbps",
    "long_distance_no",
    "in_peak_mbps",
    "in_avg_mbps",
    "in_peak_util_pct",
    "in_peak_time",
    "out_peak_mbps",
    "out_avg_mbps",
    "out_peak_util_pct",
    "out_peak_time",
    "latency_avg_ms",
    "bw_peak_baseline_mbps",
    "bw_util_threshold_pct",
    "latency_baseline_ms",
    "latency_threshold_ms",
]

_ALL_COLUMNS = ["id", *_COLUMNS, "created_at"]

_FORCED_BANDWIDTH_BY_LINE = {
    ("西五环互联网B区线路", 201): 500,
    ("西五环互联网B区线路", 202): 400,
    ("西五环互联网B区线路", 203): 400,
}

_FORCED_LONG_DISTANCE_NO_BY_LINE = {
    ("TLS终端专线", 151): "MSTPBJ1003453797",
    ("TLS终端专线", 152): "110YTW19089212",
    ("TLS终端专线", 153): "MSTPBJ1003608615",
    ("TLS终端专线", 154): "110YTW20371603",
    ("体彩APP专线", 159): "北京本地B17582400",
    ("体彩APP专线", 160): "北京本地110YTW007389",
    ("体彩APP专线", 161): "MSTPBJ1002296362",
    ("体彩APP专线", 162): "110YTW12150861",
    ("西五环互联网B区线路", 201): "B14651896",
    ("西五环互联网B区线路", 202): "光17783",
    ("西五环互联网B区线路", 203): "26200002474",
}


def _split_long_distance_no_terms(value: str) -> list[str]:
    return [
        term.strip()
        for term in re.split(r"[\s,，;；]+", value)
        if term.strip()
    ]


def _to_float(value) -> float:
    if value is None:
        return 0.0
    return float(value)


def _to_int_or_none(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_bandwidth_policy(row: dict) -> dict:
    key = (row.get("line_group"), _to_int_or_none(row.get("line_no")))
    bandwidth = _FORCED_BANDWIDTH_BY_LINE.get(key)
    line_no = _FORCED_LONG_DISTANCE_NO_BY_LINE.get(key)
    if not bandwidth and not line_no:
        return row

    normalized = dict(row)
    if bandwidth:
        normalized["bandwidth_mbps"] = bandwidth
        normalized["in_peak_util_pct"] = round(_to_float(row.get("in_peak_mbps")) * 100 / bandwidth, 2)
        normalized["out_peak_util_pct"] = round(_to_float(row.get("out_peak_mbps")) * 100 / bandwidth, 2)
    if line_no:
        normalized["long_distance_no"] = line_no
    return normalized

_CREATE_MIGRATION_TABLE_SQL = """
CREATE TABLE bandwidth_lines_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date TEXT NOT NULL,
    line_group TEXT NOT NULL,
    line_no INTEGER NOT NULL,
    province TEXT,
    carrier TEXT,
    usage TEXT,
    bandwidth_mbps INTEGER,
    long_distance_no TEXT,
    in_peak_mbps REAL,
    in_avg_mbps REAL,
    in_peak_util_pct REAL,
    in_peak_time TEXT,
    out_peak_mbps REAL,
    out_avg_mbps REAL,
    out_peak_util_pct REAL,
    out_peak_time TEXT,
    latency_avg_ms REAL,
    bw_peak_baseline_mbps REAL,
    bw_util_threshold_pct INTEGER,
    latency_baseline_ms REAL,
    latency_threshold_ms REAL,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(report_date, line_group, line_no)
);
"""


def _get_unique_index_columns(conn: sqlite3.Connection) -> list[list[str]]:
    indexes = conn.execute("PRAGMA index_list(bandwidth_lines)").fetchall()
    unique_columns = []
    for index in indexes:
        if not index[2]:
            continue
        rows = conn.execute(f"PRAGMA index_info({index[1]})").fetchall()
        unique_columns.append([row[2] for row in rows])
    return unique_columns


def _ensure_unique_key(conn: sqlite3.Connection) -> None:
    desired = ["report_date", "line_group", "line_no"]
    if desired in _get_unique_index_columns(conn):
        return

    logger.info("Migrating bandwidth_lines unique key to report_date + line_group + line_no")
    columns_sql = ", ".join(_ALL_COLUMNS)
    conn.execute("ALTER TABLE bandwidth_lines RENAME TO bandwidth_lines_old")
    conn.execute(_CREATE_MIGRATION_TABLE_SQL)
    conn.execute(
        f"INSERT OR IGNORE INTO bandwidth_lines_new ({columns_sql}) "
        f"SELECT {columns_sql} FROM bandwidth_lines_old"
    )
    conn.execute("DROP TABLE bandwidth_lines_old")
    conn.execute("ALTER TABLE bandwidth_lines_new RENAME TO bandwidth_lines")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bl_date ON bandwidth_lines(report_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bl_ldn ON bandwidth_lines(long_distance_no)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_bl_date_ldn "
        "ON bandwidth_lines(report_date, long_distance_no)"
    )


class BandwidthLinesClient:
    def __init__(self, db_path: str):
        self.db_path = _resolve_path(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(_CREATE_TABLES_SQL)
            _ensure_unique_key(conn)

    def ingest_data(self, rows: list[dict]) -> tuple[int, int]:
        """批量入库，返回 (inserted, skipped)。"""
        inserted = 0
        skipped = 0
        placeholders = ", ".join(["?"] * len(_COLUMNS))
        columns_sql = ", ".join(_COLUMNS)
        sql = f"INSERT OR IGNORE INTO bandwidth_lines ({columns_sql}) VALUES ({placeholders})"
        with sqlite3.connect(self.db_path) as conn:
            for row in rows:
                normalized_row = _normalize_bandwidth_policy(row)
                values = tuple(normalized_row.get(col) for col in _COLUMNS)
                cur = conn.execute(sql, values)
                if cur.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1
            conn.commit()
        return inserted, skipped

    def get_lines_for_period(
        self,
        start_date: str,
        end_date: str,
        long_distance_no: Optional[str] = None,
    ) -> list[dict]:
        """按日期范围查询线路数据，可选按线路编号过滤。"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = (
                "SELECT * FROM bandwidth_lines "
                "WHERE report_date >= ? AND report_date <= ?"
            )
            params: list = [start_date, end_date]
            if long_distance_no:
                query += " AND long_distance_no = ?"
                params.append(long_distance_no)
            query += " ORDER BY report_date, line_no"
            return [dict(row) for row in conn.execute(query, params).fetchall()]

    def get_available_dates(self) -> list[str]:
        """返回已入库的所有 report_date（升序去重）。"""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT DISTINCT report_date FROM bandwidth_lines ORDER BY report_date"
            ).fetchall()
            return [r[0] for r in rows]

    def query_records(
        self,
        start_date: str,
        end_date: str,
        line_group: str | None = None,
        long_distance_no: str | None = None,
    ) -> list[dict]:
        """按日期范围查询原始带宽记录，返回 bandwidth_lines 全字段。"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = (
                "SELECT * FROM bandwidth_lines "
                "WHERE report_date >= ? AND report_date <= ?"
            )
            params: list = [start_date, end_date]

            if line_group:
                query += " AND line_group = ?"
                params.append(line_group)

            if long_distance_no:
                terms = _split_long_distance_no_terms(long_distance_no)
                if terms:
                    clauses = []
                    for term in terms:
                        clauses.append("(long_distance_no = ? OR long_distance_no LIKE ?)")
                        params.extend([term, f"%{term}%"])
                    query += " AND (" + " OR ".join(clauses) + ")"

            query += " ORDER BY report_date, line_no"
            return [dict(row) for row in conn.execute(query, params).fetchall()]

    def delete_by_dates(self, dates: list[str]) -> int:
        """删除指定日期的数据，返回删除的行数。"""
        if not dates:
            return 0
        with sqlite3.connect(self.db_path) as conn:
            placeholders = ", ".join(["?"] * len(dates))
            cur = conn.execute(
                f"DELETE FROM bandwidth_lines WHERE report_date IN ({placeholders})",
                dates,
            )
            conn.commit()
            return cur.rowcount
