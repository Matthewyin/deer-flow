import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.model import (  # noqa: E402
    AddressObject,
    ConfigTemplate,
    DeviceProfile,
    ManagementAccess,
    NormalizedConfig,
    PolicyRule,
    ServiceObject,
    Zone,
)
from core.compare import check_snippet_against_template, compare_config_to_template  # noqa: E402
from core.template import infer_template, load_template, save_approved_template  # noqa: E402


def test_infer_template_creates_draft_from_approved_configs():
    template = infer_template(
        [
            _config(
                "fw-a",
                zones=["trust", "untrust"],
                address_objects=["web_server", "db_server"],
                service_objects=["https", "ssh"],
            ),
            _config(
                "fw-b",
                zones=["trust", "dmz"],
                address_objects=["web_server", "app_server"],
                service_objects=["https", "mysql"],
            ),
        ],
        standard_zone="internet_edge",
        role="border_firewall",
    )

    assert template.template_id == "firewall.internet_edge.border_firewall"
    assert template.status == "draft"
    assert template.device_type == "firewall"
    assert template.required_modules == [
        "zones",
        "address_objects",
        "service_objects",
        "policy_rules",
    ]
    assert template.expected_patterns["policy_rules"]["require_logging"] is True
    assert template.expected_patterns["policy_rules"]["forbid_any_to_any_permit"] is True
    assert template.expected_patterns["management_access"]["forbid_any_source"] is True
    assert template.reference_baseline["zone_names"] == ["dmz", "trust", "untrust"]
    assert template.reference_baseline["service_names"] == ["https", "mysql", "ssh"]
    assert template.reference_baseline["address_object_names"] == [
        "app_server",
        "db_server",
        "web_server",
    ]
    assert template.source_configs == ["fw-a", "fw-b"]


def test_infer_template_only_requires_modules_present_in_all_configs():
    template = infer_template(
        [
            _config("fw-a", service_objects=["https"]),
            _config("fw-b", service_objects=[]),
        ],
        standard_zone="dmz",
        role="border_firewall",
    )

    assert "service_objects" not in template.required_modules
    assert "zones" in template.required_modules
    assert "address_objects" in template.required_modules
    assert "policy_rules" in template.required_modules


def test_save_approved_template_writes_yaml_without_mutating_draft(tmp_path):
    draft = infer_template(
        [_config("中文设备", service_objects=["https"])],
        standard_zone="dmz",
        role="border_firewall",
    )

    path = save_approved_template(draft, tmp_path, reviewed_by="张三")
    loaded = load_template(path)

    assert path == tmp_path / "firewall" / "dmz" / "border_firewall.yaml"
    assert draft.status == "draft"
    assert draft.reviewed_by == ""
    assert draft.reviewed_at == ""
    assert loaded.status == "approved"
    assert loaded.reviewed_by == "张三"
    assert loaded.reviewed_at
    assert loaded.source_configs == ["中文设备"]
    assert "中文设备" in path.read_text(encoding="utf-8")


def test_load_template_roundtrip_preserves_template_data(tmp_path):
    draft = infer_template(
        [_config("fw-a", service_objects=["https", "ssh"])],
        standard_zone="internet_edge",
        role="border_firewall",
    )

    path = save_approved_template(draft, tmp_path, reviewed_by="reviewer")
    loaded = load_template(path)

    assert loaded.template_id == draft.template_id
    assert loaded.standard_zone == draft.standard_zone
    assert loaded.role == draft.role
    assert loaded.required_modules == draft.required_modules
    assert loaded.expected_patterns == draft.expected_patterns
    assert loaded.reference_baseline == draft.reference_baseline


def test_infer_template_rejects_empty_configs():
    with pytest.raises(ValueError, match="至少需要一份认可配置才能反推模板"):
        infer_template([], standard_zone="dmz", role="border_firewall")


def test_compare_reports_missing_required_module():
    result = compare_config_to_template(
        _config("fw-a", service_objects=[]),
        _approved_template(required_modules=["zones", "service_objects"]),
    )

    assert result.matched == ["zones"]
    assert [
        (finding.finding_id, finding.severity, finding.module, finding.finding_type)
        for finding in result.findings
    ] == [
        ("F-0001", "high", "service_objects", "missing")
    ]


def test_compare_reports_policy_logging_false_and_unknown():
    result = compare_config_to_template(
        _config(
            "fw-a",
            policy_rules=[
                PolicyRule(
                    name="logged",
                    action="permit",
                    source_objects=["host-a"],
                    destination_objects=["host-b"],
                    services=["https"],
                    logging=True,
                ),
                PolicyRule(
                    name="unknown",
                    action="permit",
                    source_objects=["host-a"],
                    destination_objects=["host-b"],
                    services=["https"],
                    logging=None,
                ),
                PolicyRule(
                    name="not_logged",
                    action="permit",
                    source_objects=["host-a"],
                    destination_objects=["host-b"],
                    services=["https"],
                    logging=False,
                ),
            ],
        ),
        _approved_template(require_logging=True, forbid_any_to_any_permit=False),
    )

    assert [
        (finding.severity, finding.finding_type, finding.actual)
        for finding in result.findings
    ] == [
        ("info", "unknown", "无法确认策略 unknown 是否开启日志"),
        ("medium", "risky", "策略 not_logged 未开启日志"),
    ]
    assert all("日志" in finding.recommendation for finding in result.findings)
    assert "policy_rules" not in result.matched
    assert "zones" in result.matched


