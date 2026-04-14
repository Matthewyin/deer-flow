import sqlite3
import os


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_date TEXT NOT NULL UNIQUE,
            report_time TEXT NOT NULL,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            raw_text TEXT NOT NULL,
            parsed_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(report_date)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_date TEXT NOT NULL,
            category TEXT NOT NULL,
            metric_key TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            sub_name TEXT,
            request_count INTEGER,
            tech_failures INTEGER,
            biz_failures INTEGER,
            peak_tps REAL,
            avg_response_ms REAL,
            max_response_ms REAL,
            median_response_ms REAL,
            extra_value REAL,
            extra_value_2 REAL,
            unit TEXT DEFAULT '',
            UNIQUE(report_date, metric_key, sub_name)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS baseline (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_key TEXT NOT NULL,
            sub_name TEXT,
            baseline_type TEXT NOT NULL DEFAULT 'full_history',
            avg_request_count REAL,
            avg_tech_failures REAL,
            avg_biz_failures REAL,
            avg_peak_tps REAL,
            avg_response_ms REAL,
            avg_max_response_ms REAL,
            avg_median_response_ms REAL,
            avg_extra_value REAL,
            sample_count INTEGER NOT NULL,
            calculated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(metric_key, sub_name)
        )
    """)

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_metrics_date ON metrics(report_date)"
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_key ON metrics(metric_key)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_metrics_category ON metrics(category)"
    )

    conn.commit()
    conn.close()
