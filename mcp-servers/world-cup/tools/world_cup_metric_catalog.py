from fastmcp import FastMCP

from config import get_config
from core.db import metric_catalog


def register(mcp: FastMCP):
    @mcp.tool()
    def world_cup_metric_catalog() -> dict:
        """返回世界杯数据指标目录，包含 metric_key、中文名、来源 sheet 和粒度。"""
        cfg = get_config()
        return metric_catalog(cfg.db_path)
