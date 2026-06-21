import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.model import (  # noqa: E402
    AddressObject,
    ConfigFinding,
    ConfigTemplate,
    DeviceProfile,
    Interface,
    LoggingConfig,
    ManagementAccess,
    NatRule,
    NormalizedConfig,
    PolicyRule,
    Route,
    ServiceObject,
    UnparsedBlock,
    Zone,
)


def test_device_profile_defaults_to_firewall():
    profile = DeviceProfile(vendor="H3C", standard_zone="internet_edge", role="border_firewall")

    assert profile.device_type == "firewall"
    assert profile.vendor == "H3C"
    assert profile.standard_zone == "internet_edge"
    assert profile.role == "border_firewall"


def test_normalized_config_has_stable_module_lists():
    config = NormalizedConfig(
        device_profile=DeviceProfile(
            vendor="Hillstone",
            standard_zone="dmz",
            role="border_firewall",
        ),
        zones=[Zone(name="trust", vrouter="trust-vr")],
        address_objects=[AddressObject(name="web_server", values=["10.0.0.10"])],
        service_objects=[ServiceObject(name="https", protocol="tcp", ports=["443"])],
        policy_rules=[
            PolicyRule(
                name="allow_https",
                action="permit",
                source_zones=["untrust"],
                destination_zones=["dmz"],
                source_objects=["any"],
                destination_objects=["web_server"],
                services=["https"],
                logging=True,
                enabled=True,
            )
        ],
    )

    assert config.device_profile.device_type == "firewall"
    assert config.zones[0].name == "trust"
    assert config.policy_rules[0].logging is True


def test_finding_shape_is_stable():
    finding = ConfigFinding(
        finding_id="F-0001",
        severity="high",
        module="policy_rules",
        finding_type="missing",
        expected="存在默认拒绝策略",
        actual="未发现默认拒绝策略",
        evidence="policy_rules",
        recommendation="补充默认拒绝策略并开启日志",
    )

    dumped = finding.model_dump()

    assert dumped["severity"] == "high"
    assert dumped["finding_type"] == "missing"
    assert dumped["llm_analysis"] == ""


def test_normalized_config_default_module_lists_are_isolated_between_instances():
    first = NormalizedConfig(
        device_profile=DeviceProfile(
            vendor="H3C",
            standard_zone="internet_edge",
            role="border_firewall",
        )
    )
    second = NormalizedConfig(
        device_profile=DeviceProfile(
            vendor="Hillstone",
            standard_zone="dmz",
            role="border_firewall",
        )
    )

    first.zones.append(Zone(name="trust"))
    first.interfaces.append(Interface(name="GigabitEthernet1/0/1"))
    first.address_objects.append(AddressObject(name="web_server"))
    first.service_objects.append(ServiceObject(name="https"))
    first.policy_rules.append(PolicyRule(name="allow_https", action="permit"))
    first.nat_rules.append(NatRule(name="source_nat"))
    first.routes.append(Route(destination="0.0.0.0/0"))
    first.management_access.append(ManagementAccess(protocol="ssh"))
    first.logging.append(LoggingConfig(name="syslog"))
    first.unparsed_blocks.append(UnparsedBlock(block_type="unknown", content="raw block"))

    assert second.zones == []
    assert second.interfaces == []
    assert second.address_objects == []
    assert second.service_objects == []
    assert second.policy_rules == []
    assert second.nat_rules == []
    assert second.routes == []
    assert second.management_access == []
    assert second.logging == []
    assert second.unparsed_blocks == []


def test_config_template_default_collections_are_isolated_between_instances():
    first = ConfigTemplate(template_id="tpl-1", standard_zone="dmz", role="border_firewall")
    second = ConfigTemplate(template_id="tpl-2", standard_zone="dmz", role="border_firewall")

    first.source_configs.append("fw-1.cfg")
    first.required_modules.append("policy_rules")
    first.expected_patterns["policy_rules"] = {"default_deny": True}
    first.reference_baseline["zones"] = ["trust", "untrust"]
    first.vendor_overrides["H3C"] = {"policy_name": "security-policy"}

    assert second.source_configs == []
    assert second.required_modules == []
    assert second.expected_patterns == {}
    assert second.reference_baseline == {}
    assert second.vendor_overrides == {}


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        ("severity", "critical"),
        ("finding_type", "extra"),
    ],
)
def test_config_finding_rejects_invalid_literal_values(field_name, bad_value):
    finding_data = {
        "finding_id": "F-0002",
        "severity": "high",
        "module": "policy_rules",
        "finding_type": "missing",
        "expected": "存在默认拒绝策略",
        "actual": "未发现默认拒绝策略",
        "evidence": "policy_rules",
        "recommendation": "补充默认拒绝策略并开启日志",
    }

    finding_data[field_name] = bad_value

    with pytest.raises(ValidationError):
        ConfigFinding(**finding_data)
