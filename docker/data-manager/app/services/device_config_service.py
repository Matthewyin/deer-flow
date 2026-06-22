import json
import os
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(os.environ.get("DEVICE_CONFIG_IMPORT_DIR", "/app/.deer-flow/device-configs"))
INDEX_PATH = BASE_DIR / "index.json"

VENDORS = {
    "huawei": "华为",
    "h3c": "华三",
    "hillstone": "山石",
    "f5": "F5",
    "sangfor": "深信服",
}

DEVICE_TYPES = {
    "firewall": "防火墙",
    "router": "路由器",
    "switch": "交换机",
    "load_balancer": "负载均衡",
}

VENDOR_ALIASES = {
    "华为": "huawei",
    "huawei": "huawei",
    "华三": "h3c",
    "h3c": "h3c",
    "山石": "hillstone",
    "hillstone": "hillstone",
    "f5": "f5",
    "深信服": "sangfor",
    "sangfor": "sangfor",
}


def get_options() -> dict:
    return {
        "vendors": [{"value": k, "label": v} for k, v in VENDORS.items()],
        "device_types": [{"value": k, "label": v} for k, v in DEVICE_TYPES.items()],
        "base_dir": str(BASE_DIR),
    }


def normalize_vendor(vendor: str) -> str:
    key = vendor.strip().lower()
    normalized = VENDOR_ALIASES.get(key) or VENDOR_ALIASES.get(vendor.strip())
    if not normalized:
        raise ValueError("不支持的厂商")
    return normalized


def normalize_device_type(device_type: str) -> str:
    key = device_type.strip().lower()
    if key not in DEVICE_TYPES:
        raise ValueError("不支持的设备类型")
    return key


def _load_index() -> dict:
    if not INDEX_PATH.exists():
        return {"imports": []}
    try:
        data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"imports": []}
    if not isinstance(data.get("imports"), list):
        return {"imports": []}
    return data


def _save_index(data: dict) -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_filename(filename: str) -> str:
    name = Path(filename or "config.txt").name
    name = re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+", "_", name).strip("._")
    return name or "config.txt"


def create_import_batch(
    *,
    vendor: str,
    device_type: str,
    files: list[tuple[str, bytes]],
    batch_name: str = "",
    standard_zone: str = "",
    role: str = "",
    site_name: str = "",
    local_area_name: str = "",
) -> dict:
    vendor_key = normalize_vendor(vendor)
    device_type_key = normalize_device_type(device_type)
    if not files:
        raise ValueError("未选择配置文件")
    for original_name, _content in files:
        if Path(_safe_filename(original_name)).suffix.lower() != ".txt":
            raise ValueError("仅支持 .txt 配置文件")

    import_id = datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]
    storage_dir = BASE_DIR / device_type_key / vendor_key / import_id
    storage_dir.mkdir(parents=True, exist_ok=True)

    saved_files = []
    for original_name, content in files:
        filename = _safe_filename(original_name)
        target = storage_dir / filename
        if target.exists():
            target = storage_dir / f"{target.stem}-{uuid.uuid4().hex[:6]}{target.suffix}"
        target.write_bytes(content)
        saved_files.append(
            {
                "filename": original_name,
                "stored_filename": target.name,
                "size": len(content),
                "path": str(target),
            }
        )

    created_at = datetime.now().isoformat()
    metadata = {
        "import_id": import_id,
        "batch_name": batch_name.strip(),
        "created_at": created_at,
        "vendor": vendor_key,
        "vendor_label": VENDORS[vendor_key],
        "device_type": device_type_key,
        "device_type_label": DEVICE_TYPES[device_type_key],
        "standard_zone": standard_zone.strip(),
        "role": role.strip(),
        "site_name": site_name.strip(),
        "local_area_name": local_area_name.strip(),
        "storage_dir": str(storage_dir),
        "file_count": len(saved_files),
        "files": saved_files,
    }
    (storage_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    index = _load_index()
    index["imports"] = [item for item in index["imports"] if item.get("import_id") != import_id]
    index["imports"].insert(0, metadata)
    _save_index(index)
    return metadata


def list_import_batches(vendor: str = "", device_type: str = "") -> dict:
    vendor_key = normalize_vendor(vendor) if vendor else ""
    device_type_key = normalize_device_type(device_type) if device_type else ""
    imports = _load_index()["imports"]
    if vendor_key:
        imports = [item for item in imports if item.get("vendor") == vendor_key]
    if device_type_key:
        imports = [item for item in imports if item.get("device_type") == device_type_key]
    return {"base_dir": str(BASE_DIR), "total": len(imports), "imports": imports}


def delete_import_batches(import_ids: list[str]) -> dict:
    ids = [item.strip() for item in import_ids if item.strip()]
    if not ids:
        raise ValueError("未指定要删除的导入批次")

    index = _load_index()
    by_id = {item.get("import_id"): item for item in index["imports"]}
    deleted = []
    not_found = []
    errors = []

    for import_id in ids:
        item = by_id.get(import_id)
        if not item:
            not_found.append(import_id)
            continue
        storage_dir = Path(item.get("storage_dir", ""))
        try:
            storage_root = BASE_DIR.resolve()
            target_dir = storage_dir.resolve()
            if target_dir != storage_root and storage_root in target_dir.parents and target_dir.exists():
                shutil.rmtree(target_dir)
            elif target_dir.exists():
                raise ValueError("批次目录不在设备配置导入目录下")
            deleted.append(import_id)
        except (OSError, ValueError) as e:
            errors.append({"import_id": import_id, "error": str(e)})

    if deleted:
        deleted_set = set(deleted)
        index["imports"] = [
            item for item in index["imports"] if item.get("import_id") not in deleted_set
        ]
        _save_index(index)

    return {"deleted": deleted, "not_found": not_found, "errors": errors}
