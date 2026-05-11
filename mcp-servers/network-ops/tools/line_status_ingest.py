import json
import logging
import os
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP

from db.line_status_client import LineStatusClient
from config import get_config

logger = logging.getLogger(__name__)

_client: Optional[LineStatusClient] = None


def _get_client() -> LineStatusClient:
    global _client
    if _client is None:
        config = get_config()
        _client = LineStatusClient(config.sqlite.db_path)
    return _client


def register(mcp: FastMCP):
    @mcp.tool()
    async def ensure_line_status_data() -> dict:
        """扫描共享目录中的线路状态 JSON 文件，入库新数据并更新 CMA 基线。无需参数。"""
        client = _get_client()
        data_dir = os.environ.get("LINE_STATUS_DATA_DIR", "/app/.deer-flow/line-status")
        data_path = Path(data_dir)

        if not data_path.exists():
            return {"new_files": 0, "lines_ingested": 0, "baselines_updated": 0, "latest_date": None}

        ingested_dates = client.get_ingested_dates()
        new_files = 0
        total_inserted = 0
        total_skipped = 0
        latest_date = None

        for json_file in sorted(data_path.glob("*.json")):
            date_str = json_file.stem
            if date_str in ingested_dates:
                continue

            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning(f"跳过损坏文件 {json_file.name}: {e}")
                continue

            inserted, skipped = client.ingest_daily_data(data)
            total_inserted += inserted
            total_skipped += skipped
            new_files += 1
            latest_date = date_str

        baselines_updated = 0
        if new_files > 0 and latest_date:
            baselines_updated = client.update_baselines(latest_date)

        return {
            "new_files": new_files,
            "lines_ingested": total_inserted,
            "baselines_updated": baselines_updated,
            "latest_date": latest_date,
        }
