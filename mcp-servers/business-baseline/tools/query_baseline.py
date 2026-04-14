import logging
from typing import Optional

from config import get_config
from db.database import get_connection, init_db
from db.models import get_all_baselines

logger = logging.getLogger(__name__)


def query_baseline_impl(metric_key: Optional[str] = None) -> dict:
    cfg = get_config()
    init_db(cfg.sqlite.db_path)
    conn = get_connection(cfg.sqlite.db_path)

    baselines = get_all_baselines(conn, metric_key)
    conn.close()

    return {
        "baseline_count": len(baselines),
        "baselines": baselines,
    }


def register(mcp):
    @mcp.tool()
    def query_baseline(metric_key: Optional[str] = None) -> dict:
        """查询基线数据（全历史平均）。为空则返回所有指标的基线。

        Args:
            metric_key: 指标键名，为空则返回全部基线

        Returns:
            dict: {baseline_count, baselines: [{metric_key, sub_name, avg_*, sample_count}]}
        """
        return query_baseline_impl(metric_key)
