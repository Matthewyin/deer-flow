import logging
from fastmcp import FastMCP
from db.sqlite_client import SQLiteClient
from config import get_config

logger = logging.getLogger(__name__)

_db = None


def _get_db():
    global _db
    if _db is None:
        config = get_config()
        _db = SQLiteClient(config.sqlite.db_path)
    return _db


def register(mcp: FastMCP):
    @mcp.tool()
    def bandwidth_assess(current_bw_mbps: int, current_traffic_mbps: float) -> dict:
        """
        根据当前带宽和流量，评估是否需要扩容或缩容。基于带宽策略表（8档：2M/4M/6M/8M/10M/20M/30M/40M），判断当前流量是否超过扩容阈值或低于缩容阈值。

        Args:
            current_bw_mbps: 当前带宽档位（Mbps），如 10 代表 10M
            current_traffic_mbps: 当前 P95 流量（Mbps），如 5.0 代表 5Mbps

        Returns:
            dict: 评估结果字典，包含 action ("scale_up"/"scale_down"/"maintain"), current_bw, target_bw, threshold_mbps, reasoning
        """
        db = _get_db()
        return db.get_recommendation(current_bw_mbps, current_traffic_mbps)
