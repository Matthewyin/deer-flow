"""导入批次读取 MCP 工具。"""

import json
import os
from pathlib import Path
from typing import Any

from core.model import NormalizedConfig
from core.template import infer_template
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


def _compact_config(config: dict) -> dict:
    profile = config.get("device_profile", {})
    return {
        "device_profile": profile,
        "module_counts": {
            "zones": len(config.get("zones", [])),
            "interfaces": len(config.get("interfaces", [])),
            "address_objects": len(config.get("address_objects", [])),
            "service_objects": len(config.get("service_objects", [])),
            "policy_rules": len(config.get("policy_rules", [])),
            "nat_rules": len(config.get("nat_rules", [])),
            "routes": len(config.get("routes", [])),
            "management_access": len(config.get("management_access", [])),
            "logging": len(config.get("logging", [])),
            "unparsed_blocks": len(config.get("unparsed_blocks", [])),
        },
    }


def _unsupported_result(import_id: str, vendor: str, device_type: str) -> dict:
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


def _parse_import_configs(
    import_id: str,
    standard_zone: str = "",
    role: str = "",
    include_filenames: list[str] | None = None,
    exclude_filenames: list[str] | None = None,
) -> tuple[dict, list[dict], list[dict]]:
    item = _find_import(import_id)
    vendor = item.get("vendor", "")
    device_type = item.get("device_type", "")
    zone = standard_zone or item.get("standard_zone") or "unspecified"
    device_role = role or item.get("role") or "unspecified"

    if device_type != "firewall" or vendor not in SUPPORTED_FIREWALL_VENDORS:
        return item, [], [{"unsupported": _unsupported_result(import_id, vendor, device_type)["unsupported"][0]}]

    include_set = {name for name in include_filenames or [] if name}
    exclude_set = {name for name in exclude_filenames or [] if name}
    configs = []
    failed = []
    for file_item in item.get("files", []):
        filename = file_item.get("filename") or ""
        stored_filename = file_item.get("stored_filename") or ""
        if include_set and filename not in include_set and stored_filename not in include_set:
            continue
        if filename in exclude_set or stored_filename in exclude_set:
            continue
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
                    "filename": filename,
                    "stored_filename": stored_filename,
                    "path": str(path),
                    "config": config,
                }
            )
        except Exception as e:
            failed.append(
                {
                    "filename": filename,
                    "path": str(path),
                    "error": str(e),
                }
            )
    return item, configs, failed


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
    include_full_configs: bool = False,
    include_filenames: list[str] | None = None,
    exclude_filenames: list[str] | None = None,
) -> dict:
    """解析 data-manager 导入的配置批次。

    当前只解析防火墙，且仅支持 H3C、Huawei、Hillstone。F5、深信服及其他设备类型会保留为未支持项。
    默认只返回摘要，避免把大批量完整配置写入对话历史。
    """
    item = _find_import(import_id)
    vendor = item.get("vendor", "")
    device_type = item.get("device_type", "")

    if device_type != "firewall" or vendor not in SUPPORTED_FIREWALL_VENDORS:
        return _unsupported_result(import_id, vendor, device_type)

    _item, configs, failed = _parse_import_configs(
        import_id,
        standard_zone=standard_zone,
        role=role,
        include_filenames=include_filenames,
        exclude_filenames=exclude_filenames,
    )
    returned_configs = configs if include_full_configs else [
        {
            "filename": config["filename"],
            "stored_filename": config["stored_filename"],
            "path": config["path"],
            "config": _compact_config(config["config"]),
        }
        for config in configs
    ]

    return {
        "ok": True,
        "import_id": import_id,
        "vendor": vendor,
        "device_type": device_type,
        "configs": returned_configs,
        "compact": not include_full_configs,
        "failed": failed,
        "unsupported": [],
    }


def config_audit_infer_template_from_import_batch(
    import_id: str,
    standard_zone: str,
    role: str,
    include_filenames: list[str] | None = None,
    exclude_filenames: list[str] | None = None,
) -> dict:
    """从 data-manager 导入批次直接反推 draft 模板。

    工具内部解析完整配置，但只返回模板草稿和文件统计，避免大批量配置事实进入对话历史。
    """
    item, configs, failed = _parse_import_configs(
        import_id,
        standard_zone=standard_zone,
        role=role,
        include_filenames=include_filenames,
        exclude_filenames=exclude_filenames,
    )
    vendor = item.get("vendor", "")
    device_type = item.get("device_type", "")
    if device_type != "firewall" or vendor not in SUPPORTED_FIREWALL_VENDORS:
        return _unsupported_result(import_id, vendor, device_type)

    normalized = [NormalizedConfig(**config["config"]) for config in configs]
    template = infer_template(normalized, standard_zone, role)
    return {
        "ok": True,
        "import_id": import_id,
        "vendor": vendor,
        "device_type": device_type,
        "parsed_count": len(configs),
        "failed": failed,
        "template": template.model_dump(),
    }


def register(mcp: Any):
    mcp.tool()(config_audit_list_import_batches)
    mcp.tool()(config_audit_parse_import_batch)
    mcp.tool()(config_audit_infer_template_from_import_batch)
