import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import import_batches  # noqa: E402


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def _write_index(base_dir: Path, item: dict) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "index.json").write_text(
        json.dumps({"imports": [item]}, ensure_ascii=False), encoding="utf-8"
    )


def test_list_import_batches_filters_by_vendor_and_device_type(tmp_path, monkeypatch):
    monkeypatch.setattr(import_batches, "DEFAULT_IMPORT_DIR", str(tmp_path))
    item = {
        "import_id": "batch-1",
        "vendor": "huawei",
        "device_type": "firewall",
        "files": [],
    }
    _write_index(tmp_path, item)

    result = import_batches.config_audit_list_import_batches(
        vendor="huawei", device_type="firewall"
    )

    assert result["ok"] is True
    assert result["total"] == 1
    assert result["imports"][0]["import_id"] == "batch-1"


def test_parse_import_batch_parses_supported_firewall(tmp_path, monkeypatch):
    monkeypatch.setattr(import_batches, "DEFAULT_IMPORT_DIR", str(tmp_path))
    config_dir = tmp_path / "firewall" / "huawei" / "batch-1"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "fw.txt"
    config_path.write_text((FIXTURE_DIR / "huawei_firewall.cfg").read_text(encoding="utf-8"), encoding="utf-8")
    item = {
        "import_id": "batch-1",
        "vendor": "huawei",
        "device_type": "firewall",
        "standard_zone": "internet_edge",
        "role": "border_firewall",
        "files": [
            {
                "filename": "fw.txt",
                "stored_filename": "fw.txt",
                "path": str(config_path),
            }
        ],
    }
    _write_index(tmp_path, item)

    result = import_batches.config_audit_parse_import_batch("batch-1")

    assert result["ok"] is True
    assert result["compact"] is True
    assert result["failed"] == []
    assert result["configs"][0]["config"]["device_profile"]["vendor"] == "Huawei"
    assert "policy_rules" in result["configs"][0]["config"]["module_counts"]
    assert "policy_rules" not in result["configs"][0]["config"]


def test_parse_import_batch_can_return_full_configs_when_explicit(tmp_path, monkeypatch):
    monkeypatch.setattr(import_batches, "DEFAULT_IMPORT_DIR", str(tmp_path))
    config_dir = tmp_path / "firewall" / "huawei" / "batch-1"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "fw.txt"
    config_path.write_text((FIXTURE_DIR / "huawei_firewall.cfg").read_text(encoding="utf-8"), encoding="utf-8")
    item = {
        "import_id": "batch-1",
        "vendor": "huawei",
        "device_type": "firewall",
        "standard_zone": "internet_edge",
        "role": "border_firewall",
        "files": [
            {
                "filename": "fw.txt",
                "stored_filename": "fw.txt",
                "path": str(config_path),
            }
        ],
    }
    _write_index(tmp_path, item)

    result = import_batches.config_audit_parse_import_batch(
        "batch-1", include_full_configs=True
    )

    assert result["ok"] is True
    assert result["compact"] is False
    assert result["configs"][0]["config"]["device_profile"]["vendor"] == "Huawei"
    assert "policy_rules" in result["configs"][0]["config"]


def test_infer_template_from_import_batch_returns_template_without_configs(tmp_path, monkeypatch):
    monkeypatch.setattr(import_batches, "DEFAULT_IMPORT_DIR", str(tmp_path))
    config_dir = tmp_path / "firewall" / "huawei" / "batch-1"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "fw.txt"
    config_path.write_text((FIXTURE_DIR / "huawei_firewall.cfg").read_text(encoding="utf-8"), encoding="utf-8")
    item = {
        "import_id": "batch-1",
        "vendor": "huawei",
        "device_type": "firewall",
        "standard_zone": "internet_edge",
        "role": "border_firewall",
        "files": [
            {
                "filename": "fw.txt",
                "stored_filename": "fw.txt",
                "path": str(config_path),
            }
        ],
    }
    _write_index(tmp_path, item)

    result = import_batches.config_audit_infer_template_from_import_batch(
        "batch-1",
        standard_zone="internet_edge",
        role="border_firewall",
    )

    assert result["ok"] is True
    assert result["parsed_count"] == 1
    assert result["template"]["template_id"] == "firewall.internet_edge.border_firewall"
    assert "configs" not in result


def test_parse_import_batch_marks_unsupported_vendor(tmp_path, monkeypatch):
    monkeypatch.setattr(import_batches, "DEFAULT_IMPORT_DIR", str(tmp_path))
    item = {
        "import_id": "batch-1",
        "vendor": "f5",
        "device_type": "load_balancer",
        "files": [],
    }
    _write_index(tmp_path, item)

    result = import_batches.config_audit_parse_import_batch("batch-1")

    assert result["ok"] is True
    assert result["configs"] == []
    assert result["unsupported"][0]["vendor"] == "f5"
