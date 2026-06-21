# Config Audit Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a DeerFlow `config-audit` capability for firewall configuration parsing, template inference, standard checks, snippet checks, and report export.

**Architecture:** Add a new `config-audit` MCP server that owns deterministic parsing, normalization, template storage, comparison, and report export. Add a custom skill that forces the Agent to call MCP tools before doing LLM analysis. Create and validate a runtime custom Agent on an implementation branch, but do not commit ignored runtime `.deer-flow` state.

**Tech Stack:** Python 3, FastMCP, Pydantic, PyYAML, openpyxl, pytest, DeerFlow custom skills, DeerFlow MCP configuration.

---

## Implementation Rules

- Create implementation branch before code changes: `codex/config-audit-agent`.
- Keep `main` protected as the integration branch. Develop and test on the feature branch, then merge back to `main` only after tests pass.
- Do not commit `config.yaml`, `extensions_config.json`, `.env`, `backend/.deer-flow/`, `docker/volumes/`, or `.ssh/`.
- `skills/custom/...` is ignored in this repo. When adding `skills/custom/config-audit/SKILL.md`, stage it with `git add -f`.
- Use existing MCP pattern: `FastMCP` server in `mcp-servers/<name>/server.py`, tool modules expose `register(mcp)`.
- Keep LLM analysis outside MCP implementation. MCP returns facts, differences, and report files; Agent explains them.

## File Structure

Create:

- `mcp-servers/config-audit/server.py`  
  FastMCP entrypoint and tool registration.
- `mcp-servers/config-audit/requirements.txt`  
  MCP server runtime dependencies.
- `mcp-servers/config-audit/core/model.py`  
  Shared Pydantic models for device profile, normalized modules, findings, and report paths.
- `mcp-servers/config-audit/core/normalize.py`  
  Common helpers for vendor detection, list normalization, object normalization, and text block tracking.
- `mcp-servers/config-audit/core/template.py`  
  Draft template inference, approved template storage, loading, and validation.
- `mcp-servers/config-audit/core/compare.py`  
  Deterministic template-vs-config comparison and snippet checks.
- `mcp-servers/config-audit/core/export.py`  
  Excel and Markdown report generation.
- `mcp-servers/config-audit/parsers/h3c_firewall.py`  
  H3C firewall parser.
- `mcp-servers/config-audit/parsers/huawei_firewall.py`  
  Huawei firewall parser.
- `mcp-servers/config-audit/parsers/hillstone_firewall.py`  
  Hillstone firewall parser.
- `mcp-servers/config-audit/tools/parse_config.py`
- `mcp-servers/config-audit/tools/parse_snippet.py`
- `mcp-servers/config-audit/tools/infer_template.py`
- `mcp-servers/config-audit/tools/review_template.py`
- `mcp-servers/config-audit/tools/compare_config.py`
- `mcp-servers/config-audit/tools/check_snippet.py`
- `mcp-servers/config-audit/tools/export_report.py`
- `mcp-servers/config-audit/tests/fixtures/h3c_firewall.cfg`
- `mcp-servers/config-audit/tests/fixtures/huawei_firewall.cfg`
- `mcp-servers/config-audit/tests/fixtures/hillstone_firewall.cfg`
- `mcp-servers/config-audit/tests/test_models.py`
- `mcp-servers/config-audit/tests/test_parsers.py`
- `mcp-servers/config-audit/tests/test_template_compare.py`
- `mcp-servers/config-audit/tests/test_export.py`
- `skills/custom/config-audit/SKILL.md`
- `docs/config-audit-agent-runtime.md`

Modify:

- `extensions_config.example.json`  
  Add disabled `config-audit` MCP server example.

Runtime only, do not commit:

- `backend/.deer-flow/agents/config-audit/config.yaml`
- `backend/.deer-flow/agents/config-audit/SOUL.md`
- `backend/.deer-flow/config-audit/**`

---

### Task 1: Create Branch and Confirm Clean Base

**Files:**
- No code files.

- [ ] **Step 1: Confirm current branch and clean status**

Run:

```bash
git status --short --branch
```

Expected:

```text
## main...origin/main [ahead 1]
```

No uncommitted files should be listed.

- [ ] **Step 2: Create implementation branch**

Run:

```bash
git switch -c codex/config-audit-agent
```

Expected:

```text
Switched to a new branch 'codex/config-audit-agent'
```

- [ ] **Step 3: Confirm branch**

Run:

```bash
git status --short --branch
```

Expected:

```text
## codex/config-audit-agent
```

- [ ] **Step 4: Commit checkpoint**

No commit is needed for this task. Branch creation is the checkpoint.

---

### Task 2: Add MCP Server Skeleton

**Files:**
- Create: `mcp-servers/config-audit/server.py`
- Create: `mcp-servers/config-audit/requirements.txt`
- Create: `mcp-servers/config-audit/core/__init__.py`
- Create: `mcp-servers/config-audit/parsers/__init__.py`
- Create: `mcp-servers/config-audit/tools/__init__.py`
- Create: `mcp-servers/config-audit/tests/__init__.py`
- Modify: `extensions_config.example.json`

- [ ] **Step 1: Create minimal server file**

Create `mcp-servers/config-audit/server.py`:

```python
"""设备配置审查 MCP Server。"""

from fastmcp import FastMCP


mcp = FastMCP(
    "config-audit",
    instructions=(
        "设备配置审查工具集：解析防火墙完整配置和配置片段，"
        "反推标准模板，执行标准化对比，并导出 Excel 与 Markdown 报告。"
    ),
)


if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 2: Add requirements**

Create `mcp-servers/config-audit/requirements.txt`:

```text
fastmcp>=2.0
pydantic>=2.0
pyyaml>=6.0
openpyxl>=3.1
```

- [ ] **Step 3: Add package marker files**

Create these empty files:

```text
mcp-servers/config-audit/core/__init__.py
mcp-servers/config-audit/parsers/__init__.py
mcp-servers/config-audit/tools/__init__.py
mcp-servers/config-audit/tests/__init__.py
```

- [ ] **Step 4: Add extension example**

Modify `extensions_config.example.json` and add this disabled server inside `mcpServers`:

```json
"config-audit": {
  "enabled": false,
  "type": "stdio",
  "command": "/opt/venv/bin/python",
  "args": ["/app/mcp-servers/config-audit/server.py"],
  "env": {
    "CONFIG_AUDIT_DATA_DIR": "/app/backend/.deer-flow/config-audit",
    "CONFIG_AUDIT_OUTPUT_DIR": "/app/backend/.deer-flow/mcp-outputs/config-audit"
  },
  "description": "设备配置审查：防火墙配置解析、标准模板反推、配置差异检查、脚本片段检查和报告导出"
}
```

Keep the surrounding JSON valid.

- [ ] **Step 5: Smoke-test imports**

Run:

```bash
cd mcp-servers/config-audit && python3 -m py_compile server.py
```

Expected: command exits with status 0 and no output.

- [ ] **Step 6: Commit**

Run:

```bash
git add extensions_config.example.json mcp-servers/config-audit
git commit -m "feat: add config audit MCP skeleton"
```

---

### Task 3: Add Core Models

**Files:**
- Create: `mcp-servers/config-audit/core/model.py`
- Create: `mcp-servers/config-audit/tests/test_models.py`

- [ ] **Step 1: Write model tests**

Create `mcp-servers/config-audit/tests/test_models.py`:

```python
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
```

- [ ] **Step 2: Run model tests and verify failure**

Run:

```bash
python3 -m pytest mcp-servers/config-audit/tests/test_models.py -q
```

Expected: FAIL because `core.model` does not exist.

- [ ] **Step 3: Implement models**

Create `mcp-servers/config-audit/core/model.py`:

```python
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
```

- [ ] **Step 4: Run model tests**

Run:

```bash
python3 -m pytest mcp-servers/config-audit/tests/test_models.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit**

