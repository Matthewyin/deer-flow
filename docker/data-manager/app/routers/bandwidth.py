from fastapi import APIRouter, UploadFile, File, HTTPException

from app.services.bandwidth_service import (
    get_status,
    save_file,
    trigger_rebuild,
)

router = APIRouter(tags=["bandwidth"])


@router.get("/api/bandwidth/status")
async def bandwidth_status():
    return get_status()


@router.post("/api/bandwidth/upload")
async def bandwidth_upload(file: UploadFile = File(...)):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext != "md":
        raise HTTPException(status_code=400, detail="Only .md files are accepted")
    content = await file.read()
    save_result = save_file(content)
    if not save_result["success"]:
        raise HTTPException(status_code=400, detail=save_result["error"])
    rebuild_result = trigger_rebuild()
    return {"save": save_result, "rebuild": rebuild_result}


@router.post("/api/bandwidth/rebuild")
async def bandwidth_rebuild():
    rebuild_result = trigger_rebuild()
    return {"rebuild": rebuild_result}