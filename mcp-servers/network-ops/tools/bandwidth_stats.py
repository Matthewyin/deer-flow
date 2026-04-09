"""bandwidth_stats tool — query bandwidth tier statistics and line counts."""

import logging
from typing import Optional

from fastmcp import FastMCP

from config import get_config

logger = logging.getLogger(__name__)


def register(mcp: FastMCP):
    @mcp.tool()
    def bandwidth_stats(
        bandwidth: Optional[str] = None,
    ) -> dict:
        """查询带宽档位统计信息。可按带宽档位筛选，返回线路数量。

        Args:
            bandwidth: 可选带宽筛选，如 "10M"。不传则返回所有档位统计。

        Returns:
            统计信息字典，包含:
            - tiers: 所有带宽档位配置列表
            - line_count: 匹配的线路数量（需要MySQL连接）
            - total_lines: 总线路数
        """
        from db.sqlite_client import SQLiteClient

        config = get_config()
        db = SQLiteClient(config.sqlite.db_path)

        tiers = db.get_all_tiers()

        line_count = None
        total_lines = None
        try:
            from db.mysql_client import MySQLClient

            mysql = MySQLClient(config.mysql)
            if bandwidth:
                lines = mysql.search_lines(bandwidth=bandwidth)
                line_count = len(lines)
            total_lines = len(mysql.search_lines())
            mysql.close()
        except Exception as e:
            logger.warning(f"MySQL unavailable for stats: {e}")

        return {
            "tiers": tiers,
            "line_count": line_count,
            "total_lines": total_lines,
        }
