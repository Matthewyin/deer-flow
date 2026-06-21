import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parsers.h3c_firewall import parse_h3c_firewall  # noqa: E402
from parsers.hillstone_firewall import parse_hillstone_firewall  # noqa: E402
from parsers.huawei_firewall import parse_huawei_firewall  # noqa: E402


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text()


def test_parse_h3c_firewall_p0_modules():
    config = parse_h3c_firewall(
        read_fixture("h3c_firewall.cfg"),
        standard_zone="internet_edge",
        role="border_firewall",
    )

    assert config.device_profile.vendor == "H3C"
    assert [zone.name for zone in config.zones] == ["Trust", "Untrust"]
    assert config.address_objects[0].name == "WEB_SERVER"
    assert config.service_objects[0].ports == ["443"]
    assert config.policy_rules[0].name == "allow_https"
    assert config.policy_rules[0].logging is True


def test_parse_huawei_firewall_p0_modules():
    config = parse_huawei_firewall(
        read_fixture("huawei_firewall.cfg"),
        standard_zone="internet_edge",
        role="border_firewall",
    )

    assert config.device_profile.vendor == "Huawei"
    assert config.address_objects[0].values == ["10.0.0.10/32"]
    assert config.service_objects[0].name == "HTTPS"
    assert config.policy_rules[0].action == "permit"
    assert config.policy_rules[0].destination_objects == ["WEB_SERVER"]


def test_parse_hillstone_firewall_p0_modules():
    config = parse_hillstone_firewall(
        read_fixture("hillstone_firewall.cfg"),
        standard_zone="internet_edge",
        role="border_firewall",
    )

    assert config.device_profile.vendor == "Hillstone"
    assert config.zones[0].vrouter == "trust-vr"
    assert config.address_objects[0].values == ["10.0.0.10"]
    assert config.service_objects[0].ports == ["443"]
    assert config.policy_rules[0].source_zones == ["untrust"]
