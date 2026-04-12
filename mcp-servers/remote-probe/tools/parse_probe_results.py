import json
import logging
import os
from typing import Optional

from config import get_config
from db.database import get_connection, init_db
from db.models import insert_probe_metric

logger = logging.getLogger(__name__)


def _extract_metric(filepath: str, region: str) -> dict | None:
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to parse {filepath}: {e}")
        return None

    icmp_summary = data.get("multi_ip_icmp", {}).get("summary", {})
    tcp_summary = data.get("multi_ip_tcp", {}).get("summary", {})
    tls_info = data.get("tls_info", {})
    dns = data.get("dns_resolution", {})
    mtr_summary = data.get("multi_ip_network_path", {}).get("summary", {})

    return {
        "region": region,
        "domain": data.get("domain", ""),
        "target_ip": data.get("target_ip", ""),
        "probe_timestamp": data.get("timestamp", ""),
        "avg_rtt_ms": icmp_summary.get("avg_rtt_ms"),
        "min_rtt_ms": icmp_summary.get("min_rtt_ms"),
        "max_rtt_ms": icmp_summary.get("max_rtt_ms"),
        "packet_loss_pct": icmp_summary.get("overall_packet_loss_percent"),
        "tcp_connect_ms": tcp_summary.get("average_connection_time_ms"),
        "fastest_ip": tcp_summary.get("fastest_connection_ip"),
        "recommended_ip": tcp_summary.get("recommended_ip"),
        "tls_handshake_ms": tls_info.get("handshake_time_ms"),
        "tls_protocol": tls_info.get("protocol_version"),
        "mutual_tls": 1
        if tls_info.get("mutual_tls_info", {}).get("requires_client_cert")
        else 0,
        "dns_resolution_ms": dns.get("resolution_time_ms"),
        "resolved_ips": ",".join(dns.get("resolved_ips", [])),
        "mtr_hops": mtr_summary.get("avg_hops"),
        "mtr_avg_latency": mtr_summary.get("avg_latency_ms"),
        "mtr_common_hops": ",".join(mtr_summary.get("common_hops", [])),
        "raw_json_path": filepath,
    }


def parse_probe_results_impl(regions: Optional[list[str]] = None) -> dict:
    """Core logic for parsing JSON probe results into metrics."""
    cfg = get_config()
    init_db(cfg.sqlite.db_path)
    conn = get_connection(cfg.sqlite.db_path)

    if not regions:
        regions = list(cfg.probe.nodes.keys())

    results = {}
    for region in regions:
        json_dir = os.path.join(cfg.probe.local_raw_dir, region, "domain_based")
        if not os.path.isdir(json_dir):
            results[region] = {
                "parsed": 0,
                "skipped": 0,
                "errors": 0,
                "note": "no data dir",
            }
            continue

        summary = {"parsed": 0, "skipped": 0, "errors": 0}
        for fname in sorted(os.listdir(json_dir)):
            if not fname.endswith(".json"):
                continue
            filepath = os.path.join(json_dir, fname)
            metric = _extract_metric(filepath, region)
            if metric is None:
                summary["errors"] += 1
                continue

            ok = insert_probe_metric(conn, metric)
            if ok:
                summary["parsed"] += 1
            else:
                summary["skipped"] += 1

        results[region] = summary

    tgz_results = {}
    for region in regions:
        tgz_results[region] = {"note": "tgz extraction not yet implemented"}

    conn.close()
    return {"json": results, "tgz": tgz_results}


def register(mcp):
    @mcp.tool()
    def parse_probe_results(regions: Optional[list[str]] = None) -> dict:
        """解析已采集的JSON探测结果，提取ICMP/TCP/TLS/DNS/MTR指标入库。
        自动跳过已解析的文件（通过probe_metrics唯一约束去重）。

        Args:
            regions: 要解析的region列表，为空则解析全部

        Returns:
            dict: 每个region的解析统计 {region: {parsed, skipped, errors}}
        """
        return parse_probe_results_impl(regions)
