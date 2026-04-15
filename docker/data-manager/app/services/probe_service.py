import json
import os
import sys
from pathlib import Path
from datetime import datetime

REMOTE_PROBE_DIR = "/app/mcp-servers/remote-probe"
for p in [REMOTE_PROBE_DIR, f"{REMOTE_PROBE_DIR}/tools", f"{REMOTE_PROBE_DIR}/db"]:
    if p not in sys.path:
        sys.path.insert(0, p)

LOG_PATH = "/app/.deer-flow/probe/collection_log.json"


def _load_log() -> list[dict]:
    if not os.path.exists(LOG_PATH):
        return []
    try:
        with open(LOG_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_log(logs: list[dict]):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


def save_collection_log(entry: dict):
    logs = _load_log()
    logs.append(entry)
    _save_log(logs)


def collect_probe_data(regions=None) -> dict:
    from collect_probe_data import collect_probe_data_impl

    return collect_probe_data_impl(regions)


def get_status() -> dict:
    from config import get_config

    cfg = get_config()

    logs = _load_log()
    last_collection = logs[-1] if logs else None

    regions_info = []
    for name, info in cfg.probe.nodes.items():
        raw_dir = Path(cfg.probe.local_raw_dir) / name
        file_count = 0
        if raw_dir.exists():
            file_count = sum(1 for _ in raw_dir.rglob("*") if _.is_file())
        regions_info.append(
            {
                "name": name,
                "city": info.get("city", name),
                "file_count": file_count,
            }
        )

    return {
        "scheduler_running": False,
        "next_run": None,
        "last_collection": last_collection,
        "regions": regions_info,
    }


def get_history(limit: int = 20) -> list[dict]:
    logs = _load_log()
    return logs[-limit:]