@pytest.mark.parametrize(
    "rule",
    [
        PolicyRule(
            name="permit_upper",
            action="PERMIT",
            source_objects=["ANY"],
            destination_objects=["any"],
            services=["any"],
        ),
        PolicyRule(
            name="pass_empty",
            action="pass",
            source_objects=[],
            destination_objects=[],
            services=[],
        ),
        PolicyRule(
            name="allow_mixed",
            action="Allow",
            source_objects=["host-a", "any"],
            destination_objects=["ANY"],
            services=["tcp", "Any"],
        ),
    ],
)
def test_compare_reports_any_to_any_permit_actions(rule):
    result = compare_config_to_template(
        _config("fw-a", policy_rules=[rule]),
        _approved_template(require_logging=False, forbid_any_to_any_permit=True),
    )

    assert [
        (finding.severity, finding.module, finding.finding_type)
        for finding in result.findings
    ] == [
        ("high", "policy_rules", "risky")
    ]


def test_compare_does_not_report_deny_any_to_any():
    result = compare_config_to_template(
        _config(
            "fw-a",
            policy_rules=[
                PolicyRule(
                    name="deny_any",
                    action="deny",
                    source_objects=["any"],
                    destination_objects=["any"],
                    services=["any"],
                ),
            ],
        ),
        _approved_template(require_logging=False, forbid_any_to_any_permit=True),
    )

    assert result.findings == []


def test_compare_skips_disabled_policy_risks():
    result = compare_config_to_template(
        _config(
            "fw-a",
            policy_rules=[
                PolicyRule(
                    name="disabled_any",
                    action="permit",
                    source_objects=["any"],
                    destination_objects=["any"],
                    services=["any"],
                    logging=False,
                    enabled=False,
                ),
            ],
        ),
        _approved_template(require_logging=True, forbid_any_to_any_permit=True),
    )

    assert result.findings == []
    assert "policy_rules" in result.matched


def test_check_snippet_without_current_adds_info_unknown():
    result = check_snippet_against_template(
        _config("snippet"),
        _approved_template(require_logging=False, forbid_any_to_any_permit=False),
    )

    assert [(finding.severity, finding.finding_type) for finding in result.findings] == [
        ("info", "unknown")
    ]
    assert "当前完整配置" in result.findings[0].recommendation


def test_check_snippet_with_current_does_not_add_info_unknown():
    result = check_snippet_against_template(
        _config("snippet"),
        _approved_template(require_logging=False, forbid_any_to_any_permit=False),
        current=_config("current"),
    )

    assert all(finding.finding_type != "unknown" for finding in result.findings)


def test_check_snippet_with_current_merges_non_empty_modules():
    result = check_snippet_against_template(
        _config(
            "snippet",
            zones=[],
            address_objects=[],
            service_objects=[],
            policy_rules=[
                PolicyRule(
                    name="snippet_without_logging",
                    action="permit",
                    source_objects=["host-a"],
                    destination_objects=["host-b"],
                    services=["https"],
                    logging=False,
                ),
            ],
        ),
        _approved_template(),
        current=_config("current"),
    )

    assert ("medium", "risky", "policy_rules") in [
        (finding.severity, finding.finding_type, finding.module)
        for finding in result.findings
    ]
    assert all(finding.finding_type != "missing" for finding in result.findings)
    assert all(finding.module != "config" for finding in result.findings)
    assert "zones" in result.matched
    assert "policy_rules" not in result.matched


def test_compare_matched_excludes_modules_with_findings():
    result = compare_config_to_template(
        _config(
            "fw-a",
            policy_rules=[
                PolicyRule(
                    name="unknown_logging",
                    action="permit",
                    source_objects=["host-a"],
                    destination_objects=["host-b"],
                    services=["https"],
                    logging=None,
                ),
            ],
        ),
        _approved_template(required_modules=["zones", "policy_rules"]),
    )

    assert result.matched == ["zones"]
    assert [
        (finding.severity, finding.module, finding.finding_type)
        for finding in result.findings
    ] == [
        ("info", "policy_rules", "unknown")
    ]


def _config(
    device_name: str,
    zones: list[str] | None = None,
    address_objects: list[str] | None = None,
    service_objects: list[str] | None = None,
    policy_rules: list[PolicyRule] | None = None,
) -> NormalizedConfig:
    return NormalizedConfig(
        device_profile=DeviceProfile(
            device_name=device_name,
            vendor="H3C",
            standard_zone="dmz",
            role="border_firewall",
        ),
        zones=[Zone(name=name) for name in (["trust"] if zones is None else zones)],
        address_objects=[
            AddressObject(name=name) for name in (["web_server"] if address_objects is None else address_objects)
        ],
        service_objects=[
            ServiceObject(name=name) for name in (["https"] if service_objects is None else service_objects)
        ],
        policy_rules=policy_rules
        if policy_rules is not None
        else [
            PolicyRule(
                name="allow_https",
                action="permit",
                source_zones=["untrust"],
                destination_zones=["dmz"],
                source_objects=["any"],
                destination_objects=["web_server"],
                services=["https"],
                logging=True,
            )
        ],
        management_access=[ManagementAccess(protocol="ssh", allowed_sources=["10.0.0.0/24"])],
    )


def _approved_template(
    required_modules: list[str] | None = None,
    require_logging: bool = True,
    forbid_any_to_any_permit: bool = True,
) -> ConfigTemplate:
    return ConfigTemplate(
        template_id="firewall.dmz.border_firewall",
        standard_zone="dmz",
        role="border_firewall",
        status="approved",
        required_modules=["zones", "address_objects", "service_objects", "policy_rules"]
        if required_modules is None
        else required_modules,
        expected_patterns={
            "policy_rules": {
                "require_logging": require_logging,
                "forbid_any_to_any_permit": forbid_any_to_any_permit,
            }
        },
    )
