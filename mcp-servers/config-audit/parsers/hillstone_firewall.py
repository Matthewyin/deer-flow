import re

from core.model import (
    AddressObject,
    DeviceProfile,
    NormalizedConfig,
    PolicyRule,
    ServiceObject,
    Zone,
)
from core.normalize import bool_from_text, clean_name, normalize_list


def parse_hillstone_firewall(
    text: str,
    standard_zone: str,
    role: str,
    **profile_kwargs,
) -> NormalizedConfig:
    profile = DeviceProfile(
        vendor="Hillstone",
        standard_zone=standard_zone,
        role=role,
        **profile_kwargs,
    )
    config = NormalizedConfig(device_profile=profile)

    for block in _split_hillstone_blocks(text):
        first_line = block.splitlines()[0].strip()
        if first_line.startswith("zone "):
            config.zones.append(_parse_zone(block))
        elif first_line.startswith("address "):
            config.address_objects.append(_parse_address_object(block))
        elif first_line.startswith("service "):
            config.service_objects.append(_parse_service_object(block))
        elif first_line.startswith("rule id "):
            config.policy_rules.append(_parse_policy_rule(block))

    return config


def _split_hillstone_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("zone ", "address ", "service ", "rule id ")) and current:
            blocks.append("\n".join(current).strip())
            current = []

        current.append(line.rstrip())
        if stripped == "exit":
            blocks.append("\n".join(current).strip())
            current = []

    if current:
        blocks.append("\n".join(current).strip())

    return [block for block in blocks if block]


def _parse_zone(block: str) -> Zone:
    first_line = block.splitlines()[0].strip()
    match = re.match(r'zone\s+"([^"]+)"\s+vrouter\s+"([^"]+)"', first_line)
    if not match:
        return Zone(name=clean_name(first_line), raw=block)
    return Zone(name=clean_name(match.group(1)), vrouter=clean_name(match.group(2)), raw=block)


def _parse_address_object(block: str) -> AddressObject:
    lines = [line.strip() for line in block.splitlines()]
    name = _quoted_name(lines[0])
    values: list[str] = []

    for line in lines[1:]:
        if line.startswith("host "):
            values.append(clean_name(line.removeprefix("host ")))

    return AddressObject(name=name, values=values, object_type="ip", raw=block)


def _parse_service_object(block: str) -> ServiceObject:
    lines = [line.strip() for line in block.splitlines()]
    name = _quoted_name(lines[0])
    protocol = ""
    ports: list[str] = []

    for line in lines[1:]:
        if match := re.match(r"(\S+)\s+dst-port\s+(\S+)", line):
            protocol = clean_name(match.group(1))
            ports.append(clean_name(match.group(2)))

    return ServiceObject(name=name, protocol=protocol, ports=ports, raw=block)


def _parse_policy_rule(block: str) -> PolicyRule:
    lines = [line.strip() for line in block.splitlines()]
    name = clean_name(lines[0].removeprefix("rule id "))
    fields: dict[str, str] = {}

    for line in lines[1:]:
        key, _, value = line.partition(" ")
        fields[key] = value

    if "name" in fields:
        name = clean_name(fields["name"])

    return PolicyRule(
        name=name,
        action=clean_name(fields.get("action", "")),
        source_zones=normalize_list(fields.get("src-zone")),
        destination_zones=normalize_list(fields.get("dst-zone")),
        destination_objects=normalize_list(fields.get("dst-addr")),
        services=normalize_list(fields.get("service")),
        logging=bool_from_text(fields.get("log", "")),
        raw=block,
    )


def _quoted_name(line: str) -> str:
    match = re.search(r'"([^"]+)"', line)
    return clean_name(match.group(1)) if match else clean_name(line)
