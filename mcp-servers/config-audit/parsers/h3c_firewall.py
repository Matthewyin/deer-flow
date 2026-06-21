import re

from core.model import (
    AddressObject,
    DeviceProfile,
    NormalizedConfig,
    PolicyRule,
    ServiceObject,
    Zone,
)
from core.normalize import bool_from_text, clean_name, normalize_list, split_blocks


def parse_h3c_firewall(
    text: str,
    standard_zone: str,
    role: str,
    **profile_kwargs,
) -> NormalizedConfig:
    profile = DeviceProfile(
        vendor="H3C",
        standard_zone=standard_zone,
        role=role,
        **profile_kwargs,
    )
    config = NormalizedConfig(device_profile=profile)

    for block in split_blocks(text):
        first_line = block.splitlines()[0].strip()
        if first_line.startswith("security-zone name "):
            config.zones.append(_parse_zone(block))
        elif first_line.startswith("object-group ip address "):
            config.address_objects.append(_parse_address_object(block))
        elif first_line.startswith("object-group service "):
            config.service_objects.append(_parse_service_object(block))
        elif first_line.startswith("rule "):
            config.policy_rules.append(_parse_policy_rule(block))

    return config


def _parse_zone(block: str) -> Zone:
    name = clean_name(block.splitlines()[0].removeprefix("security-zone name "))
    return Zone(name=name, raw=block)


def _parse_address_object(block: str) -> AddressObject:
    lines = [line.strip() for line in block.splitlines()]
    name = clean_name(lines[0].removeprefix("object-group ip address "))
    zone = ""
    values: list[str] = []

    for line in lines[1:]:
        if line.startswith("security-zone "):
            zone = clean_name(line.removeprefix("security-zone "))
        elif match := re.search(r"\bnetwork host address (\S+)", line):
            values.append(clean_name(match.group(1)))
        elif match := re.search(r"\bnetwork subnet(?: address)? (\S+) (\S+)", line):
            values.append(f"{clean_name(match.group(1))}/{clean_name(match.group(2))}")
        elif match := re.search(r"\bnetwork range (\S+) (\S+)", line):
            values.append(f"{clean_name(match.group(1))}-{clean_name(match.group(2))}")

    return AddressObject(name=name, values=values, object_type="ip", zone=zone, raw=block)


def _parse_service_object(block: str) -> ServiceObject:
    lines = [line.strip() for line in block.splitlines()]
    name = clean_name(lines[0].removeprefix("object-group service "))
    protocol = ""
    ports: list[str] = []

    for line in lines[1:]:
        if match := re.search(r"\bservice (\S+) destination eq (\S+)", line):
            protocol = clean_name(match.group(1))
            ports.append(clean_name(match.group(2)))

    return ServiceObject(name=name, protocol=protocol, ports=ports, raw=block)


def _parse_policy_rule(block: str) -> PolicyRule:
    lines = [line.strip() for line in block.splitlines()]
    header_match = re.match(r"rule\s+\S+\s+name\s+(.+)", lines[0])
    name = clean_name(header_match.group(1)) if header_match else lines[0]
    fields: dict[str, list[str]] = {}

    for line in lines[1:]:
        key, _, value = line.partition(" ")
        fields.setdefault(key, []).append(value)

    logging = bool_from_text(_first(fields, "logging"))

    return PolicyRule(
        name=name,
        action=clean_name(_first(fields, "action")),
        source_zones=normalize_list(fields.get("source-zone")),
        destination_zones=normalize_list(fields.get("destination-zone")),
        source_objects=normalize_list(fields.get("source-ip")),
        destination_objects=normalize_list(fields.get("destination-ip")),
        services=normalize_list(fields.get("service")),
        logging=logging,
        raw=block,
    )


def _first(fields: dict[str, list[str]], key: str) -> str:
    values = fields.get(key, [])
    return values[0] if values else ""