Run:

```bash
git add mcp-servers/config-audit/core/model.py mcp-servers/config-audit/tests/test_models.py
git commit -m "feat: add config audit core models"
```

---

### Task 4: Add Normalization Helpers and Vendor Parsers

**Files:**
- Create: `mcp-servers/config-audit/core/normalize.py`
- Create: `mcp-servers/config-audit/parsers/h3c_firewall.py`
- Create: `mcp-servers/config-audit/parsers/huawei_firewall.py`
- Create: `mcp-servers/config-audit/parsers/hillstone_firewall.py`
- Create: `mcp-servers/config-audit/tests/fixtures/h3c_firewall.cfg`
- Create: `mcp-servers/config-audit/tests/fixtures/huawei_firewall.cfg`
- Create: `mcp-servers/config-audit/tests/fixtures/hillstone_firewall.cfg`
- Create: `mcp-servers/config-audit/tests/test_parsers.py`

- [ ] **Step 1: Create focused parser fixtures**

Create `mcp-servers/config-audit/tests/fixtures/h3c_firewall.cfg`:

```text
security-zone name Trust
#
security-zone name Untrust
#
object-group ip address WEB_SERVER
 security-zone Trust
 0 network host address 10.0.0.10
#
object-group service HTTPS
 0 service tcp destination eq 443
#
rule 10 name allow_https
 source-zone Untrust
 destination-zone Trust
 source-ip any
 destination-ip WEB_SERVER
 service HTTPS
 action pass
 logging enable
#
```

Create `mcp-servers/config-audit/tests/fixtures/huawei_firewall.cfg`:

```text
ip address-set "WEB_SERVER" type object
 address 0 10.0.0.10 mask 32
#
ip service-set "HTTPS" type object
 service 0 protocol tcp destination-port 443
#
security-policy
 rule name "allow_https"
  source-zone untrust
  destination-zone trust
  destination-address address-set WEB_SERVER
  service HTTPS
  action permit
#
```

Create `mcp-servers/config-audit/tests/fixtures/hillstone_firewall.cfg`:

```text
zone "trust" vrouter "trust-vr"
zone "untrust" vrouter "untrust-vr"
address "WEB_SERVER"
 host 10.0.0.10
exit
service "HTTPS"
 tcp dst-port 443
exit
rule id 10
 name "allow_https"
 src-zone "untrust"
 dst-zone "trust"
 dst-addr "WEB_SERVER"
 service "HTTPS"
 action permit
 log enable
exit
```

- [ ] **Step 2: Write parser tests**

Create `mcp-servers/config-audit/tests/test_parsers.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parsers.h3c_firewall import parse_h3c_firewall  # noqa: E402
from parsers.hillstone_firewall import parse_hillstone_firewall  # noqa: E402
from parsers.huawei_firewall import parse_huawei_firewall  # noqa: E402


FIXTURES = Path(__file__).parent / "fixtures"


def test_h3c_parser_extracts_p0_modules():
    text = (FIXTURES / "h3c_firewall.cfg").read_text(encoding="utf-8")
    result = parse_h3c_firewall(text, standard_zone="internet_edge", role="border_firewall")

    assert result.device_profile.vendor == "H3C"
    assert [zone.name for zone in result.zones] == ["Trust", "Untrust"]
    assert result.address_objects[0].name == "WEB_SERVER"
    assert result.service_objects[0].ports == ["443"]
    assert result.policy_rules[0].name == "allow_https"
    assert result.policy_rules[0].logging is True


def test_huawei_parser_extracts_p0_modules():
    text = (FIXTURES / "huawei_firewall.cfg").read_text(encoding="utf-8")
    result = parse_huawei_firewall(text, standard_zone="internet_edge", role="border_firewall")

    assert result.device_profile.vendor == "Huawei"
    assert result.address_objects[0].values == ["10.0.0.10/32"]
    assert result.service_objects[0].name == "HTTPS"
    assert result.policy_rules[0].action == "permit"
    assert result.policy_rules[0].destination_objects == ["WEB_SERVER"]


def test_hillstone_parser_extracts_p0_modules():
    text = (FIXTURES / "hillstone_firewall.cfg").read_text(encoding="utf-8")
    result = parse_hillstone_firewall(text, standard_zone="dmz", role="border_firewall")

    assert result.device_profile.vendor == "Hillstone"
    assert result.zones[0].vrouter == "trust-vr"
    assert result.address_objects[0].values == ["10.0.0.10"]
    assert result.service_objects[0].ports == ["443"]
    assert result.policy_rules[0].source_zones == ["untrust"]
```

- [ ] **Step 3: Run parser tests and verify failure**

Run:

```bash
python3 -m pytest mcp-servers/config-audit/tests/test_parsers.py -q
```

Expected: FAIL because parser modules do not exist.

- [ ] **Step 4: Implement normalization helpers**

Create `mcp-servers/config-audit/core/normalize.py`:

```python
import re


def clean_name(value: str) -> str:
    return value.strip().strip('"').strip("'")


def split_blocks(text: str) -> list[str]:
    blocks = [block.strip() for block in re.split(r"\n#\s*\n?", text) if block.strip()]
    return blocks if blocks else [text.strip()]


def bool_from_text(value: str) -> bool | None:
    lowered = value.lower()
    if any(token in lowered for token in ("enable", "permit", "pass", "true", "yes")):
        return True
    if any(token in lowered for token in ("disable", "deny", "drop", "false", "no")):
        return False
    return None


def normalize_list(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        cleaned = clean_name(value)
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result
```

- [ ] **Step 5: Implement H3C parser**

Create `mcp-servers/config-audit/parsers/h3c_firewall.py`:

