"""导入批次读取 MCP 工具。"""

import json
import os
from pathlib import Path
from typing import Any

from tools.parse_config import parse_config_text


DEFAULT_IMPORT_DIR = os.environ.get("CONFIG_AUDIT_IMPORT_DIR", "/app/.deer-flow/device-configs")
SUPPORTED_FIREWALL_VENDORS = {"h3c", "huawei", "hillstone"}


def _index_path() -> Path:
    return Path(DEFAULT_IMPORT_DIR) / "index.json"


def _load_index() -> dict:
    path = _index_path()
    if not path.exists():
        return {"imports": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("imports"), list):
        return {"imports": []}
    return data


def _find_import(import_id: str) -> dict:
    for item in _load_index()["imports"]:
        if item.get("import_id") == import_id:
            return item
    raise ValueError(f"未找到导入批次：{import_id}")


def config_audit_list_import_batches(vendor: str = "", device_type: str = "") -> dict:
    """列出 data-manager 已导入的设备配置批次。"""
    imports = _load_index()["imports"]
    if vendor:
        imports = [item for item in imports if item.get("vendor") == vendor.strip().lower()]
    if device_type:
        imports = [item for item in imports if item.get("device_type") == device_type.strip().lower()]
    return {"ok": True, "base_dir": DEFAULT_IMPORT_DIR, "total": len(imports), "imports": imports}


def config_audit_parse_import_batch(
    import_id: str,
    standard_zone: str = "",
    role: str = "",
) -> dict:
    """解析 data-manager 导入的配置批次。

    当前只解析防火墙，且仅支持 H3C、Huawei、Hillstone。F5、深信服及其他设备类型会保留为未支持项。
    """
    item = _find_import(import_id)
    vendor = item.get("vendor", "")
    device_type = item.get("device_type", "")
    zone = standard_zone or item.get("standard_zone") or "unspecified"
    device_role = role or item.get("role") or "unspecified"

    if device_type != "firewall" or vendor not in SUPPORTED_FIREWALL_VENDORS:
        return {
            "ok": True,
            "import_id": import_id,
            "configs": [],
            "unsupported": [
                {
                    "vendor": vendor,
                    "device_type": device_type,
                    "reason": "当前 config-audit 仅支持 H3C、Huawei、Hillstone 防火墙解析",
                }
            ],
        }

    configs = []
    failed = []
    for file_item in item.get("files", []):
        path = Path(file_item.get("path", ""))
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            config = parse_config_text(
                text,
                vendor,
                zone,
                device_role,
                site_name=item.get("site_name", ""),
                local_area_name=item.get("local_area_name", ""),
            )
            configs.append(
                {
                    "filename": file_item.get("filename"),
                    "stored_filename": file_item.get("stored_filename"),
                    "path": str(path),
                    "config": config,
                }
            )
        except Exception as e:
            failed.append(
                {
                    "filename": file_item.get("filename"),
                    "path": str(path),
                    "error": str(e),
                }
            )

    return {
        "ok": True,
        "import_id": import_id,
        "vendor": vendor,
        "device_type": device_type,
        "configs": configs,
        "failed": failed,
        "unsupported": [],
    }


def register(mcp: Any):
    mcp.tool()(config_audit_list_import_batches)
    mcp.tool()(config_audit_parse_import_batch)
