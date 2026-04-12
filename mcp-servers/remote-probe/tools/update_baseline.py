import json
import logging
from datetime import datetime

from config import get_config
from db.database import get_connection, init_db
from db.models import (
    get_recent_metrics,
    get_current_baseline,
    insert_baseline,
    deactivate_old_baselines,
    insert_baseline_history,
)

logger = logging.getLogger(__name__)

COMPARE_FIELDS = [
    "avg_rtt_ms",
    "min_rtt_ms",
    "max_rtt_ms",
    "packet_loss_pct",
    "tcp_connect_ms",
    "tls_handshake_ms",
    "dns_resolution_ms",
    "mtr_hops",
    "mtr_avg_latency",
]

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


def _weighted_avg(
    metrics: list[dict], field: str, weight_recent: float
) -> float | None:
    values = [
        (m[field], i)
        for i, m in enumerate(reversed(metrics))
        if m.get(field) is not None
    ]
    if not values:
        return None
    n = len(values)
    recent_count = n // 2
    weights = []
    for _, i in values:
        if i < recent_count:
            weights.append(weight_recent / recent_count if recent_count > 0 else 1.0)
        else:
            weights.append(
                (1 - weight_recent) / (n - recent_count)
                if (n - recent_count) > 0
                else 1.0
            )
    total_weight = sum(weights)
    if total_weight == 0:
        return None
    return round(sum(v * w for (v, _), w in zip(values, weights)) / total_weight, 3)


def update_baseline_impl(
    region: str, domain: str, window_size: int = 30, weight_recent: float = 0.7
) -> dict:
    """Core logic for dynamic baseline update with weighted sliding window."""
    cfg = get_config()
    init_db(cfg.sqlite.db_path)
    conn = get_connection(cfg.sqlite.db_path)

    old_baseline = get_current_baseline(conn, region, domain)
    metrics = get_recent_metrics(conn, region, domain, window_size)

    if not metrics:
        conn.close()
        return {"error": f"no metrics for {region}/{domain}"}

    new_values = {}
    for field in COMPARE_FIELDS:
        new_values[FIELD_MAP[field]] = _weighted_avg(metrics, field, weight_recent)

    fastest_ips = [m["fastest_ip"] for m in metrics if m.get("fastest_ip")]
    new_values["tcp_fastest_ip"] = (
        max(set(fastest_ips), key=fastest_ips.count) if fastest_ips else None
    )

    tls_protocols = [m["tls_protocol"] for m in metrics if m.get("tls_protocol")]
    new_values["tls_protocol"] = (
        max(set(tls_protocols), key=tls_protocols.count) if tls_protocols else None
    )

    changed = {}
    old_id = None
    if old_baseline:
        old_id = old_baseline["id"]
        for field in COMPARE_FIELDS:
            bl_col = FIELD_MAP[field]
            old_val = old_baseline.get(bl_col)
            new_val = new_values.get(bl_col)
            if old_val is not None and new_val is not None:
                pct = abs(new_val - old_val) / old_val * 100 if old_val != 0 else 0
                if pct > 5:
                    changed[field] = {
                        "old": old_val,
                        "new": new_val,
                        "change_pct": round(pct, 2),
                    }

    new_baseline = {
        "region": region,
        "domain": domain,
        "baseline_version": f"v1_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "sample_count": len(metrics),
        "sample_start": metrics[-1]["probe_timestamp"],
        "sample_end": metrics[0]["probe_timestamp"],
    }
    new_baseline.update(new_values)

    deactivate_old_baselines(conn, region, domain)
    bid = insert_baseline(conn, new_baseline)

    if changed:
        insert_baseline_history(
            conn,
            bid,
            old_id,
            json.dumps(changed, ensure_ascii=False),
            f"auto update: {len(changed)} fields changed >5%",
        )

    conn.close()
    return {
        "status": "updated",
        "new_baseline_id": bid,
        "sample_count": len(metrics),
        "changed_fields": changed if changed else "no significant changes",
    }


def register(mcp):
    @mcp.tool()
    def update_baseline(
        region: str, domain: str, window_size: int = 30, weight_recent: float = 0.7
    ) -> dict:
        """动态更新基线。使用滑动窗口加权平均，近期数据权重更高。
        自动记录变更历史。

        Args:
            region: 节点代码
            domain: 探测目标域名（含端口）
            window_size: 滑动窗口大小，默认30个样本
            weight_recent: 近期数据权重，默认0.7（70%）

        Returns:
            dict: 新旧基线对比和变更详情
        """
        return update_baseline_impl(region, domain, window_size, weight_recent)
