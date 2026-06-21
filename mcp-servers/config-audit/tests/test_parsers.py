import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.normalize import bool_from_text, normalize_list  # noqa: E402
from parsers.h3c_firewall import parse_h3c_firewall  # noqa: E402
from parsers.hillstone_firewall import parse_hillstone_firewall  # noqa: E402
from parsers.huawei_firewall import parse_huawei_firewall  # noqa: E402


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text()


def test_normalize_helpers_cover_policy_terms_and_stable_lists():
    assert bool_from_text("permit") is True
    assert bool_from_text("pass") is True
    assert bool_from_text("enable") is True
    assert bool_from_text("deny") is False
    assert bool_from_text("drop") is False
    assert bool_from_text("disable") is False
    assert normalize_list(['"WEB_SERVER"', "", "WEB_SERVER", "'HTTPS'"]) == [
        "WEB_SERVER",
        "HTTPS",
    ]


def test_parse_h3c_firewall_p0_modules():
    config = parse_h3c_firewall(
        read_fixture("h3c_firewall.cfg"),
        standard_zone="internet_edge",
        role="border_firewall",
    )

    assert config.device_profile.vendor == "H3C"
    assert [zone.name for zone in config.zones] == ["Trust", "Untrust"]
    assert config.address_objects[0].name == "WEB_SERVER"
    assert config.address_objects[0].values == [
        "10.0.0.10",
        "10.0.1.0/24",
        "10.0.2.1-10.0.2.10",
    ]
    assert config.service_objects[0].ports == ["443"]
    assert config.policy_rules[0].name == "allow_https"
    assert config.policy_rules[0].logging is True
    assert config.policy_rules[0].source_zones == ["Untrust", "Trust"]
    assert config.policy_rules[0].destination_zones == ["Trust"]
    assert config.policy_rules[0].source_objects == ["any", "TRUST_CLIENT"]
    assert config.policy_rules[0].destination_objects == ["WEB_SERVER", "WEB_SERVER_BACKUP"]
    assert config.policy_rules[0].services == ["HTTPS", "HTTPS_BACKUP"]


def test_parse_huawei_firewall_p0_modules():
    config = parse_huawei_firewall(
        read_fixture("huawei_firewall.cfg"),
        standard_zone="internet_edge",
        role="border_firewall",
    )

    assert config.device_profile.vendor == "Huawei"
    assert config.address_objects[0].values == [
        "10.0.0.10/32",
        "10.0.1.1-10.0.1.10",
    ]
    assert config.service_objects[0].name == "HTTPS"
    assert config.policy_rules[0].action == "permit"
    assert config.policy_rules[0].source_objects == ["WEB_CLIENT"]
    assert config.policy_rules[0].destination_objects == ["WEB_SERVER"]


def test_parse_hillstone_firewall_p0_modules():
    config = parse_hillstone_firewall(
        read_fixture("hillstone_firewall.cfg"),
        standard_zone="dmz",
        role="border_firewall",
    )

    assert config.device_profile.vendor == "Hillstone"
    assert config.device_profile.standard_zone == "dmz"
    assert config.zones[0].vrouter == "trust-vr"
    assert config.address_objects[0].values == [
        "10.0.0.10",
        "10.0.0.11",
        "10.0.0.12-10.0.0.20",
    ]
    assert config.service_objects[0].ports == ["443"]
    assert config.policy_rules[0].source_zones == ["untrust"]
    assert config.policy_rules[0].source_objects == [
        "WEB_CLIENT",
        "10.0.0.20",
        "10.0.0.30-10.0.0.40",
    ]
    assert config.policy_rules[0].destination_objects == [
        "WEB_SERVER",
        "10.0.10.10",
        "10.0.10.20-10.0.10.30",
    ]
    assert config.policy_rules[0].enabled is False
