import logging
from datetime import datetime, timedelta
from fastmcp import FastMCP

# 配置日志
logger = logging.getLogger(__name__)

# 常量定义
RECIPIENTS = ["李王昊"]
CC_LIST = [
    "潘处",
    "毅总",
    "许祎恒",
    "霍乾",
    "黄美华",
    "王亮",
    "一线",
    "二线",
    "值班经理",
    "商务",
]


def _parse_bw(bw_str: str) -> int:
    """从带宽字符串提取数值"""
    try:
        if isinstance(bw_str, int):
            return bw_str
        # 简单处理：移除单位，只提取数值，假设单位是Mbps
        import re

        nums = re.findall(r"\d+", str(bw_str))
        return int(nums[0]) if nums else 0
    except Exception:
        return 0


def _effective_date() -> str:
    """返回当前+15天的日期字符串"""
    return (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d")


def _render_scale_up(line_info: dict, assessment: dict) -> dict:
    """常态化扩容申请"""
    date_str = _effective_date()
    bw_num = _parse_bw(line_info.get("bandwidth", "0"))
    traffic = assessment.get("current_traffic_mbps", 0)
    utilization = (traffic / bw_num * 100) if bw_num > 0 else 0

    subject = f"【专线扩容-常态化扩容申请】- {date_str}"
    body = f"""
## 申请摘要
根据近期流量监控，{line_info.get("local_site")}至{line_info.get("remote_name")}专线负载持续偏高，申请常态化扩容。

## 专线调整详情表
| 项目 | 内容 |
| :--- | :--- |
| 线路名称 | {line_info.get("local_site")} - {line_info.get("remote_name")} |
| 专线编号 | {line_info.get("local_line_number")} |
| 当前带宽 | {line_info.get("bandwidth")} |
| 建议带宽 | {assessment.get("target_bw")} |

## 评估结果与原因
{assessment.get("reasoning")}
当前利用率约为 {utilization:.2f}%。

## 流量监控数据
当前流量: {traffic} Mbps
"""
    return {
        "subject": subject,
        "recipients": RECIPIENTS,
        "cc": CC_LIST,
        "body": body,
        "attachments": [],
    }


def _render_scale_down(line_info: dict, assessment: dict) -> dict:
    """缩容申请"""
    date_str = _effective_date()
    target_bw = _parse_bw(assessment.get("target_bw", "0"))
    threshold = target_bw * 0.35

    subject = f"【专线缩容-带宽缩容申请】{line_info.get('local_site')} - {date_str}"
    body = f"""
## 申请摘要
监测到{line_info.get("local_site")}专线利用率长期偏低，建议进行缩容以优化成本。

## 专线调整详情表
| 项目 | 内容 |
| :--- | :--- |
| 线路名称 | {line_info.get("local_site")} - {line_info.get("remote_name")} |
| 当前带宽 | {line_info.get("bandwidth")} |
| 建议带宽 | {assessment.get("target_bw")} |

## 评估结果与合规性
{assessment.get("reasoning")}
缩容阈值参考 (建议带宽 * 0.35): {threshold:.2f} Mbps。
"""
    return {
        "subject": subject,
        "recipients": RECIPIENTS,
        "cc": CC_LIST,
        "body": body,
        "template_type": "scale_down",
    }


def _render_temporary(line_info: dict, assessment: dict) -> dict:
    """临时扩容申请"""
    date_str = _effective_date()
    subject = f"【专线扩容-临时扩容申请】活动保障 - {date_str}"
    body = f"""
## 重大活动保障理由
申请临时扩容以保障重点活动期间的网络稳定性。

## 专线调整详情表
| 项目 | 内容 |
| :--- | :--- |
| 线路名称 | {line_info.get("local_site")} - {line_info.get("remote_name")} |
| 申请带宽 | {assessment.get("target_bw")} |
"""
    return {
        "subject": subject,
        "recipients": RECIPIENTS,
        "cc": CC_LIST,
        "body": body,
        "template_type": "temporary",
    }


def _render_emergency(line_info: dict, assessment: dict) -> dict:
    """应急扩容"""
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    subject = f"【专线扩容-紧急扩容通知】{line_info.get('local_site')} 突发高负载告警 - {date_str} {time_str}"
    body = f"""
## 紧急事态
检测到线路{line_info.get("local_site")}发生突发高负载告警，当前流量已超出承载范围。

## 专线调整详情表
| 项目 | 内容 |
| :--- | :--- |
| 线路名称 | {line_info.get("local_site")} - {line_info.get("remote_name")} |
| 当前流量 | {assessment.get("current_traffic_mbps")} Mbps |
| 应急带宽 | {assessment.get("target_bw")} |

## 故障分析与处置
{assessment.get("reasoning")}
"""
    return {
        "subject": subject,
        "recipients": RECIPIENTS,
        "cc": CC_LIST,
        "body": body,
        "template_type": "emergency",
    }


def register(mcp: FastMCP):
    @mcp.tool()
    def email_generate(
        action: str, line_info: dict, assessment: dict, template_type: str = "normal"
    ) -> dict:
        """根据带宽评估结果生成邮件草稿。支持4种模板。"""
        logger.info(f"Generating email draft for {action} with type {template_type}")

        if action == "scale_up":
            if template_type == "temporary":
                return _render_temporary(line_info, assessment)
            elif template_type == "emergency":
                return _render_emergency(line_info, assessment)
            else:
                return _render_scale_up(line_info, assessment)
        elif action == "scale_down":
            return _render_scale_down(line_info, assessment)
        else:
            return {"message": f"action={action} 不需要生成邮件"}
