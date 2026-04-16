import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter

from app.services.probe_service import (
    collect_probe_data,
    get_status,
    get_history,
    get_ingest_history,
    save_collection_log,
    save_ingest_log,
    parse_and_ingest_probe_data,
)

logger = logging.getLogger("data-manager")

_collect_running = False
_ingest_running = False

_last_collect_result = None
_last_ingest_result = None

router = APIRouter(tags=["probe"])


@router.get("/api/probe/status")
async def probe_status():
    return get_status()


@router.get("/api/probe/history")
async def probe_history(limit: int = 20):
    return get_history(limit)


@router.get("/api/probe/ingest-history")
async def probe_ingest_history(limit: int = 20):
    return get_ingest_history(limit)


@router.get("/api/probe/collect-result")
async def probe_collect_result():
    global _collect_running, _last_collect_result
    if _collect_running:
        return {"status": "running", "message": "采集进行中"}
    if _last_collect_result is None:
        return {"status": "idle", "message": "无采集记录"}
    return _last_collect_result


@router.get("/api/probe/ingest-result")
async def probe_ingest_result():
    global _ingest_running, _last_ingest_result
    if _ingest_running:
        return {"status": "running", "message": "解析入库进行中"}
    if _last_ingest_result is None:
        return {"status": "idle", "message": "无入库记录"}
    return _last_ingest_result


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
        global _collect_running, _last_collect_result, _last_ingest_result
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
            logger.info(f"Background probe collection done: {total_new} new files")

            _last_collect_result = {
                "status": status,
                "message": f"采集完成：{total_new} 个新文件"
                + (f"，{len(errors)} 个区域失败" if errors else ""),
                "new_files": total_new,
                "error_code": error_code,
                "error_details": error_details,
            }

            if total_new > 0:
                logger.info("Auto-triggering probe ingest after collection")
                ingest_result = await asyncio.to_thread(parse_and_ingest_probe_data)
                logger.info(
                    f"Auto-ingest done: {ingest_result.get('total_inserted', 0)} inserted"
                )
                # 更新入库结果（供轮询接口使用）
                _last_ingest_result = {
                    "status": "success"
                    if ingest_result.get("total_errors", 0) == 0
                    else "partial",
                    "message": f"自动入库完成：{ingest_result.get('total_inserted', 0)} 条新增，{ingest_result.get('total_skipped', 0)} 条跳过",
                    "inserted": ingest_result.get("total_inserted", 0),
                    "skipped": ingest_result.get("total_skipped", 0),
                    "error_code": None
                    if ingest_result.get("total_errors", 0) == 0
                    else "INGEST_PARTIAL_ERROR",
                    "error_details": ingest_result.get("errors", []),
                }

        except Exception as e:
            logger.error(f"Background probe collection failed: {e}")
            _last_collect_result = {
                "status": "failed",
                "message": f"采集异常：{str(e)}",
                "error_code": "COLLECT_EXCEPTION",
                "error_details": {"exception": str(e)},
            }
        finally:
            _collect_running = False

    asyncio.create_task(_run())
    return {"status": "started", "message": "采集已启动，完成后将自动解析入库"}


@router.post("/api/probe/parse-ingest")
async def probe_parse_ingest():
    global _ingest_running, _last_ingest_result
    if _ingest_running:
        return {
            "status": "already_running",
            "message": "解析入库正在进行中，请稍后",
            "error_code": "INGEST_ALREADY_RUNNING",
        }

    _ingest_running = True
    _last_ingest_result = None

    async def _run():
        global _ingest_running, _last_ingest_result
        try:
            result = await asyncio.to_thread(parse_and_ingest_probe_data)
            total_inserted = result.get("total_inserted", 0)
            total_parsed = result.get("total_parsed", 0)
            total_skipped = result.get("total_skipped", 0)
            errors = result.get("errors", [])

            if errors:
                final_status = "partial" if total_inserted > 0 else "failed"
                error_code = (
                    "INGEST_PARTIAL_ERROR" if total_inserted > 0 else "INGEST_FAILED"
                )
            else:
                final_status = "success"
                error_code = None

            save_ingest_log(
                {
                    "time": datetime.now().isoformat(),
                    "status": final_status,
                    "total_parsed": total_parsed,
                    "total_inserted": total_inserted,
                    "total_skipped": total_skipped,
                    "errors": errors,
                }
            )
            logger.info(f"Manual ingest done: {total_inserted} inserted")

            _last_ingest_result = {
                "status": final_status,
                "message": f"解析入库完成：{total_parsed} 解析，{total_inserted} 入库，{total_skipped} 跳过"
                + (f"，{len(errors)} 个错误" if errors else ""),
                "total_parsed": total_parsed,
                "total_inserted": total_inserted,
                "total_skipped": total_skipped,
                "error_code": error_code,
                "error_details": errors if errors else None,
            }

        except Exception as e:
            logger.error(f"Probe ingest failed: {e}")
            _last_ingest_result = {
                "status": "failed",
                "message": f"解析入库异常：{str(e)}",
                "error_code": "INGEST_EXCEPTION",
                "error_details": {"exception": str(e)},
            }
        finally:
            _ingest_running = False

    asyncio.create_task(_run())
    return {"status": "started", "message": "解析入库已启动，请稍后查看结果"}