```python
import re

from core.model import AddressObject, DeviceProfile, NormalizedConfig, PolicyRule, ServiceObject, Zone
from core.normalize import clean_name, normalize_list, split_blocks


def parse_h3c_firewall(text: str, standard_zone: str, role: str, **profile_kwargs) -> NormalizedConfig:
    profile = DeviceProfile(vendor="H3C", standard_zone=standard_zone, role=role, **profile_kwargs)
    zones: list[Zone] = []
    addresses: list[AddressObject] = []
    services: list[ServiceObject] = []
    policies: list[PolicyRule] = []

    for block in split_blocks(text):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        header = lines[0]

        zone_match = re.match(r"security-zone name (\S+)", header)
        if zone_match:
            zones.append(Zone(name=clean_name(zone_match.group(1)), raw=block))
            continue

        address_match = re.match(r"object-group ip address (.+)", header)
        if address_match:
            name = clean_name(address_match.group(1))
            zone = ""
            values: list[str] = []
            for line in lines[1:]:
                if line.startswith("security-zone "):
                    zone = clean_name(line.split(None, 1)[1])
                elif "network host address" in line:
                    values.append(line.split()[-1])
                elif "network subnet" in line:
                    parts = line.split()
                    values.append(f"{parts[-2]} {parts[-1]}")
                elif "network range" in line:
                    parts = line.split()
                    values.append(f"{parts[-2]} {parts[-1]}")
            addresses.append(AddressObject(name=name, values=normalize_list(values), zone=zone, raw=block))
            continue

        service_match = re.match(r"object-group service (.+)", header)
        if service_match:
            name = clean_name(service_match.group(1))
            ports: list[str] = []
            protocol = ""
            for line in lines[1:]:
                match = re.search(r"service (tcp|udp) destination (?:eq|range) (.+)", line)
                if match:
                    protocol = match.group(1)
                    ports.append(match.group(2).strip())
            services.append(ServiceObject(name=name, protocol=protocol, ports=normalize_list(ports), raw=block))
            continue

        rule_match = re.match(r"rule (\d+) name (.+)", header)
        if rule_match:
            rule_name = clean_name(rule_match.group(2))
            values: dict[str, list[str] | str | bool | None] = {
                "source_zones": [],
                "destination_zones": [],
                "source_objects": [],
                "destination_objects": [],
                "services": [],
                "action": "drop",
                "logging": None,
                "enabled": True,
            }
            for line in lines[1:]:
                if line.startswith("source-zone "):
                    values["source_zones"].append(line.split(None, 1)[1])  # type: ignore[union-attr]
                elif line.startswith("destination-zone "):
                    values["destination_zones"].append(line.split(None, 1)[1])  # type: ignore[union-attr]
                elif line.startswith("source-ip "):
                    values["source_objects"].append(line.split(None, 1)[1])  # type: ignore[union-attr]
                elif line.startswith("destination-ip "):
                    values["destination_objects"].append(line.split(None, 1)[1])  # type: ignore[union-attr]
                elif line.startswith("service "):
                    values["services"].append(line.split(None, 1)[1])  # type: ignore[union-attr]
                elif line.startswith("action "):
                    values["action"] = line.split(None, 1)[1]
                elif line.startswith("logging "):
                    values["logging"] = "enable" in line.lower()
                elif line == "disable":
                    values["enabled"] = False
            policies.append(
                PolicyRule(
                    name=rule_name,
                    action=str(values["action"]),
                    source_zones=normalize_list(values["source_zones"]),  # type: ignore[arg-type]
                    destination_zones=normalize_list(values["destination_zones"]),  # type: ignore[arg-type]
                    source_objects=normalize_list(values["source_objects"]),  # type: ignore[arg-type]
                    destination_objects=normalize_list(values["destination_objects"]),  # type: ignore[arg-type]
                    services=normalize_list(values["services"]),  # type: ignore[arg-type]
                    logging=values["logging"],  # type: ignore[arg-type]
                    enabled=bool(values["enabled"]),
                    raw=block,
                )
            )

    return NormalizedConfig(
        device_profile=profile,
        zones=zones,
        address_objects=addresses,
        service_objects=services,
        policy_rules=policies,
    )
```

- [ ] **Step 6: Implement Huawei parser**

Create `mcp-servers/config-audit/parsers/huawei_firewall.py`:

```python
import re

from core.model import AddressObject, DeviceProfile, NormalizedConfig, PolicyRule, ServiceObject
from core.normalize import clean_name, normalize_list, split_blocks


def parse_huawei_firewall(text: str, standard_zone: str, role: str, **profile_kwargs) -> NormalizedConfig:
    profile = DeviceProfile(vendor="Huawei", standard_zone=standard_zone, role=role, **profile_kwargs)
    addresses: list[AddressObject] = []
    services: list[ServiceObject] = []
    policies: list[PolicyRule] = []

    for block in split_blocks(text):
        lines = [line.rstrip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        header = lines[0].strip()

        address_match = re.match(r'ip address-set "?([^"]+)"? type (\S+)', header)
        if address_match:
            values: list[str] = []
            members: list[str] = []
            for line in lines[1:]:
                stripped = line.strip()
                if stripped.startswith("address ") and " mask " in stripped:
                    parts = stripped.split()
                    values.append(f"{parts[2]}/{parts[4]}")
                elif stripped.startswith("address ") and " range " in stripped:
                    parts = stripped.split()
                    values.append(f"{parts[3]} {parts[4]}")
                elif "address-set" in stripped:
                    members.append(stripped.split()[-1])
            addresses.append(
                AddressObject(
                    name=clean_name(address_match.group(1)),
                    object_type=address_match.group(2),
                    values=normalize_list(values),
                    members=normalize_list(members),
                    raw=block,
                )
            )
            continue

        service_match = re.match(r'ip service-set "?([^"]+)"? type (\S+)', header)
        if service_match:
            ports: list[str] = []
            protocol = ""
            for line in lines[1:]:
                stripped = line.strip()
                match = re.search(r"protocol (tcp|udp) destination-port (.+)", stripped)
                if match:
                    protocol = match.group(1)
                    ports.append(match.group(2))
            services.append(ServiceObject(name=clean_name(service_match.group(1)), protocol=protocol, ports=normalize_list(ports), raw=block))
            continue

        if header == "security-policy":
            current: dict[str, object] | None = None
            current_raw: list[str] = []
            for raw_line in lines[1:]:
                line = raw_line.strip()
                if line.startswith("rule name"):
                    if current:
                        policies.append(_policy_from_dict(current, "\n".join(current_raw)))
                    current = {
                        "name": clean_name(line.split("rule name", 1)[1]),
                        "action": "drop",
                        "source_zones": [],
                        "destination_zones": [],
                        "source_objects": [],
                        "destination_objects": [],
                        "services": [],
                    }
                    current_raw = [raw_line]
                elif current:
                    current_raw.append(raw_line)
                    if line.startswith("source-zone "):
                        current["source_zones"].append(line.split()[-1])  # type: ignore[union-attr]
                    elif line.startswith("destination-zone "):
                        current["destination_zones"].append(line.split()[-1])  # type: ignore[union-attr]
                    elif "source-address address-set" in line:
                        current["source_objects"].append(line.split()[-1])  # type: ignore[union-attr]
                    elif "destination-address address-set" in line:
                        current["destination_objects"].append(line.split()[-1])  # type: ignore[union-attr]
                    elif line.startswith("service "):
                        current["services"].append(line.split()[-1])  # type: ignore[union-attr]
                    elif line.startswith("action "):
                        current["action"] = line.split()[-1]
            if current:
                policies.append(_policy_from_dict(current, "\n".join(current_raw)))

    return NormalizedConfig(device_profile=profile, address_objects=addresses, service_objects=services, policy_rules=policies)


def _policy_from_dict(data: dict[str, object], raw: str) -> PolicyRule:
    return PolicyRule(
        name=str(data["name"]),
        action=str(data["action"]),
        source_zones=normalize_list(data["source_zones"]),  # type: ignore[arg-type]
        destination_zones=normalize_list(data["destination_zones"]),  # type: ignore[arg-type]
        source_objects=normalize_list(data["source_objects"]),  # type: ignore[arg-type]
        destination_objects=normalize_list(data["destination_objects"]),  # type: ignore[arg-type]
        services=normalize_list(data["services"]),  # type: ignore[arg-type]
        logging=None,
        raw=raw,
    )
```

- [ ] **Step 7: Implement Hillstone parser**

Create `mcp-servers/config-audit/parsers/hillstone_firewall.py`:

