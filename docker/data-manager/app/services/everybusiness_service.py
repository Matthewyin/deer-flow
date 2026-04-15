import json
import os
import subprocess
import sys

BUSINESS_BASELINE_DIR = "/app/mcp-servers/business-baseline"
BUSINESS_BASELINE_TOOLS = f"{BUSINESS_BASELINE_DIR}/tools"

EVERYBUSINESS_PATH = "/app/docs/businessInfo/everybusiness"


def get_current_content() -> dict:
    if not os.path.exists(EVERYBUSINESS_PATH):
        return {"content": "", "file_size": 0, "last_modified": None}
    stat = os.stat(EVERYBUSINESS_PATH)
    from datetime import datetime

    mtime = datetime.fromtimestamp(stat.st_mtime).isoformat()
    with open(EVERYBUSINESS_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    return {"content": content, "file_size": stat.st_size, "last_modified": mtime}


def save_and_parse(content: str) -> dict:
    try:
        os.makedirs(os.path.dirname(EVERYBUSINESS_PATH), exist_ok=True)
        with open(EVERYBUSINESS_PATH, "w", encoding="utf-8") as f:
            f.write(content)
        file_size = os.path.getsize(EVERYBUSINESS_PATH)
    except OSError as e:
        return {"success": False, "error": str(e)}

    try:
        # Use subprocess to avoid db package namespace collision with remote-probe
        script = (
            "import sys, os, json; "
            f"sys.path.insert(0, '{BUSINESS_BASELINE_DIR}'); "
            f"sys.path.insert(0, '{BUSINESS_BASELINE_TOOLS}'); "
            "os.chdir(sys.path[0]); "
            "from parse_daily_report import parse_daily_report_impl; "
            "r = parse_daily_report_impl(); "
            "print(json.dumps(r))"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=60,
            env={
                **os.environ,
                "BUSINESS_DB_PATH": os.environ.get(
                    "BUSINESS_DB_PATH", "/app/.deer-flow/db/business_baseline.db"
                ),
            },
        )
        if result.returncode == 0 and result.stdout.strip():
            parsed = json.loads(result.stdout.strip())
            return {
                "success": True,
                "file_size": file_size,
                "parsed_count": parsed.get("parsed_reports", 0),
                "parsed_metrics": parsed.get("parsed_metrics", 0),
                "skipped_blocks": parsed.get("skipped_blocks", 0),
            }
        else:
            err = result.stderr.strip()[-500:] if result.stderr else "unknown error"
            return {"success": True, "file_size": file_size, "parse_error": err}
    except Exception as e:
        return {
            "success": True,
            "file_size": file_size,
            "parse_error": str(e),
        }
