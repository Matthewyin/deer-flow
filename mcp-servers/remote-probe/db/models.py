import sqlite3
from typing import Optional


def insert_raw_file(
    conn, region: str, filename: str, file_type: str, file_size: int, file_hash: str
) -> bool:
    cursor = conn.execute(
        "INSERT OR IGNORE INTO raw_files (region, filename, file_type, file_size, file_hash) "
        "VALUES (?, ?, ?, ?, ?)",
        (region, filename, file_type, file_size, file_hash),
    )
    return cursor.rowcount > 0


def get_collected_files(conn, region: str, file_type: str) -> list[str]:
    rows = conn.execute(
        "SELECT filename FROM raw_files WHERE region = ? AND file_type = ?",
        (region, file_type),
    ).fetchall()
    return [r["filename"] for r in rows]


def insert_probe_metric(conn, m: dict) -> bool:
    keys = [
        "region",
        "domain",
        "target_ip",
        "probe_timestamp",
        "avg_rtt_ms",
        "min_rtt_ms",
        "max_rtt_ms",
        "packet_loss_pct",
        "tcp_connect_ms",
        "fastest_ip",
        "recommended_ip",
        "tls_handshake_ms",
        "tls_protocol",
        "mutual_tls",
        "dns_resolution_ms",
        "resolved_ips",
        "mtr_hops",
        "mtr_avg_latency",
        "mtr_common_hops",
        "raw_json_path",
    ]
    values = [m.get(k) for k in keys]
    placeholders = ", ".join(["?"] * len(keys))
    cols = ", ".join(keys)
    cursor = conn.execute(
        f"INSERT OR REPLACE INTO probe_metrics ({cols}) VALUES ({placeholders})",
        values,
    )
    conn.commit()
    return cursor.rowcount > 0


def get_recent_metrics(conn, region: str, domain: str, limit: int = 30) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM probe_metrics WHERE region = ? AND domain = ? "
        "ORDER BY probe_timestamp DESC LIMIT ?",
        (region, domain, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_metrics_since(
    conn, region: str, domain: Optional[str], since: str
) -> list[dict]:
    if domain:
        rows = conn.execute(
            "SELECT * FROM probe_metrics WHERE region = ? AND domain = ? "
            "AND probe_timestamp >= ? ORDER BY probe_timestamp DESC",
            (region, domain, since),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM probe_metrics WHERE region = ? "
            "AND probe_timestamp >= ? ORDER BY probe_timestamp DESC",
            (region, since),
        ).fetchall()
    return [dict(r) for r in rows]


def get_current_baseline(conn, region: str, domain: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM probe_baseline WHERE region = ? AND domain = ? AND is_current = 1",
        (region, domain),
    ).fetchone()
    return dict(row) if row else None


def insert_baseline(conn, b: dict) -> int:
    keys = [
        "region",
        "domain",
        "baseline_version",
        "icmp_avg_rtt",
        "icmp_max_rtt",
        "icmp_min_rtt",
        "icmp_packet_loss",
        "tcp_avg_connect",
        "tcp_fastest_ip",
        "tls_avg_handshake",
        "tls_protocol",
        "dns_avg_resolution",
        "mtr_avg_hops",
        "mtr_avg_latency",
        "sample_count",
        "sample_start",
        "sample_end",
    ]
    values = [b.get(k) for k in keys]
    placeholders = ", ".join(["?"] * len(keys))
    cols = ", ".join(keys)
    cursor = conn.execute(
        f"INSERT INTO probe_baseline ({cols}) VALUES ({placeholders})",
        values,
    )
    conn.commit()
    return cursor.lastrowid


def deactivate_old_baselines(conn, region: str, domain: str) -> int:
    cursor = conn.execute(
        "UPDATE probe_baseline SET is_current = 0 "
        "WHERE region = ? AND domain = ? AND is_current = 1",
        (region, domain),
    )
    conn.commit()
    return cursor.rowcount


def insert_baseline_history(
    conn, baseline_id: int, prev_id: Optional[int], changed_fields: str, reason: str
) -> int:
    cursor = conn.execute(
        "INSERT INTO baseline_history (baseline_id, previous_baseline_id, changed_fields, change_reason) "
        "VALUES (?, ?, ?, ?)",
        (baseline_id, prev_id, changed_fields, reason),
    )
    conn.commit()
    return cursor.lastrowid


def get_all_region_domains(conn) -> list[tuple[str, str]]:
    rows = conn.execute("SELECT DISTINCT region, domain FROM probe_metrics").fetchall()
    return [(r["region"], r["domain"]) for r in rows]


def get_metric_count(conn, region: str, domain: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM probe_metrics WHERE region = ? AND domain = ?",
        (region, domain),
    ).fetchone()
    return row["cnt"] if row else 0


def get_uningested_file_count(conn, region: str) -> int:
    """Return count of uningested raw files for a given region."""
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM raw_files WHERE region = ? AND ingested = 0",
        (region,),
    ).fetchone()
    return row["cnt"] if row else 0


def mark_raw_files_ingested(conn, region: str) -> int:
    """Mark all uningested raw files for a region as ingested. Returns count updated."""
    from datetime import datetime

    now = datetime.now().isoformat()
    cursor = conn.execute(
        "UPDATE raw_files SET ingested = 1, ingested_at = ? WHERE region = ? AND ingested = 0",
        (now, region),
    )
    conn.commit()
    return cursor.rowcount


def get_latest_metric_timestamp(conn, region: str) -> Optional[str]:
    """Return the most recent probe_timestamp for a region, or None."""
    row = conn.execute(
        "SELECT MAX(probe_timestamp) as ts FROM probe_metrics WHERE region = ?",
        (region,),
    ).fetchone()
    return row["ts"] if row and row["ts"] else None
