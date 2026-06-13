import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from config import get_config


REQUIRED_KEYS = {"dates", "lines", "groups"}


def _validate_report_config(report_config: dict[str, Any]) -> str | None:
    missing = sorted(REQUIRED_KEYS - set(report_config.keys()))
    if missing:
        return "report_config missing required key(s): " + ", ".join(missing)

    if not isinstance(report_config.get("dates"), list) or not report_config["dates"]:
        return "report_config.dates must be a non-empty list"
    if not isinstance(report_config.get("lines"), dict) or not report_config["lines"]:
        return "report_config.lines must be a non-empty object"
    if not isinstance(report_config.get("groups"), list) or not report_config["groups"]:
        return "report_config.groups must be a non-empty list"

    return None


def _safe_output_filename(filename: str) -> str:
    name = Path(filename.strip()).name
    if not name:
        name = get_config().default_output_filename
    if not name.endswith(".html"):
        name += ".html"
    return name


def generate_report(report_config: dict[str, Any], output_filename: str = "") -> dict[str, Any]:
    if not isinstance(report_config, dict):
        return {
            "ok": False,
            "error": "report_config must be an object",
        }

    error = _validate_report_config(report_config)
    if error:
        return {
            "ok": False,
            "error": error,
        }

    cfg = get_config()
    script_path = Path(cfg.report_script_path)
    if not script_path.exists():
        return {
            "ok": False,
            "error": f"report script not found: {script_path}",
        }

    filename = _safe_output_filename(output_filename or str(report_config.get("output_filename", "")))

    with tempfile.TemporaryDirectory(prefix="network-weekly-report-") as tmpdir:
        tmp_path = Path(tmpdir)
        input_path = tmp_path / "report_input.json"
        output_path = tmp_path / filename

        payload = dict(report_config)
        payload["output_path"] = str(output_path)
        input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--input",
                str(input_path),
                "--output",
                str(output_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            return {
                "ok": False,
                "error": "report script failed",
                "returncode": result.returncode,
                "stdout": result.stdout[-2000:],
                "stderr": result.stderr[-4000:],
            }

        if not output_path.exists():
            return {
                "ok": False,
                "error": "report script did not create output file",
                "stdout": result.stdout[-2000:],
                "stderr": result.stderr[-4000:],
            }

        html = output_path.read_text(encoding="utf-8")

    line_count = len(report_config.get("lines", {}))
    group_count = len(report_config.get("groups", []))
    return {
        "ok": True,
        "html": html,
        "output_filename": filename,
        "suggested_output_path": f"/mnt/user-data/outputs/{filename}",
        "line_count": line_count,
        "group_count": group_count,
        "stdout": result.stdout[-2000:],
    }


def register(mcp: FastMCP):
    @mcp.tool()
    def generate(report_config: dict[str, Any], output_filename: str = "") -> dict[str, Any]:
        """调用标准 network-weekly-report skill 脚本生成 HTML 周报。

        Args:
            report_config: 报告数据 JSON 对象，必须包含 dates、lines、groups。
            output_filename: 建议保存给用户的 HTML 文件名，默认使用配置值。

        Returns:
            dict: 生成结果。成功时返回 html 和 suggested_output_path，Agent 只需写入文件并 present_files。
        """
        return generate_report(report_config, output_filename)
