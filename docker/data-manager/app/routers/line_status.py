from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from app.services.line_status_service import (
    parse_html,
    save_parsed_data,
    parse_line_table,
    save_bandwidth_data,
    get_status,
    delete_files,
)

router = APIRouter(tags=["line-status"])


class DeleteRequest(BaseModel):
    dates: list[str]


@router.get("/api/line-status/status")
async def line_status_status():
    return get_status()


@router.post("/api/line-status/upload")
async def line_status_upload(file: UploadFile = File(...)):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ("html", "htm"):
        raise HTTPException(status_code=400, detail="仅支持 .html/.htm 文件")

    content = await file.read()
    try:
        parsed = parse_html(content, file.filename or "unknown.html")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"HTML 解析失败: {e}")

    saved = save_parsed_data(parsed)

    try:
        bw_parsed = parse_line_table(content, file.filename or "unknown.html")
        bw_saved = save_bandwidth_data(bw_parsed)
    except Exception:
        bw_saved = None

    return {**saved, "bandwidth_lines": bw_saved}


@router.post("/api/line-status/delete")
async def line_status_delete(req: DeleteRequest):
    if not req.dates:
        raise HTTPException(status_code=400, detail="未指定要删除的日期")
    return delete_files(req.dates)
