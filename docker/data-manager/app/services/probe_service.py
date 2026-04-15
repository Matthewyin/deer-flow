import json
import logging
import os
import sys
from pathlib import Path
from datetime import datetime

REMOTE_PROBE_DIR = "/app/mcp-servers/remote-probe"
for p in [REMOTE_PROBE_DIR, f"{REMOTE_PROBE_DIR}/tools", f"{REMOTE_PROBE_DIR}/db"]:
    if p not in sys.path:
        sys.path.insert(0, p)

LOG_PATH = "/app/.deer-flow/probe/collection_log.json"
INGEST_LOG_PATH = "/app/.deer-flow/probe/ingest_log.json"

logger = logging.getLogger("data-manager")


def _load_log() -> list[dict]:
    if not os.path.exists(LOG_PATH):
        return []
    try:
        with open(LOG_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_log(logs: list[dict]):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


def _load_ingest_log() -> list[dict]:
    if not os.path.exists(INGEST_LOG_PATH):
        return []
    try:
        with open(INGEST_LOG_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_ingest_log(logs: list[dict]):
    os.makedirs(os.path.dirname(INGEST_LOG_PATH), exist_ok=True)
    with open(INGEST_LOG_PATH, "w") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


def save_collection_log(entry: dict):
    logs = _load_log()
    logs.append(entry)
    _save_log(logs)


def collect_probe_data(regions=None) -> dict:
    from collect_probe_data import collect_probe_data_impl

    return collect_probe_data_impl(regions)


def _extract_metric(region: str, data: dict, json_path: str) -> dict | None:
    """Extract a single probe_metrics row from one JSON diagnosis result."""
    domain = data.get("domain")
    target_ip = data.get("target_ip")
    timestamp = data.get("timestamp")
    if not domain or not target_ip or not timestamp:
        return None

    # --- ICMP (from multi_ip_icmp summary, fallback to per-IP) ---
    avg_rtt = min_rtt = max_rtt = None
    packet_loss = None
    multi_icmp = data.get("multi_ip_icmp", {})
    icmp_summary = multi_icmp.get("summary", {})
    if icmp_summary:
        avg_rtt = icmp_summary.get("avg_rtt_ms")
        min_rtt = icmp_summary.get("min_rtt_ms")
        max_rtt = icmp_summary.get("max_rtt_ms")
        packet_loss = icmp_summary.get("avg_packet_loss_percent")

    # --- TCP (from multi_ip_tcp summary) ---
    tcp_connect = None
    fastest_ip = None
    recommended_ip = None
    multi_tcp = data.get("multi_ip_tcp", {})
    tcp_summary = multi_tcp.get("summary", {})
    if tcp_summary:
        tcp_connect = tcp_summary.get("fastest_connection_time_ms")
        fastest_ip = tcp_summary.get("fastest_connection_ip")
        recommended_ip = fastest_ip

    # --- TLS ---
    tls_handshake = None
    tls_protocol = None
    mutual_tls = 0
    tls_info = data.get("tls_info", {})
    if tls_info:
        tls_handshake = tls_info.get("handshake_time_ms")
        tls_protocol = tls_info.get("protocol_version")
        mt = tls_info.get("mutual_tls_info", {})
        if mt and mt.get("is_mutual_tls"):
            mutual_tls = 1

    # --- DNS ---
    dns_resolution_ms = None
    resolved_ips = None
    dns = data.get("dns_resolution", {})
    if dns:
        dns_resolution_ms = dns.get("resolution_time_ms")
        ips = dns.get("resolved_ips")
        if ips:
            resolved_ips = ",".join(ips)

    # --- MTR / Network Path ---
    mtr_hops = None
    mtr_avg_latency = None
    mtr_common_hops = None
    net_path = data.get("multi_ip_network_path", {})
    path_summary = net_path.get("summary", {})
    if path_summary:
        mtr_hops = path_summary.get("avg_hops")
        mtr_avg_latency = path_summary.get("avg_latency_ms")

    return {
        "region": region,
        "domain": domain,
        "target_ip": target_ip,
        "probe_timestamp": timestamp,
        "avg_rtt_ms": avg_rtt,
        "min_rtt_ms": min_rtt,
        "max_rtt_ms": max_rtt,
        "packet_loss_pct": packet_loss,
        "tcp_connect_ms": tcp_connect,
        "fastest_ip": fastest_ip,
        "recommended_ip": recommended_ip,
        "tls_handshake_ms": tls_handshake,
        "tls_protocol": tls_protocol,
        "mutual_tls": mutual_tls,
        "dns_resolution_ms": dns_resolution_ms,
        "resolved_ips": resolved_ips,
        "mtr_hops": mtr_hops,
        "mtr_avg_latency": mtr_avg_latency,
        "mtr_common_hops": mtr_common_hops,
        "raw_json_path": json_path,
    }


def parse_and_ingest_probe_data() -> dict:
    """
    Scan all region directories for JSON files, parse them, and insert
    into probe_metrics. Returns a summary dict.
    """
    from config import get_config
    from database import get_connection, init_db
    from models import insert_probe_metric

    cfg = get_config()
    db_path = os.environ.get("PROBE_DB_PATH", "/app/.deer-flow/db/remote_probe.db")
    raw_base = Path(cfg.probe.local_raw_dir)

    init_db(db_path)
    conn = get_connection(db_path)

    ingested = {
        row["raw_json_path"]
        for row in conn.execute(
            "SELECT raw_json_path FROM probe_metrics WHERE raw_json_path IS NOT NULL"
        ).fetchall()
        if row["raw_json_path"]
    }
    conn.close()

    total_parsed = 0
    total_inserted = 0
    total_skipped = 0
    errors = []

    if not raw_base.exists():
        return {"error": f"raw dir not found: {raw_base}"}

    for region_dir in sorted(raw_base.iterdir()):
        if not region_dir.is_dir():
            continue
        region = region_dir.name

        domain_dir = region_dir / "domain_based"
        if not domain_dir.exists():
            json_files = sorted(region_dir.glob("*.json"))
        else:
            json_files = sorted(domain_dir.glob("*.json"))

        for jf in json_files:
            rel_path = str(jf.relative_to(raw_base))
            if rel_path in ingested:
                total_skipped += 1
                continue

            try:
                with open(jf, "r", encoding="utf-8") as f:
                    data = json.load(f)

                metric = _extract_metric(region, data, rel_path)
                if metric is None:
                    total_skipped += 1
                    continue

                total_parsed += 1
                conn = get_connection(db_path)
                try:
                    if insert_probe_metric(conn, metric):
                        total_inserted += 1
                finally:
                    conn.close()

            except Exception as e:
                errors.append(f"{rel_path}: {e}")
                logger.warning(f"Failed to parse {rel_path}: {e}")

    result = {
        "total_parsed": total_parsed,
        "total_inserted": total_inserted,
        "total_skipped": total_skipped,
        "errors": errors[:20],
    }

    log_entry = {
        "time": datetime.now().isoformat(),
        **result,
    }
    logs = _load_ingest_log()
    logs.append(log_entry)
    _save_ingest_log(logs)

    logger.info(
        f"Probe ingest done: {total_inserted} inserted, "
        f"{total_skipped} skipped, {len(errors)} errors"
    )
    return result


def get_ingest_history(limit: int = 20) -> list[dict]:
    logs = _load_ingest_log()
    return logs[-limit:]


def get_status() -> dict:
    from config import get_config

    cfg = get_config()

    logs = _load_log()
    last_collection = logs[-1] if logs else None

    ingest_logs = _load_ingest_log()
    last_ingest = ingest_logs[-1] if ingest_logs else None

    regions_info = []
    for name, info in cfg.probe.nodes.items():
        raw_dir = Path(cfg.probe.local_raw_dir) / name
        file_count = 0
        if raw_dir.exists():
            file_count = sum(1 for _ in raw_dir.rglob("*") if _.is_file())
        regions_info.append(
            {
                "name": name,
                "city": info.get("city", name),
                "file_count": file_count,
            }
        )

    return {
        "scheduler_running": False,
        "next_run": None,
        "last_collection": last_collection,
        "last_ingest": last_ingest,
        "regions": regions_info,
    }


def get_history(limit: int = 20) -> list[dict]:
    logs = _load_log()
    return logs[-limit:]
