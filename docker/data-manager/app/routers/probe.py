import asyncio
import logging

from fastapi import APIRouter

from app.services.probe_service import (
    collect_probe_data,
    get_status,
    get_history,
    save_collection_log,
)

logger = logging.getLogger("data-manager")
_collect_running = False

router = APIRouter(tags=["probe"])


@router.get("/api/probe/status")
async def probe_status():
    return get_status()


@router.get("/api/probe/history")
async def probe_history(limit: int = 20):
    return get_history(limit)


@router.post("/api/probe/collect")
async def probe_collect():
    global _collect_running
    if _collect_running:
        return {
            "status": "already_running",
            "message": "采集正在进行中，请稍后查看历史记录",
        }

    _collect_running = True

    async def _run():
        global _collect_running
        try:
            result = await asyncio.to_thread(collect_probe_data)
            from datetime import datetime

            total_new = sum(
                v.get("tgz_new", 0) + v.get("json_new", 0)
                for v in result.values()
                if isinstance(v, dict) and "error" not in v
            )
            errors = [
                k for k, v in result.items() if isinstance(v, dict) and "error" in v
            ]
            log_entry = {
                "time": datetime.now().isoformat(),
                "status": "success"
                if not errors
                else "partial"
                if total_new > 0
                else "failed",
                "new_files": total_new,
                "errors": errors,
                "details": result,
            }
            save_collection_log(log_entry)
            logger.info(f"Background probe collection done: {total_new} new files")
        except Exception as e:
            logger.error(f"Background probe collection failed: {e}")
        finally:
            _collect_running = False

    asyncio.create_task(_run())
    return {"status": "started", "message": "采集已启动，请稍后查看历史记录"}
