"""Bandwidth policy tool for DeerFlow.

This tool provides bandwidth policy queries using RAG retrieval.
It answers questions about current bandwidth, traffic levels, and recommended actions.
"""

import logging
from typing import Optional

from pydantic import BaseModel, Field

from deerflow.rag import get_bandwidth_rag

logger = logging.getLogger(__name__)


class BandwidthQueryInput(BaseModel):
    """Input for bandwidth policy query."""

    current_bw: Optional[str] = Field(
        None,
        description="当前带宽档位，例如 '10 Mbps'",
    )
    current_traffic: Optional[float] = Field(
        None,
        description="当前流量 (Mbps)",
    )
    query: Optional[str] = Field(
        None,
        description="自然语言查询，例如 '我当前10M带宽，流量5Mbps，应该怎么办？'",
    )


class BandwidthQueryOutput(BaseModel):
    """Output from bandwidth policy query."""

    action: str = Field(
        ...,
        description="建议操作: scale_up(扩容), scale_down(缩容), maintain(维持)",
    )
    current_bw: Optional[str] = Field(None, description="当前带宽档位")
    current_traffic_mbps: Optional[float] = Field(None, description="当前流量 Mbps")
    target_bw: Optional[str] = Field(None, description="目标带宽档位")
    threshold_mbps: Optional[float] = Field(None, description="触发阈值 Mbps")
    reasoning: str = Field(..., description="操作建议的详细说明")
    relevant_policies: list[dict] = Field(
        default_factory=list,
        description="检索到的相关策略",
    )


async def bandwidth_policy_query(
    current_bw: Optional[str] = None,
    current_traffic: Optional[float] = None,
    query: Optional[str] = None,
) -> BandwidthQueryOutput:
    """查询带宽策略并给出操作建议。

    基于RAG检索带宽策略表，根据当前带宽和流量给出扩容/缩容/维持的建议。

    Args:
        current_bw: 当前带宽档位，例如 "10 Mbps"
        current_traffic: 当前流量 (Mbps)
        query: 自然语言查询（可选，覆盖结构化参数）

    Returns:
        BandwidthQueryOutput 包含操作建议和详细说明

    Examples:
        >>> await bandwidth_policy_query("10 Mbps", 5.0)
        BandwidthQueryOutput(action="scale_up", ...)

        >>> await bandwidth_policy_query(query="当前10M带宽流量3Mbps该怎么办")
        BandwidthQueryOutput(action="maintain", ...)
    """
    rag = get_bandwidth_rag()

    # Parse query if provided
    if query and not (current_bw and current_traffic):
        # Try to extract values from natural language query
        parsed_bw, parsed_traffic = _parse_query(query)
        current_bw = current_bw or parsed_bw
        current_traffic = current_traffic or parsed_traffic

    # If we have both structured params, use RAG recommendation
    if current_bw and current_traffic is not None:
        recommendation = rag.get_recommendation(current_bw, current_traffic)
        relevant_policies = rag.query(
            current_bw=current_bw,
            current_traffic=current_traffic,
            k=2,
        )

        return BandwidthQueryOutput(
            action=recommendation["action"],
            current_bw=recommendation.get("current_bw"),
            current_traffic_mbps=recommendation.get("current_traffic_mbps"),
            target_bw=recommendation.get("target_bw"),
            threshold_mbps=recommendation.get("threshold_mbps"),
            reasoning=recommendation["reasoning"],
            relevant_policies=relevant_policies,
        )

    # Otherwise, just do semantic search
    results = rag.query(
        current_bw=current_bw,
        current_traffic=current_traffic,
        query_text=query,
        k=3,
    )

    if not results:
        return BandwidthQueryOutput(
            action="unknown",
            reasoning="未找到匹配的带宽策略，请提供当前带宽档位（如 '10 Mbps'）和流量数据",
        )

    # Build response from top result
    top = results[0]
    return BandwidthQueryOutput(
        action="info",
        current_bw=current_bw,
        current_traffic_mbps=current_traffic,
        reasoning=f"检索到最相关的带宽策略：{top['description']}",
        relevant_policies=results,
    )


def _parse_query(query: str) -> tuple[Optional[str], Optional[float]]:
    """Parse bandwidth and traffic values from natural language query.

    Handles patterns like:
    - "10M带宽流量5Mbps"
    - "当前10 Mbps，流量3.5"
    - "20兆带宽，8M流量"
    """
    import re

    bw_pattern = r"(\d+)\s*[Mm]?(?:bps|兆|M)"
    traffic_pattern = r"(?:流量|traffic)?[:：]?\s*(\d+\.?\d*)\s*[Mm]?(?:bps|兆|M)?"

    bw_match = re.search(bw_pattern, query)
    traffic_match = re.search(traffic_pattern, query)

    bw = None
    traffic = None

    if bw_match:
        bw_value = int(bw_match.group(1))
        bw = f"{bw_value} Mbps"

    if traffic_match:
        traffic = float(traffic_match.group(1))

    return bw, traffic


# Tool definition for DeerFlow integration
bandwidth_policy_query_tool = {
    "name": "bandwidth_policy_query",
    "description": """查询带宽策略并给出扩容/缩容/维持建议。

基于RAG检索带宽策略表，根据当前带宽档位和流量水平给出操作建议。
支持结构化参数输入或自然语言查询。

使用场景:
- 用户问"当前10M带宽，流量5Mbps应该怎么办"
- 用户问"我现在的带宽够不够用"
- 需要判断是否需要扩容或缩容

返回内容包括:
- action: 建议操作 (scale_up/扩容, scale_down/缩容, maintain/维持)
- target_bw: 目标带宽档位
- reasoning: 详细说明和建议
""",
    "func": bandwidth_policy_query,
    "input_model": BandwidthQueryInput,
    "output_model": BandwidthQueryOutput,
}
