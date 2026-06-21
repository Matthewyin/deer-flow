from typing import Literal

from pydantic import BaseModel, Field


class DeviceProfile(BaseModel):
    device_name: str = ""
    vendor: str
    device_type: str = "firewall"
    model: str = ""
    os_version: str = ""
    site_name: str = ""
    local_area_name: str = ""
    standard_zone: str
    role: str


class Zone(BaseModel):
    name: str
    vrouter: str = ""
    vsys: str = "default"
    raw: str = ""


class Interface(BaseModel):
    name: str
    ip_addresses: list[str] = Field(default_factory=list)
    zone: str = ""
    status: str = ""
    raw: str = ""


class AddressObject(BaseModel):
    name: str
    values: list[str] = Field(default_factory=list)
    object_type: str = ""
    zone: str = ""
    members: list[str] = Field(default_factory=list)
    raw: str = ""


class ServiceObject(BaseModel):
    name: str
    protocol: str = ""
    ports: list[str] = Field(default_factory=list)
    members: list[str] = Field(default_factory=list)
    raw: str = ""


class PolicyRule(BaseModel):
    name: str
    action: str
    source_zones: list[str] = Field(default_factory=list)
    destination_zones: list[str] = Field(default_factory=list)
    source_objects: list[str] = Field(default_factory=list)
    destination_objects: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)
    logging: bool | None = None
    enabled: bool = True
    raw: str = ""


class NatRule(BaseModel):
    name: str
    nat_type: str = ""
    source: str = ""
    destination: str = ""
    translated: str = ""
    raw: str = ""


class Route(BaseModel):
    destination: str
    next_hop: str = ""
    interface: str = ""
    raw: str = ""


class ManagementAccess(BaseModel):
    protocol: str
    allowed_sources: list[str] = Field(default_factory=list)
    raw: str = ""


class LoggingConfig(BaseModel):
    name: str
    enabled: bool = True
    destination: str = ""
    raw: str = ""


class UnparsedBlock(BaseModel):
    block_type: str
    content: str
    reason: str = ""


class NormalizedConfig(BaseModel):
    device_profile: DeviceProfile
    zones: list[Zone] = Field(default_factory=list)
    interfaces: list[Interface] = Field(default_factory=list)
    address_objects: list[AddressObject] = Field(default_factory=list)
    service_objects: list[ServiceObject] = Field(default_factory=list)
    policy_rules: list[PolicyRule] = Field(default_factory=list)
    nat_rules: list[NatRule] = Field(default_factory=list)
    routes: list[Route] = Field(default_factory=list)
    management_access: list[ManagementAccess] = Field(default_factory=list)
    logging: list[LoggingConfig] = Field(default_factory=list)
    unparsed_blocks: list[UnparsedBlock] = Field(default_factory=list)


class ConfigTemplate(BaseModel):
    template_id: str
    device_type: str = "firewall"
    standard_zone: str
    role: str
    version: str = "1.0"
    status: Literal["draft", "approved"] = "draft"
    source_configs: list[str] = Field(default_factory=list)
    reviewed_by: str = ""
    reviewed_at: str = ""
    required_modules: list[str] = Field(default_factory=list)
    expected_patterns: dict[str, object] = Field(default_factory=dict)
    reference_baseline: dict[str, object] = Field(default_factory=dict)
    vendor_overrides: dict[str, object] = Field(default_factory=dict)


class ConfigFinding(BaseModel):
    finding_id: str
    severity: Literal["high", "medium", "low", "info"]
    module: str
    finding_type: Literal["missing", "mismatch", "risky", "unknown"]
    expected: str
    actual: str
    evidence: str
    llm_analysis: str = ""
    recommendation: str


class CompareResult(BaseModel):
    template_id: str
    findings: list[ConfigFinding] = Field(default_factory=list)
    matched: list[str] = Field(default_factory=list)


class ReportPaths(BaseModel):
    excel_path: str
    markdown_path: str
    present_filepaths: list[str] = Field(default_factory=list)
