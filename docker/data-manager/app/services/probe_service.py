import json
import logging
import os
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

REMOTE_PROBE_DIR = "/app/mcp-servers/remote-probe"
for p in [REMOTE_PROBE_DIR, f"{REMOTE_PROBE_DIR}/tools", f"{REMOTE_PROBE_DIR}/db"]:
    if p not in sys.path:
        sys.path.insert(0, p)

LOG_PATH = "/app/.deer-flow/probe/collection_log.json"

logger = logging.getLogger("data-manager")


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


def _get_db_path() -> str:
    return os.environ.get("PROBE_DB_PATH", "/app/backend/.deer-flow/db/remote_probe.db")


def collect_probe_data(regions=None) -> dict:
    from collect_probe_data import collect_probe_data_impl

    # Sync REMOTE_PROBE_DB_PATH (read by config.get_config) to the shared volume path
    os.environ["REMOTE_PROBE_DB_PATH"] = _get_db_path()

    return collect_probe_data_impl(regions)


def get_status() -> dict:
    from config import get_config

    cfg = get_config()

    logs = _load_log()
    last_collection = logs[-1] if logs else None

    # Get actual scheduler state from app module
    from app.app import _scheduler
    scheduler_running = _scheduler is not None and _scheduler.running

    # Get next run time
    next_run = None
    if scheduler_running:
        jobs = _scheduler.get_jobs()
        if jobs:
            next_run = str(jobs[0].next_run_time) if jobs[0].next_run_time else None

    regions_info = []
    try:
        db_path = _get_db_path()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        for name, info in cfg.probe.nodes.items():
            raw_dir = Path(cfg.probe.local_raw_dir) / name
            file_count = 0
            if raw_dir.exists():
                file_count = sum(1 for _ in raw_dir.rglob("*") if _.is_file())

            # Count uningested files from DB
            uningested_row = conn.execute(
                "SELECT COUNT(*) as cnt FROM raw_files WHERE region = ? AND ingested = 0",
                (name,),
            ).fetchone()
            uningested = uningested_row["cnt"] if uningested_row else 0

            regions_info.append({
                "name": name,
                "city": info.get("city", name),
                "file_count": file_count,
                "uningested_files": uningested,
            })
        conn.close()
    except Exception:
        # Fallback if DB not available
        for name, info in cfg.probe.nodes.items():
            raw_dir = Path(cfg.probe.local_raw_dir) / name
            file_count = 0
            if raw_dir.exists():
                file_count = sum(1 for _ in raw_dir.rglob("*") if _.is_file())
            regions_info.append({
                "name": name,
                "city": info.get("city", name),
                "file_count": file_count,
                "uningested_files": 0,
            })

    return {
        "scheduler_running": scheduler_running,
        "next_run": next_run,
        "last_collection": last_collection,
        "regions": regions_info,
    }


def get_history(limit: int = 20) -> list[dict]:
    logs = _load_log()
    return logs[-limit:]
