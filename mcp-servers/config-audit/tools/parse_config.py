"""配置解析 MCP 工具。"""

from pathlib import Path
from typing import Any

from parsers.h3c_firewall import parse_h3c_firewall
from parsers.hillstone_firewall import parse_hillstone_firewall
from parsers.huawei_firewall import parse_huawei_firewall


def parse_config_text(
    text: str,
    vendor: str,
    standard_zone: str,
    role: str,
    **profile_kwargs,
) -> dict:
    vendor_key = vendor.strip().lower()
    if vendor_key == "h3c":
        config = parse_h3c_firewall(text, standard_zone, role, **profile_kwargs)
    elif vendor_key in {"huawei", "华为"}:
        config = parse_huawei_firewall(text, standard_zone, role, **profile_kwargs)
    elif vendor_key in {"hillstone", "山石"}:
        config = parse_hillstone_firewall(text, standard_zone, role, **profile_kwargs)
    else:
        raise ValueError(f"暂不支持的防火墙厂商：{vendor}")

    return config.model_dump()


def config_audit_parse_config(
    vendor: str,
    standard_zone: str,
    role: str,
    config_text: str = "",
    config_path: str = "",
    device_name: str = "",
    model: str = "",
    os_version: str = "",
    site_name: str = "",
    local_area_name: str = "",
) -> dict:
    """解析防火墙完整配置，产出结构化事实。

    覆盖 security zones、inter-zone policy、logging 等字段；LLM 只负责解释事实，
    不替代人工复核，也不会自动下发配置。
    """
    text = config_text
    if not text and config_path:
        path = Path(config_path)
        if not path.exists():
            raise ValueError(f"配置文件不存在：{config_path}")
        text = path.read_text(encoding="utf-8")
    if not text:
        raise ValueError("必须提供 config_text 或 config_path")

    config = parse_config_text(
        text,
        vendor,
        standard_zone,
        role,
        device_name=device_name,
        model=model,
        os_version=os_version,
        site_name=site_name,
        local_area_name=local_area_name,
    )
    return {"ok": True, "config": config}


def register(mcp: Any):
    mcp.tool()(config_audit_parse_config)
