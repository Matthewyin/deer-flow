from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from core.model import ConfigTemplate, NormalizedConfig


P0_MODULES = ["zones", "address_objects", "service_objects", "policy_rules"]


def infer_template(
    configs: list[NormalizedConfig],
    standard_zone: str,
    role: str,
) -> ConfigTemplate:
    if not configs:
        raise ValueError("至少需要一份认可配置才能反推模板")

    return ConfigTemplate(
        template_id=f"firewall.{standard_zone}.{role}",
        device_type=_first_device_type(configs),
        standard_zone=standard_zone,
        role=role,
        status="draft",
        source_configs=_source_config_names(configs),
        required_modules=_required_modules(configs),
        expected_patterns={
            "policy_rules": {
                "require_logging": True,
                "forbid_any_to_any_permit": True,
            },
            "management_access": {
                "forbid_any_source": True,
            },
        },
        reference_baseline={
            "zone_names": _sorted_names(configs, "zones"),
            "service_names": _sorted_names(configs, "service_objects"),
            "address_object_names": _sorted_names(configs, "address_objects"),
        },
    )


def save_approved_template(
    template: ConfigTemplate,
    base_dir: str | Path,
    reviewed_by: str,
) -> Path:
    approved = template.model_copy(
        deep=True,
        update={
            "status": "approved",
            "reviewed_by": reviewed_by,
            "reviewed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        },
    )
    path = Path(base_dir) / approved.device_type / approved.standard_zone / f"{approved.role}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            approved.model_dump(),
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def load_template(path: str | Path) -> ConfigTemplate:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return ConfigTemplate(**data)


def _first_device_type(configs: list[NormalizedConfig]) -> str:
    for config in configs:
        device_type = config.device_profile.device_type
        if device_type:
            return device_type
    return "firewall"


def _source_config_names(configs: list[NormalizedConfig]) -> list[str]:
    return sorted(
        {
            config.device_profile.device_name
            for config in configs
            if config.device_profile.device_name
        }
    )


def _required_modules(configs: list[NormalizedConfig]) -> list[str]:
    return [module for module in P0_MODULES if all(getattr(config, module) for config in configs)]


def _sorted_names(configs: list[NormalizedConfig], module: str) -> list[str]:
    names: set[str] = set()
    for config in configs:
        for item in getattr(config, module):
            name = _get_name(item)
            if name:
                names.add(name)
    return sorted(names)


def _get_name(item: Any) -> str:
    name = getattr(item, "name", "")
    if not isinstance(name, str):
        return ""
    return name
