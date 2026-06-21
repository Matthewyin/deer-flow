import importlib.util
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.export_report import DEFAULT_OUTPUT_DIR  # noqa: E402
from tools.parse_config import config_audit_parse_config, parse_config_text  # noqa: E402
from tools.parse_snippet import config_audit_parse_snippet  # noqa: E402
from tools.review_template import DEFAULT_DATA_DIR  # noqa: E402


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_parse_config_text_supports_chinese_vendor_alias():
    huawei = parse_config_text(
        read_fixture("huawei_firewall.cfg"),
        vendor="华为",
        standard_zone="internet_edge",
        role="border_firewall",
    )
    hillstone = parse_config_text(
        read_fixture("hillstone_firewall.cfg"),
        vendor="山石",
        standard_zone="dmz",
        role="border_firewall",
    )

    assert huawei["device_profile"]["vendor"] == "Huawei"
    assert hillstone["device_profile"]["vendor"] == "Hillstone"


def test_parse_tools_return_dict_without_json_decode():
    config = config_audit_parse_config(
        config_text=read_fixture("huawei_firewall.cfg"),
        vendor="华为",
        standard_zone="internet_edge",
        role="border_firewall",
    )
    snippet = config_audit_parse_snippet(
        config_text=read_fixture("hillstone_firewall.cfg"),
        vendor="山石",
        standard_zone="dmz",
        role="border_firewall",
    )

    assert isinstance(config, dict)
    assert config["ok"] is True
    assert config["config"]["device_profile"]["vendor"] == "Huawei"
    assert isinstance(snippet, dict)
    assert snippet["scope"] == "snippet"
    assert "配置脚本片段" in snippet["uncertainty"]


def test_parse_config_path_missing_raises_chinese_value_error(tmp_path):
    missing = tmp_path / "missing.cfg"

    with pytest.raises(ValueError, match=f"配置文件不存在：{missing}"):
        config_audit_parse_config(
            config_path=str(missing),
            vendor="h3c",
            standard_zone="internet_edge",
            role="border_firewall",
        )


def test_default_runtime_paths_do_not_start_with_backend_prefix():
    assert DEFAULT_DATA_DIR == ".deer-flow/config-audit"
    assert DEFAULT_OUTPUT_DIR == ".deer-flow/mcp-outputs/config-audit"
    assert not DEFAULT_DATA_DIR.startswith("backend/.deer-flow")
    assert not DEFAULT_OUTPUT_DIR.startswith("backend/.deer-flow")


def test_server_import_when_fastmcp_is_available():
    if importlib.util.find_spec("fastmcp") is None:
        pytest.skip("本地 Python 环境未安装 fastmcp")

    import server  # noqa: F401
