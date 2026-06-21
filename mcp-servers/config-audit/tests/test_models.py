import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.model import (  # noqa: E402
    AddressObject,
    ConfigFinding,
    DeviceProfile,
    NormalizedConfig,
    PolicyRule,
    ServiceObject,
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
