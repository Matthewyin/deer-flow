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
        CREATE TABLE IF NOT EXISTS raw_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            region TEXT NOT NULL,
            filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            file_hash TEXT,
            UNIQUE(region, filename)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS probe_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            region TEXT NOT NULL,
            domain TEXT NOT NULL,
            target_ip TEXT NOT NULL,
            probe_timestamp TEXT NOT NULL,
            avg_rtt_ms REAL,
            min_rtt_ms REAL,
            max_rtt_ms REAL,
            packet_loss_pct REAL,
            tcp_connect_ms REAL,
            fastest_ip TEXT,
            recommended_ip TEXT,
            tls_handshake_ms REAL,
            tls_protocol TEXT,
            mutual_tls INTEGER,
            dns_resolution_ms REAL,
            resolved_ips TEXT,
            mtr_hops INTEGER,
            mtr_avg_latency REAL,
            mtr_common_hops TEXT,
            raw_json_path TEXT,
            UNIQUE(region, domain, target_ip, probe_timestamp)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS probe_baseline (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            region TEXT NOT NULL,
            domain TEXT NOT NULL,
            baseline_version TEXT NOT NULL,
            icmp_avg_rtt REAL,
            icmp_max_rtt REAL,
            icmp_min_rtt REAL,
            icmp_packet_loss REAL,
            tcp_avg_connect REAL,
            tcp_fastest_ip TEXT,
            tls_avg_handshake REAL,
            tls_protocol TEXT,
            dns_avg_resolution REAL,
            mtr_avg_hops REAL,
            mtr_avg_latency REAL,
            sample_count INTEGER,
            sample_start TEXT,
            sample_end TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_current INTEGER DEFAULT 1,
            UNIQUE(region, domain, baseline_version)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS baseline_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            baseline_id INTEGER REFERENCES probe_baseline(id),
            previous_baseline_id INTEGER,
            changed_fields TEXT,
            change_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_metrics_region_domain
        ON probe_metrics(region, domain)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_metrics_timestamp
        ON probe_metrics(probe_timestamp)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_baseline_current
        ON probe_baseline(region, domain, is_current)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_raw_region_type
        ON raw_files(region, file_type)
    """)

    conn.commit()
    conn.close()
