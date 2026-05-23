import json
import logging
import os
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP

from db.bandwidth_lines_client import BandwidthLinesClient
from config import get_config

logger = logging.getLogger(__name__)

_client: Optional[BandwidthLinesClient] = None


def _get_client() -> BandwidthLinesClient:
    global _client
    if _client is None:
        config = get_config()
        _client = BandwidthLinesClient(config.sqlite.db_path)
    return _client


def register(mcp: FastMCP):
    @mcp.tool()
    async def ensure_bandwidth_data() -> dict:
        """扫描共享目录中的线路带宽 JSON 文件，入库新数据。无需参数。"""
        client = _get_client()
        data_dir = os.environ.get("BANDWIDTH_LINES_DATA_DIR", "/app/.deer-flow/bandwidth-lines")
        data_path = Path(data_dir)

        if not data_path.exists():
            return {"new_files": 0, "lines_inserted": 0, "lines_skipped": 0, "latest_date": None}

        processed_files = 0
        new_files = 0
        total_inserted = 0
        total_skipped = 0
        latest_date = None

        for json_file in sorted(data_path.glob("*.json")):
            date_str = json_file.stem

            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning(f"跳过损坏文件 {json_file.name}: {e}")
                continue

            report_date = data.get("report_date") or date_str
            lines = [
                {**line, "report_date": line.get("report_date") or report_date}
                for line in data.get("lines", [])
            ]
            if lines:
                inserted, skipped = client.ingest_data(lines)
                total_inserted += inserted
                total_skipped += skipped
                processed_files += 1
                if inserted:
                    new_files += 1
                latest_date = date_str

        return {
            "processed_files": processed_files,
            "new_files": new_files,
            "lines_inserted": total_inserted,
            "lines_skipped": total_skipped,
            "latest_date": latest_date,
            "available_dates": client.get_available_dates(),
        }
