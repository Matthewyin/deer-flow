import re

from core.model import (
    AddressObject,
    DeviceProfile,
    NormalizedConfig,
    PolicyRule,
    ServiceObject,
)
from core.normalize import clean_name, normalize_list, split_blocks


def parse_huawei_firewall(
    text: str,
    standard_zone: str,
    role: str,
    **profile_kwargs,
) -> NormalizedConfig:
    profile = DeviceProfile(
        vendor="Huawei",
        standard_zone=standard_zone,
        role=role,
        **profile_kwargs,
    )
    config = NormalizedConfig(device_profile=profile)

    for block in split_blocks(text):
        first_line = block.splitlines()[0].strip()
        if first_line.startswith("ip address-set "):
            config.address_objects.append(_parse_address_object(block))
        elif first_line.startswith("ip service-set "):
            config.service_objects.append(_parse_service_object(block))
        elif first_line == "security-policy":
            config.policy_rules.extend(_parse_policy_rules(block))

    return config


def _parse_address_object(block: str) -> AddressObject:
    lines = [line.strip() for line in block.splitlines()]
    name_match = re.match(r'ip address-set "?([^"]+)"? type object', lines[0])
    name = clean_name(name_match.group(1)) if name_match else lines[0]
    values: list[str] = []

    for line in lines[1:]:
        if match := re.match(r"address\s+\S+\s+(\S+)\s+mask\s+(\S+)", line):
            values.append(f"{clean_name(match.group(1))}/{clean_name(match.group(2))}")
        elif match := re.match(r"address\s+\S+\s+range\s+(\S+)\s+(\S+)", line):
            values.append(f"{clean_name(match.group(1))}-{clean_name(match.group(2))}")

    return AddressObject(name=name, values=values, object_type="ip", raw=block)


def _parse_service_object(block: str) -> ServiceObject:
    lines = [line.strip() for line in block.splitlines()]
    name_match = re.match(r'ip service-set "?([^"]+)"? type object', lines[0])
    name = clean_name(name_match.group(1)) if name_match else lines[0]
    protocol = ""
    ports: list[str] = []

    for line in lines[1:]:
        if match := re.match(r"service\s+\S+\s+protocol\s+(\S+)\s+destination-port\s+(\S+)", line):
            protocol = clean_name(match.group(1))
            ports.append(clean_name(match.group(2)))

    return ServiceObject(name=name, protocol=protocol, ports=ports, raw=block)


def _parse_policy_rules(block: str) -> list[PolicyRule]:
    rules: list[PolicyRule] = []
    current: list[str] = []

    for line in block.splitlines()[1:]:
        stripped = line.strip()
        if stripped.startswith("rule name "):
            if current:
                rules.append(_parse_policy_rule("\n".join(current)))
            current = [line.rstrip()]
        elif current:
            current.append(line.rstrip())

    if current:
        rules.append(_parse_policy_rule("\n".join(current)))

    return rules


def _parse_policy_rule(block: str) -> PolicyRule:
    lines = [line.strip() for line in block.splitlines()]
    name_match = re.match(r'rule name "?([^"]+)"?', lines[0])
    name = clean_name(name_match.group(1)) if name_match else lines[0]
    fields: dict[str, list[str]] = {}

    for line in lines[1:]:
        key, _, value = line.partition(" ")
        fields.setdefault(key, []).append(value)

    sources = [_strip_address_set(value) for value in fields.get("source-address", [])]
    destinations = [_strip_address_set(value) for value in fields.get("destination-address", [])]

    return PolicyRule(
        name=name,
        action=clean_name(_first(fields, "action")),
        source_zones=normalize_list(fields.get("source-zone")),
        destination_zones=normalize_list(fields.get("destination-zone")),
        source_objects=normalize_list(sources),
        destination_objects=normalize_list(destinations),
        services=normalize_list(fields.get("service")),
        raw=block,
    )


def _strip_address_set(value: str) -> str:
    if value.startswith("address-set "):
        return value.removeprefix("address-set ")
    return value


def _first(fields: dict[str, list[str]], key: str) -> str:
    values = fields.get(key, [])
    return values[0] if values else ""
