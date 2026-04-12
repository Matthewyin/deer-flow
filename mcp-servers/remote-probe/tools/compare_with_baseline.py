import logging
from datetime import datetime, timedelta
from typing import Optional

from config import get_config
from db.database import get_connection, init_db
from db.models import get_metrics_since, get_current_baseline, get_all_region_domains

logger = logging.getLogger(__name__)

THRESHOLDS = {
    "avg_rtt_ms": {"warning": 0.30, "critical": 0.50},
    "packet_loss_pct": {"warning": 0.5, "critical": 1.0, "absolute": True},
    "tcp_connect_ms": {"warning": 0.30, "critical": 0.50},
    "tls_handshake_ms": {"warning": 0.30, "critical": 0.50},
    "dns_resolution_ms": {"warning": 0.30, "critical": 0.50},
}

BASELINE_COL = {
    "avg_rtt_ms": "icmp_avg_rtt",
    "packet_loss_pct": "icmp_packet_loss",
    "tcp_connect_ms": "tcp_avg_connect",
    "tls_handshake_ms": "tls_avg_handshake",
    "dns_resolution_ms": "dns_avg_resolution",
    "mtr_hops": "mtr_avg_hops",
}


def _classify(field: str, current: float, baseline: float) -> str:
    thresh = THRESHOLDS.get(field)
    if not thresh:
        return "normal"

    if thresh.get("absolute"):
        if current >= thresh["critical"]:
            return "CRITICAL"
        if current >= thresh["warning"]:
            return "WARNING"
        return "normal"

    if baseline == 0:
        return "normal"
    deviation = abs(current - baseline) / baseline

    if deviation >= thresh["critical"]:
        return "CRITICAL"
    if deviation >= thresh["warning"]:
        return "WARNING"
    return "normal"


def compare_with_baseline_impl(
    region: Optional[str] = None, domain: Optional[str] = None, hours: int = 6
) -> dict:
    """Core logic for comparing recent metrics against baseline."""
    cfg = get_config()
    init_db(cfg.sqlite.db_path)
    conn = get_connection(cfg.sqlite.db_path)

    since = (datetime.now() - timedelta(hours=hours)).isoformat()

    pairs = []
    if region and domain:
        pairs = [(region, domain)]
    elif region:
        all_pairs = get_all_region_domains(conn)
        pairs = [(r, d) for r, d in all_pairs if r == region]
    else:
        pairs = get_all_region_domains(conn)

    results = {}
    for r, d in pairs:
        baseline = get_current_baseline(conn, r, d)
        if not baseline:
            results[f"{r}/{d}"] = {"status": "no_baseline"}
            continue

        metrics = get_metrics_since(conn, r, d, since)
        if not metrics:
            results[f"{r}/{d}"] = {"status": "no_recent_data"}
            continue

        deviations = {}
        alerts = []
        for field in [
            "avg_rtt_ms",
            "packet_loss_pct",
            "tcp_connect_ms",
            "tls_handshake_ms",
            "dns_resolution_ms",
        ]:
            bl = baseline.get(BASELINE_COL.get(field, field))
            if bl is None:
                continue

            values = [m[field] for m in metrics if m.get(field) is not None]
            if not values:
                continue

            current_avg = round(sum(values) / len(values), 3)
            deviation_pct = round(abs(current_avg - bl) / bl * 100, 2) if bl != 0 else 0
            severity = _classify(field, current_avg, bl)

            deviations[field] = {
                "baseline": bl,
                "current_avg": current_avg,
                "deviation_pct": deviation_pct,
                "severity": severity,
                "sample_count": len(values),
            }
            if severity != "normal":
                alerts.append(f"{field}: {severity} ({deviation_pct}%)")

        mtr_hops_bl = baseline.get("mtr_avg_hops")
        mtr_hops_now = [m["mtr_hops"] for m in metrics if m.get("mtr_hops") is not None]
        if mtr_hops_bl and mtr_hops_now:
            avg_hops = round(sum(mtr_hops_now) / len(mtr_hops_now), 1)
            if avg_hops != mtr_hops_bl:
                deviations["mtr_hops"] = {
                    "baseline": mtr_hops_bl,
                    "current_avg": avg_hops,
                    "change": "hops changed",
                    "severity": "WARNING",
                }
                alerts.append(
                    f"mtr_hops: WARNING (baseline={mtr_hops_bl}, current={avg_hops})"
                )

        results[f"{r}/{d}"] = {
            "status": "compared",
            "metric_count": len(metrics),
            "deviations": deviations,
            "alerts": alerts if alerts else ["all metrics within baseline"],
        }

    conn.close()
    return results


def register(mcp):
    @mcp.tool()
    def compare_with_baseline(
        region: Optional[str] = None, domain: Optional[str] = None, hours: int = 6
    ) -> dict:
        """将近期探测指标与基线进行偏差分析。计算各指标的偏差百分比，
        按阈值标记为 WARNING（>30%）或 CRITICAL（>50%）。

        Args:
            region: 节点代码，为空则分析全部
            domain: 探测目标域名，为空则分析全部
            hours: 回溯小时数，默认6小时

        Returns:
            dict: 各region+domain的对比结果，包含偏差和严重级别
        """
        return compare_with_baseline_impl(region, domain, hours)