```python
import re

from core.model import AddressObject, DeviceProfile, NormalizedConfig, PolicyRule, ServiceObject, Zone
from core.normalize import clean_name, normalize_list


def parse_hillstone_firewall(text: str, standard_zone: str, role: str, **profile_kwargs) -> NormalizedConfig:
    profile = DeviceProfile(vendor="Hillstone", standard_zone=standard_zone, role=role, **profile_kwargs)
    zones: list[Zone] = []
    addresses: list[AddressObject] = []
    services: list[ServiceObject] = []
    policies: list[PolicyRule] = []

    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()

        zone_match = re.match(r'zone "(.+)"\s+vrouter "(.+)"', line)
        if zone_match:
            zones.append(Zone(name=zone_match.group(1), vrouter=zone_match.group(2), raw=line))
            index += 1
            continue

        if line.startswith("address "):
            name = clean_name(line.split(" ", 1)[1])
            block = [line]
            values: list[str] = []
            index += 1
            while index < len(lines) and lines[index].strip() != "exit":
                current = lines[index].strip()
                block.append(current)
                if current.startswith(("host ", "ip ", "range ")):
                    values.append(current.split(" ", 1)[1])
                index += 1
            addresses.append(AddressObject(name=name, values=normalize_list(values), raw="\n".join(block)))

        elif line.startswith("service "):
            name = clean_name(line.split(" ", 1)[1])
            block = [line]
            protocol = ""
            ports: list[str] = []
            index += 1
            while index < len(lines) and lines[index].strip() != "exit":
                current = lines[index].strip()
                block.append(current)
                if current.startswith(("tcp ", "udp ")):
                    parts = current.split()
                    protocol = parts[0]
                    ports.append(parts[-1])
                index += 1
            services.append(ServiceObject(name=name, protocol=protocol, ports=normalize_list(ports), raw="\n".join(block)))

        elif line.startswith("rule id "):
            rule_id = line.split()[-1]
            block = [line]
            data: dict[str, object] = {
                "name": rule_id,
                "action": "drop",
                "source_zones": [],
                "destination_zones": [],
                "source_objects": [],
                "destination_objects": [],
                "services": [],
                "logging": None,
                "enabled": True,
            }
            index += 1
            while index < len(lines) and lines[index].strip() != "exit":
                current = lines[index].strip()
                block.append(current)
                if current.startswith("name "):
                    data["name"] = clean_name(current.split(" ", 1)[1])
                elif current.startswith("src-zone "):
                    data["source_zones"].append(current.split(" ", 1)[1])  # type: ignore[union-attr]
                elif current.startswith("dst-zone "):
                    data["destination_zones"].append(current.split(" ", 1)[1])  # type: ignore[union-attr]
                elif current.startswith(("src-addr ", "src-ip ", "src-range ")):
                    data["source_objects"].append(current.split(" ", 1)[1])  # type: ignore[union-attr]
                elif current.startswith(("dst-addr ", "dst-ip ", "dst-range ")):
                    data["destination_objects"].append(current.split(" ", 1)[1])  # type: ignore[union-attr]
                elif current.startswith("service "):
                    data["services"].append(current.split(" ", 1)[1])  # type: ignore[union-attr]
                elif current.startswith("action "):
                    data["action"] = current.split(" ", 1)[1]
                elif current.startswith("log "):
                    data["logging"] = "enable" in current.lower()
                elif current == "disable":
                    data["enabled"] = False
                index += 1
            policies.append(
                PolicyRule(
                    name=str(data["name"]),
                    action=str(data["action"]),
                    source_zones=normalize_list(data["source_zones"]),  # type: ignore[arg-type]
                    destination_zones=normalize_list(data["destination_zones"]),  # type: ignore[arg-type]
                    source_objects=normalize_list(data["source_objects"]),  # type: ignore[arg-type]
                    destination_objects=normalize_list(data["destination_objects"]),  # type: ignore[arg-type]
                    services=normalize_list(data["services"]),  # type: ignore[arg-type]
                    logging=data["logging"],  # type: ignore[arg-type]
                    enabled=bool(data["enabled"]),
                    raw="\n".join(block),
                )
            )

        index += 1

    return NormalizedConfig(device_profile=profile, zones=zones, address_objects=addresses, service_objects=services, policy_rules=policies)
```

- [ ] **Step 8: Run parser tests**

Run:

```bash
python3 -m pytest mcp-servers/config-audit/tests/test_parsers.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 9: Commit**

Run:

```bash
git add mcp-servers/config-audit/core/normalize.py mcp-servers/config-audit/parsers mcp-servers/config-audit/tests
git commit -m "feat: parse firewall config modules"
```

---

### Task 5: Add Template Inference and Review

**Files:**
- Create: `mcp-servers/config-audit/core/template.py`
- Create: `mcp-servers/config-audit/tests/test_template_compare.py`

- [ ] **Step 1: Write template tests**

Create `mcp-servers/config-audit/tests/test_template_compare.py` with template tests first:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.compare import compare_config_to_template  # noqa: E402
from core.model import AddressObject, ConfigTemplate, DeviceProfile, NormalizedConfig, PolicyRule, ServiceObject, Zone  # noqa: E402
from core.template import infer_template, save_approved_template  # noqa: E402


def _sample_config() -> NormalizedConfig:
    return NormalizedConfig(
        device_profile=DeviceProfile(vendor="H3C", standard_zone="internet_edge", role="border_firewall"),
        zones=[Zone(name="Trust"), Zone(name="Untrust")],
        address_objects=[AddressObject(name="WEB_SERVER", values=["10.0.0.10"])],
        service_objects=[ServiceObject(name="HTTPS", protocol="tcp", ports=["443"])],
        policy_rules=[
            PolicyRule(
                name="allow_https",
                action="permit",
                source_zones=["Untrust"],
                destination_zones=["Trust"],
                destination_objects=["WEB_SERVER"],
                services=["HTTPS"],
                logging=True,
            )
        ],
    )


def test_infer_template_creates_draft_from_config():
    template = infer_template([_sample_config()], standard_zone="internet_edge", role="border_firewall")

    assert template.status == "draft"
    assert template.template_id == "firewall.internet_edge.border_firewall"
    assert "zones" in template.required_modules
    assert template.expected_patterns["policy_rules"]["require_logging"] is True


def test_save_approved_template_writes_yaml(tmp_path):
    draft = infer_template([_sample_config()], standard_zone="internet_edge", role="border_firewall")
    saved_path = save_approved_template(draft, tmp_path, reviewed_by="ops")

    assert saved_path.name == "border_firewall.yaml"
    assert "status: approved" in saved_path.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run template tests and verify failure**

Run:

```bash
python3 -m pytest mcp-servers/config-audit/tests/test_template_compare.py::test_infer_template_creates_draft_from_config mcp-servers/config-audit/tests/test_template_compare.py::test_save_approved_template_writes_yaml -q
```

Expected: FAIL because `core.template` does not exist.

- [ ] **Step 3: Implement template module**

Create `mcp-servers/config-audit/core/template.py`:

```python
from datetime import datetime, timezone
from pathlib import Path

import yaml

from core.model import ConfigTemplate, NormalizedConfig


P0_MODULES = ["zones", "address_objects", "service_objects", "policy_rules"]


def infer_template(configs: list[NormalizedConfig], standard_zone: str, role: str) -> ConfigTemplate:
    if not configs:
        raise ValueError("至少需要一份认可配置才能反推模板")

    required_modules = [module for module in P0_MODULES if all(getattr(config, module) for config in configs)]
    require_logging = any(
        rule.logging is True
        for config in configs
        for rule in config.policy_rules
    )
    baseline = {
        "zone_names": sorted({zone.name for config in configs for zone in config.zones}),
        "service_names": sorted({service.name for config in configs for service in config.service_objects}),
        "address_object_names": sorted({address.name for config in configs for address in config.address_objects}),
    }

    return ConfigTemplate(
        template_id=f"firewall.{standard_zone}.{role}",
        standard_zone=standard_zone,
        role=role,
        status="draft",
        source_configs=[config.device_profile.device_name for config in configs if config.device_profile.device_name],
        required_modules=required_modules,
        expected_patterns={
            "policy_rules": {
                "require_logging": require_logging,
                "forbid_any_to_any_permit": True,
            },
            "management_access": {
                "forbid_any_source": True,
            },
        },
        reference_baseline=baseline,
    )


