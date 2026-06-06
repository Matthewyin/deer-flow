from fastmcp import FastMCP

from config import get_config
from core.db import status


def register(mcp: FastMCP):
    @mcp.tool()
    def world_cup_status() -> dict:
        """查询世界杯数据入库状态、可用日期、sheet 覆盖和最近上传记录。"""
        cfg = get_config()
        return status(cfg.db_path)
