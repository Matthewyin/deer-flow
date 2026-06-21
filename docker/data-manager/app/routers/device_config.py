from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services.device_config_service import (
    create_import_batch,
    get_options,
    list_import_batches,
)


router = APIRouter(tags=["device-config"])


@router.get("/api/device-configs/options")
async def device_config_options():
    return get_options()


@router.get("/api/device-configs/imports")
async def device_config_imports(vendor: str = "", device_type: str = ""):
    try:
        return list_import_batches(vendor=vendor, device_type=device_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/device-configs/imports")
async def device_config_upload(
    vendor: str = Form(...),
    device_type: str = Form(...),
    files: list[UploadFile] = File(...),
    batch_name: str = Form(""),
    standard_zone: str = Form(""),
    role: str = Form(""),
    site_name: str = Form(""),
    local_area_name: str = Form(""),
):
    try:
        payload = [(file.filename or "config.txt", await file.read()) for file in files]
        return create_import_batch(
            vendor=vendor,
            device_type=device_type,
            files=payload,
            batch_name=batch_name,
            standard_zone=standard_zone,
            role=role,
            site_name=site_name,
            local_area_name=local_area_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
