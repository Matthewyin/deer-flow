"""带宽检查与报告生成 MCP 工具。

实现 bandwidth_check（P95 指标计算与扩缩容规则判定）和
bandwidth_report（根据检查结果生成邮件内容）两个工具。
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from fastmcp import FastMCP

from config import get_config
from db.bandwidth_lines_client import BandwidthLinesClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 单例模式 — BandwidthLinesClient
# ---------------------------------------------------------------------------

_client: Optional[BandwidthLinesClient] = None

TIERS = [2, 4, 6, 8, 10, 20, 30, 40, 50]
_EXPANSION_UTIL_THRESHOLD = 40.0
_SHRINKAGE_TRAFFIC_RATIO = 0.35


def _get_client() -> BandwidthLinesClient:
    """获取 BandwidthLinesClient 单例。"""
    global _client
    if _client is None:
        config = get_config()
        db_path = os.environ.get(
            "BANDWIDTH_DB_PATH",
            config.sqlite.db_path,
        )
        _client = BandwidthLinesClient(db_path)
    return _client


# ---------------------------------------------------------------------------
# P95 计算
# ---------------------------------------------------------------------------


def _p95(values: list[float]) -> float:
    """计算 95 百分位，使用线性插值。"""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    k = 0.95 * (n - 1)
    f = int(k)
    c = k - f
    if f + 1 < n:
        return sorted_vals[f] + c * (sorted_vals[f + 1] - sorted_vals[f])
    return sorted_vals[f]


# ---------------------------------------------------------------------------
# 带宽档位规则
# ---------------------------------------------------------------------------


def _find_tier_index(bw_mbps: int) -> int:
    """查找当前带宽在 TIERS 中的下标，-1 表示未找到。"""
    for i, t in enumerate(TIERS):
        if t == bw_mbps:
            return i
    return -1


def _expansion_target(current_bw: int) -> Optional[int]:
    """扩容目标带宽：当前档位的下一档。"""
    idx = _find_tier_index(current_bw)
    if idx >= 0 and idx + 1 < len(TIERS):
        return TIERS[idx + 1]
    return None  # 已是最高档，无法扩容


def _shrinkage_target(p95_traffic: float, current_bw: int) -> Optional[int]:
    """缩容目标带宽：低于当前档位中，满足 P95 < tier × 35% 的最高档位。

    先检查触发条件：P95 < (当前档位 - 1) × 35%。
    满足后，从当前档位向下找到第一个容纳条件成立的档位。
    """
    idx = _find_tier_index(current_bw)
    if idx <= 0:
        return None  # 最低档位，无法缩容

    # 检查是否触发缩容条件
    next_lower = TIERS[idx - 1]
    if p95_traffic >= next_lower * _SHRINKAGE_TRAFFIC_RATIO:
        return None

    # 找到目标档位：P95 流量低于该档位 × 35% 的最高档位
    for i in range(idx - 1, -1, -1):
        if p95_traffic < TIERS[i] * _SHRINKAGE_TRAFFIC_RATIO:
            return TIERS[i]
    return None


def _assess_line(
    p95_in_util: float,
    p95_out_util: float,
    p95_traffic: float,
    bandwidth_mbps: int,
) -> tuple[str, Optional[int]]:
    """对单条线路执行扩缩容规则判定。

    Returns:
        (action, target_bandwidth): action 为 "expand" / "shrink" / "stable"
    """
    if bandwidth_mbps <= 0:
        return ("stable", None)

    p95_util = max(p95_in_util, p95_out_util)

    # 扩容判定
    if p95_util > _EXPANSION_UTIL_THRESHOLD:
        target = _expansion_target(bandwidth_mbps)
        if target is not None:
            return ("expand", target)

    # 缩容判定
    target = _shrinkage_target(p95_traffic, bandwidth_mbps)
    if target is not None:
        return ("shrink", target)

    return ("stable", None)


# ---------------------------------------------------------------------------
# MCP 工具注册
# ---------------------------------------------------------------------------


def register(mcp: FastMCP):
    @mcp.tool()
    def bandwidth_check(
        days: int = 15,
        start_date: str = "",
        end_date: str = "",
        line_group: str = "",
        long_distance_no: str = "",
    ) -> dict:
        """查询带宽线路数据，计算 P95 指标并应用扩缩容规则。

        Args:
            days: 统计天数，默认 15。仅在未提供 start_date 时生效。
            start_date: 开始日期（YYYY-MM-DD），空则根据 days 自动计算。
            end_date: 结束日期（YYYY-MM-DD），空则取最新可用日期。
            line_group: 线路组过滤，空则不过滤。
            long_distance_no: 线路编号过滤，空则不过滤。

        Returns:
            dict: 包含 period（统计周期）、groups（线路组 × 线路的评估结果）。
        """
        client = _get_client()

        # ── 确定日期范围 ──
        if not start_date or not end_date:
            available_dates = client.get_available_dates()
            if not available_dates:
                return {
                    "error": "数据库中没有线路带宽数据",
                    "period": {"start": "", "end": ""},
                    "groups": [],
                }
            latest = max(available_dates)

            end = end_date if end_date else latest

            if not start_date:
                end_dt = datetime.strptime(end, "%Y-%m-%d")
                start_dt = end_dt - timedelta(days=days - 1)
                start = start_dt.strftime("%Y-%m-%d")
            else:
                start = start_date
        else:
            start, end = start_date, end_date

        # ── 查询数据 ──
        ldn_filter = long_distance_no if long_distance_no else None
        rows = client.get_lines_for_period(start, end, ldn_filter)

        if not rows:
            return {
                "period": {"start": start, "end": end},
                "groups": [],
                "message": "指定期间内无数据",
            }

        # ── 线路组过滤 ──
        if line_group:
            rows = [r for r in rows if r.get("line_group") == line_group]

        if not rows:
            return {
                "period": {"start": start, "end": end},
                "groups": [],
                "message": f"线路组 '{line_group}' 无数据",
            }

        # ── 按 line_group → long_distance_no 分组 ──
        groups_data: dict[str, dict[str, list[dict]]] = {}
        for row in rows:
            lg = row.get("line_group", "未分组")
            ldn = row.get("long_distance_no", "未知")
            groups_data.setdefault(lg, {}).setdefault(ldn, []).append(row)

        # ── 逐线路计算 P95 并评估 ──
        result_groups = []
        for group_name, lines_in_group in groups_data.items():
            group_lines = []
            group_p95_traffic_sum = 0.0

            for ldn, line_rows in lines_in_group.items():
                in_util_vals = [
                    r["in_peak_util_pct"]
                    for r in line_rows
                    if r.get("in_peak_util_pct") is not None
                ]
                out_util_vals = [
                    r["out_peak_util_pct"]
                    for r in line_rows
                    if r.get("out_peak_util_pct") is not None
                ]

                # 每日最大流量（取 in/out 峰值较大者）
                daily_max_traffic = [
                    float(
                        max(
                            r.get("in_peak_mbps") or 0,
                            r.get("out_peak_mbps") or 0,
                        )
                    )
                    for r in line_rows
                ]

                p95_in = _p95(in_util_vals)
                p95_out = _p95(out_util_vals)
                p95_traffic = _p95(daily_max_traffic)

                bandwidth_mbps = line_rows[0].get("bandwidth_mbps") or 0
                action, target_bw = _assess_line(
                    p95_in, p95_out, p95_traffic, int(bandwidth_mbps)
                )

                group_p95_traffic_sum += p95_traffic

                group_lines.append(
                    {
                        "long_distance_no": ldn,
                        "bandwidth_mbps": bandwidth_mbps,
                        "p95_in_util": round(p95_in, 2),
                        "p95_out_util": round(p95_out, 2),
                        "p95_traffic": round(p95_traffic, 2),
                        "action": action,
                        "target_bandwidth": target_bw,
                        "province": line_rows[0].get("province", ""),
                        "carrier": line_rows[0].get("carrier", ""),
                        "usage": line_rows[0].get("usage", ""),
                    }
                )

            result_groups.append(
                {
                    "group_name": group_name,
                    "group_p95_traffic_sum": round(group_p95_traffic_sum, 2),
                    "line_count": len(group_lines),
                    "lines": group_lines,
                }
            )

        return {
            "period": {"start": start, "end": end},
            "total_groups": len(result_groups),
            "groups": result_groups,
        }

    @mcp.tool()
    def bandwidth_report(
        check_result: str,
        report_type: str = "expand",
    ) -> dict:
        """根据 bandwidth_check 结果生成邮件内容。

        Args:
            check_result: bandwidth_check 工具返回的 JSON 字符串。
            report_type: 报告类型，可选 "expand"（常态化扩容）、"emergency"（应急扩容）、"shrink"（缩容）。

        Returns:
            dict: 包含 subject（主题）、to（收件人）、cc（抄送）、body（正文，Markdown 格式）。
        """
        # ── 解析输入 ──
        try:
            data = (
                json.loads(check_result)
                if isinstance(check_result, str)
                else check_result
            )
        except json.JSONDecodeError as e:
            return {"error": f"check_result JSON 解析失败: {e}"}

        if report_type not in ("expand", "emergency", "shrink"):
            return {"error": f"不支持的 report_type: {report_type}"}

        # ── 筛选相关线路 ──
        target_action = "expand" if report_type != "shrink" else "shrink"
        relevant_lines = []
        for group in data.get("groups", []):
            for line in group.get("lines", []):
                if report_type == "emergency" or line.get("action") == target_action:
                    relevant_lines.append(
                        {**line, "group_name": group.get("group_name", "")}
                    )

        if not relevant_lines:
            return {
                "message": f"没有需要生成 {report_type} 报告的线路",
                "subject": "",
                "to": "",
                "cc": "",
                "body": "",
            }

        # ── 公共字段 ──
        now = datetime.now()
        date_str = now.strftime("%Y%m%d")
        time_str = now.strftime("%Y-%m-%d %H:%M")
        effective_date = (now + timedelta(days=15)).strftime("%Y-%m-%d")
        period = data.get("period", {})

        to = "技术处接口人"
        cc = (
            "技术处分管领导、运维分管领导、安全及支援业务线分管领导、"
            "运维部经理、基础架构部经理、运维部副经理、一线、二线、值班经理、商务"
        )

        # ── 构建主题 ──
        if report_type == "expand":
            subject = f"【专线扩容-常态化扩容申请】- {date_str}"
        elif report_type == "emergency":
            line_names = "、".join(
                l["long_distance_no"] for l in relevant_lines[:2]
            )
            subject = f"【专线扩容-紧急扩容通知】{line_names} 突发高负载告警 - {time_str}"
        else:
            line_names = "、".join(
                l["long_distance_no"] for l in relevant_lines[:2]
            )
            subject = f"【专线缩容-带宽缩容申请】{line_names} - {date_str}"

        # ── 构建正文 ──
        body = _build_body(report_type, relevant_lines, period, now, effective_date)

        return {
            "subject": subject,
            "to": to,
            "cc": cc,
            "body": body,
        }


# ---------------------------------------------------------------------------
# 邮件正文构建
# ---------------------------------------------------------------------------


def _build_body(
    report_type: str,
    lines: list[dict],
    period: dict,
    now: datetime,
    effective_date: str,
) -> str:
    """根据带宽模板生成 Markdown 格式邮件正文。"""
    time_str = now.strftime("%Y-%m-%d %H:%M")

    if report_type == "expand":
        return _build_expand_body(lines, period, effective_date)
    elif report_type == "emergency":
        return _build_emergency_body(lines, time_str)
    else:
        return _build_shrink_body(lines, period, effective_date)


def _build_expand_body(
    lines: list[dict],
    period: dict,
    effective_date: str,
) -> str:
    expand_lines = [l for l in lines if l.get("action") == "expand"]
    max_util = (
        max((l.get("p95_in_util", 0) for l in expand_lines), default=0)
        if expand_lines
        else max((l.get("p95_in_util", 0) for l in lines), default=0)
    )

    parts = [
        "各位领导/同事：",
        "",
        "【申请摘要】",
        (
            f"根据《数据中心网络专线带宽扩缩容指南》，以下线路过去15天P95利用率已达"
            f" {max_util:.1f}%（阈值40%），且负载均衡正常。现申请进行带宽扩容，涉及线路如下："
        ),
        "",
        "1. 专线调整详情表",
        "",
        "| 专线号 | 专线名称 | 专线用途 | 运营商 | 现有带宽 | 申请带宽 | 当前P95利用率 | 当前P95流量 | 调整生效日期 |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for line in lines:
        ldn = line.get("long_distance_no", "")
        site = f"{line.get('province', '')}-{line.get('group_name', '')}"
        usage = line.get("usage", "")
        carrier = line.get("carrier", "")
        cur_bw = line.get("bandwidth_mbps", "")
        target_bw = line.get("target_bandwidth") or ""
        p95_util = f"{line.get('p95_in_util', 0):.1f}%"
        p95_traffic = f"{line.get('p95_traffic', 0):.1f} Mbps"
        parts.append(
            f"| {ldn} | {site} | {usage} | {carrier} | {cur_bw} Mbps "
            f"| {target_bw} Mbps | {p95_util} | {p95_traffic} | {effective_date} |"
        )

    parts.extend(
        [
            "",
            "2. 评估结果与原因",
            "",
            "● 触发原因：业务自然增长，统计周期内P95流量持续高于40%。",
            "",
            "3. 流量监控数据（附件图表）",
            "",
            f"统计周期：{period.get('start', '')} 至 {period.get('end', '')}（15个自然日）",
            "",
            "> 图1：最近15天带宽流量趋势图及P95统计",
            "> [在此处粘贴流量监控图片，需清晰显示P95线与40%阈值线]",
        ]
    )

    return "\n".join(parts)


def _build_emergency_body(
    lines: list[dict],
    time_str: str,
) -> str:
    parts = [
        "各位领导/同事：",
        "",
        "【紧急事态】",
        f"{time_str} 监控触发高负载告警，业务已受损。已电话通知运营商，要求2小时内生效。流程后补。",
        "",
        "1. 专线调整详情表",
        "",
        "| 专线号 | 专线名称 | 专线用途 | 运营商 | 现有带宽 | 申请带宽 | 当前实时利用率 | 网络质量状况 | 要求生效时间 |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for line in lines:
        ldn = line.get("long_distance_no", "")
        site = f"{line.get('province', '')}-{line.get('group_name', '')}"
        usage = line.get("usage", "")
        carrier = line.get("carrier", "")
        cur_bw = line.get("bandwidth_mbps", "")
        target_bw = line.get("target_bandwidth") or cur_bw
        p95_util = f"{line.get('p95_in_util', 0):.1f}%"
        parts.append(
            f"| {ldn} | {site} | {usage} | {carrier} | {cur_bw} Mbps "
            f"| {target_bw} Mbps | {p95_util} | 待确认 | 立即生效 |"
        )

    parts.extend(
        [
            "",
            "2. 故障分析与处置",
            "",
            "● 紧急原因：[需人工填写：备线中断/突发攻击流量等]",
            "● 后续处置：扩容后将进入3天观察期，待流量稳定并查明根因后，再评估是否恢复。",
            "",
            "3. 实时告警数据",
            "",
            "> 图1：实时流量监控与丢包/延迟告警截图",
            "> [在此处粘贴实时监控告警图，重点展示高负载时段]",
        ]
    )

    return "\n".join(parts)


def _build_shrink_body(
    lines: list[dict],
    period: dict,
    effective_date: str,
) -> str:
    parts = [
        "各位领导/同事：",
        "",
        "【申请摘要】",
        (
            "以下专线长期低负载。经核算，流量已低于跨级目标带宽的35%，"
            "符合《指南》缩容标准。申请降级以优化成本。"
        ),
        "",
        "1. 专线调整详情表",
        "",
        "| 专线号 | 专线名称 | 专线用途 | 运营商 | 现有带宽 | 申请带宽 | 缩容阈值标准 | 当前P95利用率 | 当前P95流量 | 调整生效日期 |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for line in lines:
        ldn = line.get("long_distance_no", "")
        site = f"{line.get('province', '')}-{line.get('group_name', '')}"
        usage = line.get("usage", "")
        carrier = line.get("carrier", "")
        cur_bw = line.get("bandwidth_mbps", "")
        target_bw = line.get("target_bandwidth") or ""
        p95_util = f"{line.get('p95_in_util', 0):.1f}%"
        p95_traffic = f"{line.get('p95_traffic', 0):.1f} Mbps"

        threshold_str = ""
        if target_bw and isinstance(target_bw, (int, float)):
            threshold_str = f"< {target_bw}×35%={target_bw * 0.35:.1f}Mbps"

        parts.append(
            f"| {ldn} | {site} | {usage} | {carrier} | {cur_bw} Mbps "
            f"| {target_bw} Mbps | {threshold_str} | {p95_util} | {p95_traffic} | {effective_date} |"
        )

    parts.extend(
        [
            "",
            "2. 评估结果与合规性",
            "",
            "● 合规性检查：",
            "  ○ [✓] 流量低于目标带宽的35%。",
            "  ○ [✓] 当前非重大活动保障期，未来一个月无大流量上线计划。",
            "",
            "3. 流量监控数据（附件图表）",
            "",
            f"统计周期：{period.get('start', '')} 至 {period.get('end', '')}（15个自然日）",
            "",
            "> 图1：最近15天带宽流量趋势图（含缩容模拟线）",
            "> [在此处粘贴流量图，建议在图中标注出'缩容后预计水位线'，以证明缩容后利用率处于20%-25%的安全区间]",
        ]
    )

    return "\n".join(parts)
