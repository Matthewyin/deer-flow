import os
from datetime import datetime

from config import get_config
from db.database import get_connection, init_db
from db.models import (
    get_all_region_domains,
    get_current_baseline,
    get_metrics_since,
    get_metric_count,
)

BASELINE_COL = {
    "avg_rtt_ms": "icmp_avg_rtt",
    "packet_loss_pct": "icmp_packet_loss",
    "tcp_connect_ms": "tcp_avg_connect",
    "tls_handshake_ms": "tls_avg_handshake",
    "dns_resolution_ms": "dns_avg_resolution",
    "mtr_avg_latency": "mtr_avg_latency",
}


def generate_probe_report_impl(report_type: str = "daily", hours: int = 6) -> str:
    """Core logic for generating probe baseline comparison report in Markdown."""
    cfg = get_config()
    init_db(cfg.sqlite.db_path)
    conn = get_connection(cfg.sqlite.db_path)

    now = datetime.now()
    report_lines = [
        f"# 网络探测基线报告",
        f"",
        f"**生成时间**: {now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**回溯范围**: 最近 {hours} 小时",
        f"**报告类型**: {report_type}",
        f"",
    ]

    pairs = get_all_region_domains(conn)
    if not pairs:
        report_lines.append("> 暂无探测数据，请先执行数据采集和解析。\n")
        conn.close()
        return "\n".join(report_lines)

    alert_count = 0
    critical_count = 0

    for region, domain in sorted(pairs):
        node_info = cfg.probe.nodes.get(region, {})
        city = node_info.get("city", region)

        baseline = get_current_baseline(conn, region, domain)
        metrics = get_metrics_since(
            conn,
            region,
            domain,
            (now - __import__("datetime").timedelta(hours=hours)).isoformat(),
        )
        total_metrics = get_metric_count(conn, region, domain)

        report_lines.append(f"## {city} ({region}) — {domain}")
        report_lines.append("")

        if not baseline:
            report_lines.append(
                f"> ⚠️ 未建立基线（共{total_metrics}条记录），请执行 init_baseline"
            )
            report_lines.append("")
            continue

        if not metrics:
            report_lines.append(
                f"> 近{hours}小时无新数据（基线版本: {baseline['baseline_version']}）"
            )
            report_lines.append("")
            continue

        report_lines.append(f"| 指标 | 基线 | 当前均值 | 偏差 | 状态 |")
        report_lines.append(f"|------|------|----------|------|------|")

        for field, label in [
            ("avg_rtt_ms", "ICMP RTT(ms)"),
            ("packet_loss_pct", "丢包率(%)"),
            ("tcp_connect_ms", "TCP连接(ms)"),
            ("tls_handshake_ms", "TLS握手(ms)"),
            ("dns_resolution_ms", "DNS解析(ms)"),
            ("mtr_avg_latency", "MTR延迟(ms)"),
        ]:
            bl = baseline.get(BASELINE_COL.get(field, field))
            values = [m[field] for m in metrics if m.get(field) is not None]
            if bl is None or not values:
                continue

            avg = round(sum(values) / len(values), 3)
            dev = round(abs(avg - bl) / bl * 100, 1) if bl != 0 else 0

            if field == "packet_loss_pct":
                status = (
                    "🔴 CRITICAL"
                    if avg >= 1.0
                    else ("🟡 WARNING" if avg >= 0.5 else "🟢 正常")
                )
            else:
                status = (
                    "🔴 CRITICAL"
                    if dev >= 50
                    else ("🟡 WARNING" if dev >= 30 else "🟢 正常")
                )

            if "CRITICAL" in status:
                critical_count += 1
                alert_count += 1
            elif "WARNING" in status:
                alert_count += 1

            if report_type == "summary" and "正常" in status:
                continue

            report_lines.append(f"| {label} | {bl} | {avg} | {dev}% | {status} |")

        report_lines.append(
            f"\n> 基线: {baseline['baseline_version']} | "
            f"样本: {baseline['sample_count']} | "
            f"数据: {len(metrics)}/{total_metrics} 条"
        )
        report_lines.append("")

    report_lines.append("---")
    report_lines.append("")
    report_lines.append("## 告警汇总")
    report_lines.append("")
    if alert_count == 0:
        report_lines.append("✅ 所有指标均在基线范围内")
    else:
        report_lines.append(
            f"共 **{alert_count}** 项告警（其中 **{critical_count}** 项严重）"
        )
    report_lines.append("")

    report_content = "\n".join(report_lines)

    report_dir = cfg.probe.local_report_dir
    os.makedirs(report_dir, exist_ok=True)
    filename = f"probe_report_{now.strftime('%Y%m%d_%H%M')}.md"
    filepath = os.path.join(report_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report_content)

    conn.close()
    return report_content


def register(mcp):
    @mcp.tool()
    def generate_probe_report(report_type: str = "daily", hours: int = 6) -> str:
        """生成网络探测基线对比报告（Markdown格式）。包含各节点各目标的
        当前指标、基线对比、偏差百分比和告警汇总。

        Args:
            report_type: 报告类型 - daily（完整报告）或 summary（概览）
            hours: 回溯小时数，默认6小时

        Returns:
            str: Markdown格式的探测报告，同时保存到文件
        """
        return generate_probe_report_impl(report_type, hours)
