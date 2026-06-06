from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.world_cup_service import (
    delete_world_cup_upload,
    get_world_cup_status,
    save_parse_and_import,
)

router = APIRouter(tags=["world-cup"])


@router.get("/api/world-cup/status")
async def world_cup_status():
    return get_world_cup_status()


@router.post("/api/world-cup/upload")
async def world_cup_upload(
    file: UploadFile = File(...),
):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext != "xlsx":
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 文件")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")

    try:
        return save_parse_and_import(content, file.filename or "world-cup.xlsx")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"世界杯数据导入失败: {e}")


@router.delete("/api/world-cup/uploads/{upload_id}")
async def world_cup_delete_upload(upload_id: str):
    result = delete_world_cup_upload(upload_id)
    if not result.get("deleted"):
        raise HTTPException(status_code=404, detail="未找到该导入批次")
    return result
