from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.services.emergency_service import (
    CATEGORIES,
    DOC_TYPE_TO_DIR,
    list_categories,
    list_files,
    save_file,
    delete_file,
    trigger_ingest,
)

router = APIRouter(tags=["emergency"])


@router.get("/api/emergency/categories")
async def get_categories():
    return list_categories()


@router.get("/api/emergency/files")
async def get_files(doc_type: str):
    if doc_type not in DOC_TYPE_TO_DIR:
        raise HTTPException(status_code=400, detail=f"Invalid doc_type: {doc_type}")
    return list_files(DOC_TYPE_TO_DIR[doc_type])


@router.post("/api/emergency/upload")
async def upload_file(file: UploadFile = File(...), doc_type: str = Form(...)):
    if doc_type not in DOC_TYPE_TO_DIR:
        raise HTTPException(status_code=400, detail=f"Invalid doc_type: {doc_type}")
    category_dir = DOC_TYPE_TO_DIR[doc_type]
    content = await file.read()
    save_result = save_file(category_dir, file.filename, content)
    if not save_result["success"]:
        raise HTTPException(status_code=400, detail=save_result["error"])
    ingest_result = trigger_ingest()
    return {"save": save_result, "ingest": ingest_result}


@router.delete("/api/emergency/files/{doc_type}/{filename:path}")
async def remove_file(doc_type: str, filename: str):
    if doc_type not in DOC_TYPE_TO_DIR:
        raise HTTPException(status_code=400, detail=f"Invalid doc_type: {doc_type}")
    category_dir = DOC_TYPE_TO_DIR[doc_type]
    delete_result = delete_file(category_dir, filename)
    if not delete_result["success"]:
        raise HTTPException(status_code=404, detail=delete_result["error"])
    ingest_result = trigger_ingest()
    return {"delete": delete_result, "ingest": ingest_result}