def save_approved_template(template: ConfigTemplate, base_dir: str | Path, reviewed_by: str) -> Path:
    approved = template.model_copy(
        update={
            "status": "approved",
            "reviewed_by": reviewed_by,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    output_dir = Path(base_dir) / approved.device_type / approved.standard_zone
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{approved.role}.yaml"
    output_path.write_text(
        yaml.safe_dump(approved.model_dump(), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return output_path


def load_template(path: str | Path) -> ConfigTemplate:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return ConfigTemplate(**data)
```

- [ ] **Step 4: Run template tests**

Run:

```bash
python3 -m pytest mcp-servers/config-audit/tests/test_template_compare.py::test_infer_template_creates_draft_from_config mcp-servers/config-audit/tests/test_template_compare.py::test_save_approved_template_writes_yaml -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit**

Run:

```bash
git add mcp-servers/config-audit/core/template.py mcp-servers/config-audit/tests/test_template_compare.py
git commit -m "feat: infer and approve config templates"
```

---

### Task 6: Add Config Compare and Snippet Check

**Files:**
- Create: `mcp-servers/config-audit/core/compare.py`
- Modify: `mcp-servers/config-audit/tests/test_template_compare.py`

- [ ] **Step 1: Append compare tests**

Append to `mcp-servers/config-audit/tests/test_template_compare.py`:

```python
def test_compare_reports_missing_required_module():
    config = _sample_config().model_copy(update={"policy_rules": []})
    template = ConfigTemplate(
        template_id="firewall.internet_edge.border_firewall",
        standard_zone="internet_edge",
        role="border_firewall",
        status="approved",
        required_modules=["zones", "address_objects", "service_objects", "policy_rules"],
        expected_patterns={"policy_rules": {"require_logging": True, "forbid_any_to_any_permit": True}},
    )

    result = compare_config_to_template(config, template)

    assert result.findings[0].module == "policy_rules"
    assert result.findings[0].finding_type == "missing"


def test_compare_reports_policy_without_logging():
    config = _sample_config()
    config.policy_rules[0].logging = False
    template = ConfigTemplate(
        template_id="firewall.internet_edge.border_firewall",
        standard_zone="internet_edge",
        role="border_firewall",
        status="approved",
        required_modules=["policy_rules"],
        expected_patterns={"policy_rules": {"require_logging": True, "forbid_any_to_any_permit": True}},
    )

    result = compare_config_to_template(config, template)

    assert result.findings[0].severity == "medium"
    assert "日志" in result.findings[0].recommendation
```

- [ ] **Step 2: Run compare tests and verify failure**

Run:

```bash
python3 -m pytest mcp-servers/config-audit/tests/test_template_compare.py -q
```

Expected: FAIL because `core.compare` does not exist.

- [ ] **Step 3: Implement compare module**

Create `mcp-servers/config-audit/core/compare.py`:

```python
from core.model import CompareResult, ConfigFinding, ConfigTemplate, NormalizedConfig, PolicyRule


def compare_config_to_template(config: NormalizedConfig, template: ConfigTemplate) -> CompareResult:
    findings: list[ConfigFinding] = []
    matched: list[str] = []

    for module in template.required_modules:
        value = getattr(config, module, None)
        if not value:
            findings.append(
                _finding(
                    len(findings) + 1,
                    severity="high",
                    module=module,
                    finding_type="missing",
                    expected=f"模块 {module} 必须存在",
                    actual=f"模块 {module} 为空或未解析",
                    evidence=module,
                    recommendation=f"补充或修正 {module} 相关配置",
                )
            )
        else:
            matched.append(module)

    policy_patterns = template.expected_patterns.get("policy_rules", {})
    if policy_patterns.get("require_logging"):
        for rule in config.policy_rules:
            if rule.logging is False:
                findings.append(
                    _finding(
                        len(findings) + 1,
                        severity="medium",
                        module="policy_rules",
                        finding_type="risky",
                        expected="安全策略应开启日志",
                        actual=f"策略 {rule.name} 未开启日志",
                        evidence=rule.raw or rule.name,
                        recommendation="为该策略开启日志，便于审计和故障回溯",
                    )
                )

    if policy_patterns.get("forbid_any_to_any_permit"):
        for rule in config.policy_rules:
            if _is_any_to_any_permit(rule):
                findings.append(
                    _finding(
                        len(findings) + 1,
                        severity="high",
                        module="policy_rules",
                        finding_type="risky",
                        expected="不应存在 any 到 any 的放通策略",
                        actual=f"策略 {rule.name} 可能全放通",
                        evidence=rule.raw or rule.name,
                        recommendation="收敛源、目的和服务范围，避免全放通",
                    )
                )

    return CompareResult(template_id=template.template_id, findings=findings, matched=matched)


def check_snippet_against_template(snippet: NormalizedConfig, template: ConfigTemplate, current: NormalizedConfig | None = None) -> CompareResult:
    result = compare_config_to_template(snippet, template)
    if current is None:
        result.findings.append(
            _finding(
                len(result.findings) + 1,
                severity="info",
                module="snippet",
                finding_type="unknown",
                expected="提供当前完整配置以进行强判断",
                actual="当前仅提供配置片段",
                evidence="snippet",
                recommendation="将当前完整配置一并提供，确认片段是否缺少上下文依赖",
            )
        )
    return result


def _is_any_to_any_permit(rule: PolicyRule) -> bool:
    action = rule.action.lower()
    if action not in {"permit", "pass", "allow"}:
        return False
    src_any = not rule.source_objects or "any" in {item.lower() for item in rule.source_objects}
    dst_any = not rule.destination_objects or "any" in {item.lower() for item in rule.destination_objects}
    svc_any = not rule.services or "any" in {item.lower() for item in rule.services}
    return src_any and dst_any and svc_any


def _finding(
    index: int,
    severity: str,
    module: str,
    finding_type: str,
    expected: str,
    actual: str,
    evidence: str,
    recommendation: str,
) -> ConfigFinding:
    return ConfigFinding(
        finding_id=f"F-{index:04d}",
        severity=severity,
        module=module,
        finding_type=finding_type,
        expected=expected,
        actual=actual,
        evidence=evidence,
        recommendation=recommendation,
    )
```

- [ ] **Step 4: Run compare tests**

Run:

```bash
python3 -m pytest mcp-servers/config-audit/tests/test_template_compare.py -q
```

Expected:

```text
4 passed
```

- [ ] **Step 5: Commit**

Run:

```bash
git add mcp-servers/config-audit/core/compare.py mcp-servers/config-audit/tests/test_template_compare.py
git commit -m "feat: compare configs with approved templates"
```

---

### Task 7: Add Report Export

**Files:**
- Create: `mcp-servers/config-audit/core/export.py`
- Create: `mcp-servers/config-audit/tests/test_export.py`

- [ ] **Step 1: Write export tests**

Create `mcp-servers/config-audit/tests/test_export.py`:

```python
import sys
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.compare import compare_config_to_template  # noqa: E402
from core.export import export_report  # noqa: E402
from core.model import AddressObject, ConfigTemplate, DeviceProfile, NormalizedConfig, PolicyRule, ServiceObject, Zone  # noqa: E402


def test_export_report_writes_excel_and_markdown(tmp_path):
    config = NormalizedConfig(
        device_profile=DeviceProfile(vendor="H3C", standard_zone="internet_edge", role="border_firewall"),
        zones=[Zone(name="Trust")],
        address_objects=[AddressObject(name="WEB_SERVER", values=["10.0.0.10"])],
        service_objects=[ServiceObject(name="HTTPS", protocol="tcp", ports=["443"])],
        policy_rules=[PolicyRule(name="allow_https", action="permit", logging=False)],
    )
    template = ConfigTemplate(
        template_id="firewall.internet_edge.border_firewall",
        standard_zone="internet_edge",
        role="border_firewall",
        status="approved",
        required_modules=["zones", "policy_rules"],
        expected_patterns={"policy_rules": {"require_logging": True}},
    )
    compare = compare_config_to_template(config, template)

    paths = export_report(config, compare, tmp_path, agent_analysis="策略日志存在缺失。")

    assert Path(paths.excel_path).exists()
    assert Path(paths.markdown_path).exists()
    assert "策略日志存在缺失" in Path(paths.markdown_path).read_text(encoding="utf-8")

    workbook = openpyxl.load_workbook(paths.excel_path)
    assert "device_profile" in workbook.sheetnames
    assert "findings" in workbook.sheetnames
```

- [ ] **Step 2: Run export test and verify failure**

Run:

```bash
python3 -m pytest mcp-servers/config-audit/tests/test_export.py -q
```

Expected: FAIL because `core.export` does not exist.

- [ ] **Step 3: Implement export module**

Create `mcp-servers/config-audit/core/export.py`:

```python
import uuid
from pathlib import Path

from openpyxl import Workbook

from core.model import CompareResult, NormalizedConfig, ReportPaths


SHEETS = [
    "device_profile",
    "zones",
    "interfaces",
    "address_objects",
    "service_objects",
    "policy_rules",
    "nat_rules",
    "routes",
    "management_access",
    "logging",
    "unparsed_blocks",
    "findings",
]


def export_report(config: NormalizedConfig, compare: CompareResult, output_dir: str | Path, agent_analysis: str = "") -> ReportPaths:
    artifact_id = uuid.uuid4().hex
    base = Path(output_dir) / artifact_id
    base.mkdir(parents=True, exist_ok=True)

    excel_path = base / "配置审查事实表.xlsx"
    markdown_path = base / "配置审查报告.md"

    _write_excel(config, compare, excel_path)
    _write_markdown(config, compare, markdown_path, agent_analysis)

    return ReportPaths(
        excel_path=str(excel_path),
        markdown_path=str(markdown_path),
        present_filepaths=[str(excel_path), str(markdown_path)],
    )


def _write_excel(config: NormalizedConfig, compare: CompareResult, path: Path) -> None:
    wb = Workbook()
    wb.remove(wb.active)

    for sheet in SHEETS:
        ws = wb.create_sheet(sheet)
        rows = _rows_for_sheet(config, compare, sheet)
        for row in rows:
            ws.append(row)
        ws.freeze_panes = "A2"

    wb.save(path)


def _rows_for_sheet(config: NormalizedConfig, compare: CompareResult, sheet: str) -> list[list[object]]:
    if sheet == "device_profile":
        data = config.device_profile.model_dump()
        return [["field", "value"], *[[key, value] for key, value in data.items()]]
    if sheet == "findings":
        header = ["finding_id", "severity", "module", "finding_type", "expected", "actual", "evidence", "llm_analysis", "recommendation"]
        return [header, *[[getattr(item, field) for field in header] for item in compare.findings]]

    values = getattr(config, sheet)
    if not values:
        return [["empty"]]

    first = values[0].model_dump()
    header = list(first.keys())
    return [header, *[[item.model_dump().get(field, "") for field in header] for item in values]]


def _write_markdown(config: NormalizedConfig, compare: CompareResult, path: Path, agent_analysis: str) -> None:
    profile = config.device_profile
    lines = [
        "# 配置审查报告",
        "",
        "## 结论摘要",
        f"- 发现问题数：{len(compare.findings)}",
        f"- 标准模板：{compare.template_id}",
        "",
        "## 设备画像",
        f"- 厂商：{profile.vendor}",
        f"- 设备类型：{profile.device_type}",
        f"- 标准分类：{profile.standard_zone}",
        f"- 角色：{profile.role}",
        "",
        "## 配置模块统计",
        f"- 安全域：{len(config.zones)}",
        f"- 地址对象：{len(config.address_objects)}",
        f"- 服务对象：{len(config.service_objects)}",
        f"- 策略规则：{len(config.policy_rules)}",
        "",
        "## 关键缺失项",
    ]
    missing = [finding for finding in compare.findings if finding.finding_type == "missing"]
    lines.extend(_finding_lines(missing))
    lines.extend(["", "## 异常与风险项"])
    risky = [finding for finding in compare.findings if finding.finding_type != "missing"]
    lines.extend(_finding_lines(risky))
    lines.extend(["", "## LLM 分析说明", agent_analysis or "未提供额外 LLM 分析。", "", "## 整改建议"])
    lines.extend([f"- {finding.recommendation}" for finding in compare.findings] or ["- 当前未发现需要整改的配置项。"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _finding_lines(findings) -> list[str]:
    if not findings:
        return ["- 未发现。"]
    return [f"- [{finding.severity}] {finding.module}: {finding.actual}；建议：{finding.recommendation}" for finding in findings]
```

- [ ] **Step 4: Run export tests**

Run:

```bash
python3 -m pytest mcp-servers/config-audit/tests/test_export.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit**

Run:

```bash
git add mcp-servers/config-audit/core/export.py mcp-servers/config-audit/tests/test_export.py
git commit -m "feat: export config audit reports"
```

---

### Task 8: Add MCP Tool Wrappers

**Files:**
- Create: `mcp-servers/config-audit/tools/parse_config.py`
- Create: `mcp-servers/config-audit/tools/parse_snippet.py`
- Create: `mcp-servers/config-audit/tools/infer_template.py`
- Create: `mcp-servers/config-audit/tools/review_template.py`
- Create: `mcp-servers/config-audit/tools/compare_config.py`
- Create: `mcp-servers/config-audit/tools/check_snippet.py`
- Create: `mcp-servers/config-audit/tools/export_report.py`
- Modify: `mcp-servers/config-audit/server.py`

- [ ] **Step 1: Add parser dispatcher in parse_config tool**

Create `mcp-servers/config-audit/tools/parse_config.py`:

```python
import json
from pathlib import Path

from fastmcp import FastMCP

from parsers.h3c_firewall import parse_h3c_firewall
from parsers.hillstone_firewall import parse_hillstone_firewall
from parsers.huawei_firewall import parse_huawei_firewall


def parse_config_text(text: str, vendor: str, standard_zone: str, role: str, **profile_kwargs) -> dict:
    vendor_key = vendor.lower()
    if vendor_key == "h3c":
        result = parse_h3c_firewall(text, standard_zone=standard_zone, role=role, **profile_kwargs)
    elif vendor_key in {"huawei", "华为"}:
        result = parse_huawei_firewall(text, standard_zone=standard_zone, role=role, **profile_kwargs)
    elif vendor_key in {"hillstone", "山石"}:
        result = parse_hillstone_firewall(text, standard_zone=standard_zone, role=role, **profile_kwargs)
    else:
        raise ValueError(f"暂不支持的防火墙厂商：{vendor}")
    return result.model_dump()


def register(mcp: FastMCP):
    @mcp.tool()
    def config_audit_parse_config(
        config_text: str = "",
        config_path: str = "",
        vendor: str = "",
        standard_zone: str = "",
        role: str = "",
        device_name: str = "",
        model: str = "",
        os_version: str = "",
        site_name: str = "",
        local_area_name: str = "",
    ) -> str:
        """解析防火墙完整配置，返回统一配置模型 JSON。"""
        text = config_text or Path(config_path).read_text(encoding="utf-8")
        data = parse_config_text(
            text,
            vendor=vendor,
            standard_zone=standard_zone,
            role=role,
            device_name=device_name,
            model=model,
            os_version=os_version,
            site_name=site_name,
            local_area_name=local_area_name,
        )
        return json.dumps({"ok": True, "config": data}, ensure_ascii=False)
```

- [ ] **Step 2: Add parse_snippet tool**

Create `mcp-servers/config-audit/tools/parse_snippet.py`:

```python
import json

from fastmcp import FastMCP

from tools.parse_config import parse_config_text


def register(mcp: FastMCP):
    @mcp.tool()
    def config_audit_parse_snippet(
        snippet_text: str,
        vendor: str,
        standard_zone: str,
        role: str,
    ) -> str:
        """解析配置脚本片段，返回片段涉及的统一配置模块。"""
        data = parse_config_text(snippet_text, vendor=vendor, standard_zone=standard_zone, role=role)
        return json.dumps(
            {
                "ok": True,
                "config": data,
                "scope": "snippet",
                "uncertainty": "当前输入为配置片段，缺少完整设备上下文。",
            },
            ensure_ascii=False,
        )
```

- [ ] **Step 3: Add template tools**

Create `mcp-servers/config-audit/tools/infer_template.py`:

```python
import json

from fastmcp import FastMCP

from core.model import NormalizedConfig
from core.template import infer_template


def register(mcp: FastMCP):
    @mcp.tool()
    def config_audit_infer_template(configs: list[dict], standard_zone: str, role: str) -> str:
        """从认可配置反推 draft 标准模板。"""
        normalized = [NormalizedConfig(**item) for item in configs]
        template = infer_template(normalized, standard_zone=standard_zone, role=role)
        return json.dumps({"ok": True, "template": template.model_dump()}, ensure_ascii=False)
```

Create `mcp-servers/config-audit/tools/review_template.py`:

```python
import json
import os
from pathlib import Path

from fastmcp import FastMCP

from core.model import ConfigTemplate
from core.template import save_approved_template


def register(mcp: FastMCP):
    @mcp.tool()
    def config_audit_review_template(template: dict, reviewed_by: str = "manual-review") -> str:
        """将人工复核后的模板保存为 approved 模板。"""
        base_dir = Path(os.getenv("CONFIG_AUDIT_DATA_DIR", "backend/.deer-flow/config-audit")) / "templates" / "approved"
        saved_path = save_approved_template(ConfigTemplate(**template), base_dir, reviewed_by=reviewed_by)
        return json.dumps({"ok": True, "template_path": str(saved_path)}, ensure_ascii=False)
```

- [ ] **Step 4: Add compare and snippet-check tools**

Create `mcp-servers/config-audit/tools/compare_config.py`:

```python
import json

from fastmcp import FastMCP

from core.compare import compare_config_to_template
from core.model import ConfigTemplate, NormalizedConfig


def register(mcp: FastMCP):
    @mcp.tool()
    def config_audit_compare_config(config: dict, template: dict) -> str:
        """对完整配置与 approved 标准模板进行确定性差异对比。"""
        result = compare_config_to_template(NormalizedConfig(**config), ConfigTemplate(**template))
        return json.dumps({"ok": True, "result": result.model_dump()}, ensure_ascii=False)
```

Create `mcp-servers/config-audit/tools/check_snippet.py`:

```python
import json

from fastmcp import FastMCP

from core.compare import check_snippet_against_template
from core.model import ConfigTemplate, NormalizedConfig


def register(mcp: FastMCP):
    @mcp.tool()
    def config_audit_check_snippet(snippet_config: dict, template: dict, current_config: dict | None = None) -> str:
        """检查配置脚本片段是否缺少关键内容或上下文依赖。"""
        current = NormalizedConfig(**current_config) if current_config else None
        result = check_snippet_against_template(
            NormalizedConfig(**snippet_config),
            ConfigTemplate(**template),
            current=current,
        )
        return json.dumps({"ok": True, "result": result.model_dump()}, ensure_ascii=False)
```

- [ ] **Step 5: Add export tool**

Create `mcp-servers/config-audit/tools/export_report.py`:

```python
import json
import os
from pathlib import Path

from fastmcp import FastMCP

from core.export import export_report
from core.model import CompareResult, NormalizedConfig


def register(mcp: FastMCP):
    @mcp.tool()
    def config_audit_export_report(config: dict, compare_result: dict, agent_analysis: str = "") -> str:
        """导出配置审查 Excel 事实表和 Markdown 报告。"""
        output_dir = Path(os.getenv("CONFIG_AUDIT_OUTPUT_DIR", "backend/.deer-flow/mcp-outputs/config-audit"))
        paths = export_report(
            NormalizedConfig(**config),
            CompareResult(**compare_result),
            output_dir=output_dir,
            agent_analysis=agent_analysis,
        )
        return json.dumps({"ok": True, "paths": paths.model_dump()}, ensure_ascii=False)
```

- [ ] **Step 6: Register tools in server**

Modify `mcp-servers/config-audit/server.py`:

```python
"""设备配置审查 MCP Server。"""

from fastmcp import FastMCP

from tools.check_snippet import register as register_check_snippet
from tools.compare_config import register as register_compare_config
from tools.export_report import register as register_export_report
from tools.infer_template import register as register_infer_template
from tools.parse_config import register as register_parse_config
from tools.parse_snippet import register as register_parse_snippet
from tools.review_template import register as register_review_template


mcp = FastMCP(
    "config-audit",
    instructions=(
        "设备配置审查工具集：解析防火墙完整配置和配置片段，"
        "反推标准模板，执行标准化对比，并导出 Excel 与 Markdown 报告。"
    ),
)

register_parse_config(mcp)
register_parse_snippet(mcp)
register_infer_template(mcp)
register_review_template(mcp)
register_compare_config(mcp)
register_check_snippet(mcp)
register_export_report(mcp)


if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 7: Run full MCP tests**

Run:

```bash
python3 -m pytest mcp-servers/config-audit/tests -q
```

Expected:

```text
11 passed
```

The number may be higher if more tests were added during implementation; no tests may fail.

- [ ] **Step 8: Compile all config-audit Python files**

Run:

```bash
python3 -m compileall mcp-servers/config-audit
```

Expected: command exits with status 0.

- [ ] **Step 9: Commit**

Run:

```bash
git add mcp-servers/config-audit
git commit -m "feat: expose config audit MCP tools"
```

---

### Task 9: Add Custom Skill and Agent Runtime Guide

**Files:**
- Create: `skills/custom/config-audit/SKILL.md`
- Create: `docs/config-audit-agent-runtime.md`

- [ ] **Step 1: Create custom skill**

Create `skills/custom/config-audit/SKILL.md`:

```markdown
---
name: config-audit
description: >
  设备配置审查技能。用于防火墙完整配置梳理、标准模板反推、事后标准化检查、
  以及配置脚本片段的事前正确性检查。首版覆盖 H3C、Huawei、Hillstone 防火墙。
---

# 设备配置审查

本技能只负责约束 Agent 工作流。确定性解析、模板反推、差异对比和报告导出必须调用 `config-audit` MCP 工具完成。

## 核心原则

1. 先调用 MCP 获取结构化事实，再做 LLM 分析。
2. 不要直接凭原始配置文本给最终审查结论。
3. 完整配置检查必须使用 approved 标准模板。
4. 从现有配置反推的模板只能作为 draft，必须人工复核后才能用于正式检查。
5. 配置片段分析必须声明上下文不完整；只有同时提供当前完整配置时，才能做强判断。

## 工作流 A：完整配置梳理

1. 明确厂商、标准分类和设备角色。
2. 调用 `config_audit_parse_config`。
3. 调用 `config_audit_export_report` 导出 Excel 事实表。
4. 向用户返回设备画像、模块统计、未识别块和附件路径。

## 工作流 B：标准模板反推

1. 用户明确指定“认可样本”。
2. 对每份样本调用 `config_audit_parse_config`。
3. 调用 `config_audit_infer_template` 生成 draft。
4. 用 LLM 解释 draft 模板的来源和含义。
5. 等用户人工确认或修改后，调用 `config_audit_review_template` 保存 approved 模板。

## 工作流 C：事后标准化检查

1. 调用 `config_audit_parse_config`。
2. 读取或让用户指定 approved 标准模板。
3. 调用 `config_audit_compare_config`。
4. 基于 findings 做 LLM 分析，解释风险和整改建议。
5. 调用 `config_audit_export_report` 输出 Excel 和 Markdown。

## 工作流 D：事前配置脚本检查

1. 明确目标厂商、标准分类和设备角色。
2. 调用 `config_audit_parse_snippet`。
3. 调用 `config_audit_check_snippet`。
4. 如果用户提供当前完整配置，将完整配置作为上下文一并检查。
5. 输出缺失内容、依赖问题、命令风险和建议补充项。

## 禁止事项

- 禁止直接手写临时解析脚本绕过 MCP。
- 禁止把 draft 模板当正式模板使用。
- 禁止自动下发配置命令。
- 禁止把 LLM 分析当作唯一证据。
```

- [ ] **Step 2: Create runtime guide**

Create `docs/config-audit-agent-runtime.md`:

```markdown
# Config Audit Agent 运行态创建说明

`config-audit` 的可版本化能力包括 MCP server、custom skill 和扩展配置示例。

DeerFlow 自定义 Agent 的运行态文件位于 `backend/.deer-flow/agents/`，该目录不提交到 Git。实施验证时创建：

```text
backend/.deer-flow/agents/config-audit/
  config.yaml
  SOUL.md
```

## config.yaml 示例

```yaml
name: config-audit
description: 防火墙配置审查 Agent
skills:
  - config-audit
mcp_servers:
  - config-audit
```

## SOUL.md 示例

```markdown
# 防火墙配置审查 Agent

你负责防火墙完整配置梳理、标准模板反推、事后标准化检查和配置脚本片段事前检查。

你必须先调用 config-audit MCP 工具获取结构化事实，再进行 LLM 分析。

你不能自动下发配置命令。所有整改建议必须以审查建议形式输出。
```

## 验证入口

创建运行态 Agent 后，在 DeerFlow 前端选择 `config-audit` assistant，上传或粘贴防火墙配置进行验证。
```

- [ ] **Step 3: Stage ignored custom skill explicitly**

Run:

```bash
git add -f skills/custom/config-audit/SKILL.md
git add docs/config-audit-agent-runtime.md
```

- [ ] **Step 4: Commit**

Run:

```bash
git commit -m "feat: add config audit skill"
```

---

### Task 10: Integration Validation

**Files:**
- Runtime only: `backend/.deer-flow/agents/config-audit/config.yaml`
- Runtime only: `backend/.deer-flow/agents/config-audit/SOUL.md`
- Runtime only: `extensions_config.json` if enabling local MCP server

- [ ] **Step 1: Run all config-audit tests**

Run:

```bash
python3 -m pytest mcp-servers/config-audit/tests -q
```

Expected: all tests pass.

- [ ] **Step 2: Run backend checks if backend dependencies are available**

Run:

```bash
cd backend && make lint && make test
```

Expected: lint and tests pass.

If this fails because dependencies are missing, record the exact missing dependency or environment error in the final implementation report.

- [ ] **Step 3: Create runtime custom Agent files**

Run:

```bash
mkdir -p backend/.deer-flow/agents/config-audit
```

Create `backend/.deer-flow/agents/config-audit/config.yaml`:

```yaml
name: config-audit
description: 防火墙配置审查 Agent
skills:
  - config-audit
mcp_servers:
  - config-audit
```

Create `backend/.deer-flow/agents/config-audit/SOUL.md`:

```markdown
# 防火墙配置审查 Agent

你负责防火墙完整配置梳理、标准模板反推、事后标准化检查和配置脚本片段事前检查。

你必须先调用 config-audit MCP 工具获取结构化事实，再进行 LLM 分析。

你不能自动下发配置命令。所有整改建议必须以审查建议形式输出。
```

- [ ] **Step 4: Ensure runtime files are not staged**

Run:

```bash
git status --short
```

Expected: no `backend/.deer-flow/agents/config-audit` files appear.

- [ ] **Step 5: Validate MCP server can start**

Run:

```bash
python3 mcp-servers/config-audit/server.py
```

Expected: server starts and waits for stdio input. Stop it with `Ctrl+C`.

- [ ] **Step 6: Validate local parse path through Python**

Run:

```bash
python3 - <<'PY'
import sys
from pathlib import Path

root = Path("mcp-servers/config-audit").resolve()
sys.path.insert(0, str(root))

from tools.parse_config import parse_config_text

text = (root / "tests/fixtures/h3c_firewall.cfg").read_text(encoding="utf-8")
data = parse_config_text(text, vendor="H3C", standard_zone="internet_edge", role="border_firewall")
assert data["device_profile"]["vendor"] == "H3C"
assert len(data["policy_rules"]) == 1
print("ok")
PY
```

Expected:

```text
ok
```

- [ ] **Step 7: Commit final validation notes if docs changed**

If no docs changed, no commit is needed.

---

### Task 11: Merge Back to Main

**Files:**
- No code changes beyond merge.

- [ ] **Step 1: Confirm feature branch is clean**

Run:

```bash
git status --short --branch
```

Expected:

```text
## codex/config-audit-agent
```

No uncommitted files should be listed.

- [ ] **Step 2: Review commits**

Run:

```bash
git log --oneline main..codex/config-audit-agent
```

Expected: commits for MCP skeleton, models, parsers, templates, compare, export, tools, skill.

- [ ] **Step 3: Switch to main**

Run:

```bash
git switch main
```

- [ ] **Step 4: Merge feature branch**

Run:

```bash
git merge --no-ff codex/config-audit-agent -m "merge: config audit agent"
```

Expected: merge succeeds without conflicts.

- [ ] **Step 5: Run final smoke tests on main**

Run:

```bash
python3 -m pytest mcp-servers/config-audit/tests -q
```

Expected: all config-audit tests pass.

- [ ] **Step 6: Confirm final status**

Run:

```bash
git status --short --branch
```

Expected:

```text
## main...origin/main [ahead N]
```

No uncommitted files should be listed.

Do not push unless the user explicitly asks.

---

## Self-Review Checklist

- Spec coverage:
  - MCP server: Tasks 2 and 8.
  - Unified model: Task 3.
  - H3C/Huawei/Hillstone parser support: Task 4.
  - Template inference and artificial approval flow: Task 5.
  - Full config compare and snippet check: Task 6.
  - Excel and Markdown report export: Task 7.
  - DeerFlow skill and runtime Agent guide: Task 9.
  - Branch development, tests, and merge to main: Tasks 1, 10, and 11.
- Placeholder scan: this plan has no unresolved markers or intentionally vague future steps.
- Scope check: this plan implements only firewall review. Routers, switches, load balancers, live device connection, and automatic config deployment remain out of scope.
