from fastmcp import FastMCP

from config import get_config
from core.db import report


def register(mcp: FastMCP):
    @mcp.tool()
    def world_cup_report(date: str = "") -> dict:
        """生成世界杯保障日报 Markdown。只展示数据事实、峰值、波动和空值项。"""
        cfg = get_config()
        return report(cfg.db_path, date=date)
