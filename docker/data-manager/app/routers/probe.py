import asyncio
import logging
import sqlite3
from datetime import datetime

from fastapi import APIRouter

from app.services.probe_service import (
    collect_probe_data,
    get_status,
    get_history,
    save_collection_log,
)

logger = logging.getLogger("data-manager")

_collect_running = False
_last_collect_result = None

router = APIRouter(tags=["probe"])


@router.get("/api/probe/status")
async def probe_status():
    return get_status()


@router.get("/api/probe/history")
async def probe_history(limit: int = 20):
    return get_history(limit)


@router.get("/api/probe/collect-result")
async def probe_collect_result():
    global _collect_running, _last_collect_result
    if _collect_running:
        return {"status": "running", "message": "采集进行中"}
    if _last_collect_result is None:
        return {"status": "idle", "message": "无采集记录"}
    return _last_collect_result


@router.get("/api/probe/uningested")
async def probe_uningested():
    """Return count of uningested raw files per region."""
    import os
    db_path = os.environ.get("PROBE_DB_PATH", "/app/backend/.deer-flow/db/remote_probe.db")
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT region, COUNT(*) as cnt FROM raw_files WHERE ingested = 0 GROUP BY region"
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) as cnt FROM raw_files WHERE ingested = 0").fetchone()
        conn.close()
        return {
            "total_uningested": total["cnt"] if total else 0,
            "by_region": {r["region"]: r["cnt"] for r in rows},
        }
    except Exception as e:
        return {"error": str(e), "total_uningested": 0, "by_region": {}}


@router.post("/api/probe/collect")
async def probe_collect():
    global _collect_running, _last_collect_result
    if _collect_running:
        return {
            "status": "already_running",
            "message": "采集正在进行中，请稍后查看历史记录",
            "error_code": "COLLECT_ALREADY_RUNNING",
        }

    _collect_running = True
    _last_collect_result = None

    async def _run():
        global _collect_running, _last_collect_result
        try:
            result = await asyncio.to_thread(collect_probe_data)

            total_new = sum(
                v.get("tgz_new", 0) + v.get("json_new", 0)
                for v in result.values()
                if isinstance(v, dict) and "error" not in v
            )
            errors = [
                k for k, v in result.items() if isinstance(v, dict) and "error" in v
            ]
            error_details = {
                k: v.get("error", "unknown")
                for k, v in result.items()
                if isinstance(v, dict) and "error" in v
            }

            if not errors and total_new >= 0:
                status = "success"
                error_code = None
            elif total_new > 0:
                status = "partial"
                error_code = "COLLECT_PARTIAL_FAILURE"
            else:
                status = "failed"
                error_code = "COLLECT_ALL_FAILED"

            log_entry = {
                "time": datetime.now().isoformat(),
                "status": status,
                "new_files": total_new,
                "errors": errors,
                "details": result,
            }
            save_collection_log(log_entry)
            logger.info(f"Probe collection done: {total_new} new files (ingest handled by MCP-server)")

            _last_collect_result = {
                "status": status,
                "message": f"采集完成：{total_new} 个新文件"
                + (f"，{len(errors)} 个区域失败" if errors else ""),
                "new_files": total_new,
                "error_code": error_code,
                "error_details": error_details,
            }

        except Exception as e:
            logger.error(f"Probe collection failed: {e}")
            _last_collect_result = {
                "status": "failed",
                "message": f"采集异常：{str(e)}",
                "error_code": "COLLECT_EXCEPTION",
                "error_details": {"exception": str(e)},
            }
        finally:
            _collect_running = False

    asyncio.create_task(_run())
    return {"status": "started", "message": "采集已启动，入库由 MCP Server 统一管理"}


@router.post("/api/probe/parse-ingest")
async def probe_parse_ingest():
    return {
        "status": "deprecated",
        "message": "入库操作已迁移至 MCP Server，由 ensure_probe_data 工具统一管理。此接口不再执行入库。",
    }


@router.get("/api/probe/ingest-history")
async def probe_ingest_history(limit: int = 20):
    return {
        "status": "deprecated",
        "message": "入库操作已迁移至 MCP Server",
        "history": [],
    }


@router.get("/api/probe/ingest-result")
async def probe_ingest_result():
    return {
        "status": "deprecated",
        "message": "入库操作已迁移至 MCP Server",
    }
