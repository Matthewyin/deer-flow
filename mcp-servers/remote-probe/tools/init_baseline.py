import logging
from datetime import datetime

from config import get_config
from db.database import get_connection, init_db
from db.models import (
    get_recent_metrics,
    get_current_baseline,
    insert_baseline,
    deactivate_old_baselines,
)

logger = logging.getLogger(__name__)

# metric field name → baseline DB column name
FIELD_MAP = {
    "avg_rtt_ms": "icmp_avg_rtt",
    "min_rtt_ms": "icmp_min_rtt",
    "max_rtt_ms": "icmp_max_rtt",
    "packet_loss_pct": "icmp_packet_loss",
    "tcp_connect_ms": "tcp_avg_connect",
    "tls_handshake_ms": "tls_avg_handshake",
    "dns_resolution_ms": "dns_avg_resolution",
    "mtr_hops": "mtr_avg_hops",
    "mtr_avg_latency": "mtr_avg_latency",
}

METRIC_FIELDS = list(FIELD_MAP.keys())


def _avg(metrics: list[dict], field: str) -> float | None:
    values = [m[field] for m in metrics if m.get(field) is not None]
    return round(sum(values) / len(values), 3) if values else None


def init_baseline_impl(region: str, domain: str, sample_count: int = 10) -> dict:
    """Core logic for initializing a baseline from recent metrics."""
    cfg = get_config()
    init_db(cfg.sqlite.db_path)
    conn = get_connection(cfg.sqlite.db_path)

    metrics = get_recent_metrics(conn, region, domain, sample_count)
    if not metrics:
        conn.close()
        return {"error": f"no metrics found for {region}/{domain}"}

    baseline = {
        "region": region,
        "domain": domain,
        "baseline_version": f"v1_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "sample_count": len(metrics),
        "sample_start": metrics[-1]["probe_timestamp"],
        "sample_end": metrics[0]["probe_timestamp"],
    }

    for metric_field, baseline_col in FIELD_MAP.items():
        baseline[baseline_col] = _avg(metrics, metric_field)

    fastest_ips = [m["fastest_ip"] for m in metrics if m.get("fastest_ip")]
    baseline["tcp_fastest_ip"] = (
        max(set(fastest_ips), key=fastest_ips.count) if fastest_ips else None
    )

    tls_protocols = [m["tls_protocol"] for m in metrics if m.get("tls_protocol")]
    baseline["tls_protocol"] = (
        max(set(tls_protocols), key=tls_protocols.count) if tls_protocols else None
    )

    deactivate_old_baselines(conn, region, domain)
    bid = insert_baseline(conn, baseline)
    baseline["id"] = bid
    baseline["status"] = "initialized"

    conn.close()
    return baseline


def register(mcp):
    @mcp.tool()
    def init_baseline(region: str, domain: str, sample_count: int = 10) -> dict:
        """初始化指定region+domain的基线。取最近N次探测指标的算术平均值作为基线。

        Args:
            region: 节点代码（hhht/wh/hz/wlcb/qd/cd）
            domain: 探测目标域名（含端口）
            sample_count: 采样数量，默认取最近10次

        Returns:
            dict: 初始化后的基线数据，包含各项指标平均值
        """
        return init_baseline_impl(region, domain, sample_count)
