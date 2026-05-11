"""线路状态数据 SQLite 客户端。

负责每日数据入库和 CMA（累计移动平均）基线计算。
"""

import logging
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
CREATE TABLE IF NOT EXISTS line_status_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date TEXT NOT NULL,
    line_category TEXT NOT NULL,
    line_name TEXT NOT NULL,
    traffic_peak_kbps REAL,
    traffic_avg_kbps REAL,
    util_peak_pct REAL,
    util_avg_pct REAL,
    latency_peak_ms REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(report_date, line_category, line_name)
);

CREATE TABLE IF NOT EXISTS line_status_baseline (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    line_category TEXT NOT NULL,
    line_name TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    sample_count INTEGER NOT NULL,
    avg_traffic_peak_kbps REAL,
    avg_traffic_avg_kbps REAL,
    avg_util_peak_pct REAL,
    avg_util_avg_pct REAL,
    avg_latency_peak_ms REAL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(line_category, line_name, as_of_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_date ON line_status_daily(report_date);
CREATE INDEX IF NOT EXISTS idx_daily_line ON line_status_daily(line_category, line_name);
CREATE INDEX IF NOT EXISTS idx_baseline_line ON line_status_baseline(line_category, line_name);
"""


class LineStatusClient:
    def __init__(self, db_path: str):
        self.db_path = _resolve_path(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(_CREATE_TABLES_SQL)

    def get_ingested_dates(self) -> set[str]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT DISTINCT report_date FROM line_status_daily").fetchall()
            return {r[0] for r in rows}

    def ingest_daily_data(self, data: dict) -> tuple[int, int]:
        """入库单日数据，返回 (inserted, skipped)。"""
        inserted = 0
        skipped = 0
        with sqlite3.connect(self.db_path) as conn:
            for category, lines in data.get("line_categories", {}).items():
                for line in lines:
                    try:
                        conn.execute(
                            """INSERT OR IGNORE INTO line_status_daily
                            (report_date, line_category, line_name,
                             traffic_peak_kbps, traffic_avg_kbps,
                             util_peak_pct, util_avg_pct, latency_peak_ms)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                            (
                                data["report_date"],
                                category,
                                line["line_name"],
                                line.get("traffic_peak_kbps"),
                                line.get("traffic_avg_kbps"),
                                line.get("util_peak_pct"),
                                line.get("util_avg_pct"),
                                line.get("latency_peak_ms"),
                            ),
                        )
                        if conn.total_changes > 0:
                            inserted += 1
                        else:
                            skipped += 1
                    except sqlite3.IntegrityError:
                        skipped += 1
            conn.commit()
        return inserted, skipped

    def update_baselines(self, as_of_date: str) -> int:
        """对所有有数据的线路重新计算 CMA 基线，返回更新条数。"""
        with sqlite3.connect(self.db_path) as conn:
            # 获取所有 (line_category, line_name) 组合
            pairs = conn.execute(
                "SELECT DISTINCT line_category, line_name FROM line_status_daily"
            ).fetchall()

            for cat, name in pairs:
                conn.execute(
                    """INSERT OR REPLACE INTO line_status_baseline
                    (line_category, line_name, as_of_date, sample_count,
                     avg_traffic_peak_kbps, avg_traffic_avg_kbps,
                     avg_util_peak_pct, avg_util_avg_pct,
                     avg_latency_peak_ms, updated_at)
                    SELECT ?, ?, ?, COUNT(*),
                           AVG(traffic_peak_kbps), AVG(traffic_avg_kbps),
                           AVG(util_peak_pct), AVG(util_avg_pct),
                           AVG(latency_peak_ms), CURRENT_TIMESTAMP
                    FROM line_status_daily
                    WHERE line_category = ? AND line_name = ?
                    GROUP BY line_category, line_name""",
                    (cat, name, as_of_date, cat, name),
                )
            conn.commit()
            return len(pairs)

    def get_comparison(
        self, date: str,
        line_category: Optional[str] = None,
        line_name: Optional[str] = None,
    ) -> list[dict]:
        """查询指定日期的实际值和基线值。"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            query = """
                SELECT d.line_category, d.line_name,
                       d.traffic_peak_kbps, d.traffic_avg_kbps,
                       d.util_peak_pct, d.util_avg_pct, d.latency_peak_ms,
                       b.sample_count,
                       b.avg_traffic_peak_kbps, b.avg_traffic_avg_kbps,
                       b.avg_util_peak_pct, b.avg_util_avg_pct,
                       b.avg_latency_peak_ms
                FROM line_status_daily d
                LEFT JOIN line_status_baseline b
                    ON d.line_category = b.line_category
                    AND d.line_name = b.line_name
                    AND b.as_of_date = ?
                WHERE d.report_date = ?
            """
            params: list = [date, date]

            if line_category:
                query += " AND d.line_category = ?"
                params.append(line_category)
            if line_name:
                query += " AND d.line_name = ?"
                params.append(line_name)

            return [dict(row) for row in conn.execute(query, params).fetchall()]

    def get_history(
        self, line_name: str,
        line_category: Optional[str] = None,
        days: int = 30,
    ) -> list[dict]:
        """查询指定线路的历史趋势数据。"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            query = """
                SELECT d.report_date, d.traffic_peak_kbps, d.traffic_avg_kbps,
                       d.util_peak_pct, d.util_avg_pct, d.latency_peak_ms,
                       b.avg_traffic_peak_kbps, b.avg_util_peak_pct
                FROM line_status_daily d
                LEFT JOIN line_status_baseline b
                    ON d.line_category = b.line_category
                    AND d.line_name = b.line_name
                    AND b.as_of_date = d.report_date
                WHERE d.line_name = ?
            """
            params: list = [line_name]

            if line_category:
                query += " AND d.line_category = ?"
                params.append(line_category)

            query += " ORDER BY d.report_date DESC LIMIT ?"
            params.append(days)

            return [dict(row) for row in conn.execute(query, params).fetchall()]
