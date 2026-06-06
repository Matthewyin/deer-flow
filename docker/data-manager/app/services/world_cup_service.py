import json
import os
import shutil
import sys
from pathlib import Path

WORLD_CUP_MCP_DIRS = [Path("/app/mcp-servers/world-cup")]
for parent in Path(__file__).resolve().parents:
    WORLD_CUP_MCP_DIRS.append(parent / "mcp-servers" / "world-cup")
for mcp_dir in WORLD_CUP_MCP_DIRS:
    if mcp_dir.exists() and str(mcp_dir) not in sys.path:
        sys.path.insert(0, str(mcp_dir))

from core.db import beijing_now, clear_all_data, delete_upload, import_parsed_data, status
from core.normalizer import file_sha256
from core.parser import parse_workbook
from core.transformer import normalize_workbook_for_import

DB_PATH = os.environ.get("WORLD_CUP_DB_PATH", "/app/backend/.deer-flow/db/world_cup.db")
DATA_DIR = Path(os.environ.get("WORLD_CUP_DATA_DIR", "/app/.deer-flow/world-cup"))
RAW_DIR = DATA_DIR / "raw"
PARSED_DIR = DATA_DIR / "parsed"
NORMALIZED_DIR = DATA_DIR / "normalized"


def _safe_filename(filename: str) -> str:
    name = Path(filename or "world-cup.xlsx").name
    return name.replace("/", "_").replace("\\", "_")


def _make_upload_id(filename: str, file_hash: str) -> str:
    stem = Path(filename).stem[:32] or "world-cup"
    ts = beijing_now().strftime("%Y%m%d%H%M%S")
    return f"{ts}_{file_hash[:10]}_{stem}"


def get_world_cup_status() -> dict:
    result = status(DB_PATH)
    result["db_path"] = DB_PATH
    result["data_dir"] = str(DATA_DIR)
    return result


def save_parse_and_import(file_content: bytes, filename: str) -> dict:
    safe_name = _safe_filename(filename)
    file_hash = file_sha256(file_content)
    cleared = clear_all_data(DB_PATH)
    reset_world_cup_files()

    upload_id = _make_upload_id(safe_name, file_hash)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)

    raw_path = RAW_DIR / f"{upload_id}_{safe_name}"
    normalized_path = NORMALIZED_DIR / f"{upload_id}_{safe_name}"
    parsed_path = PARSED_DIR / f"{upload_id}.json"
    raw_path.write_bytes(file_content)

    normalized = normalize_workbook_for_import(raw_path, normalized_path)
    parsed = parse_workbook(normalized_path, upload_id, safe_name)
    parsed_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")

    imported = import_parsed_data(
        DB_PATH,
        parsed,
        source_filename=safe_name,
        file_hash=file_hash,
        raw_file_path=str(raw_path),
        parsed_json_path=str(parsed_path),
    )
    return {
        "success": True,
        "replaced": True,
        "cleared": cleared,
        "upload": imported,
        "sheet_count": parsed.get("sheet_count", 0),
        "record_count": parsed.get("record_count", 0),
        "error_count": len(parsed.get("errors", [])),
        "normalized": normalized,
        "raw_file_path": str(raw_path),
        "normalized_file_path": str(normalized_path),
        "parsed_json_path": str(parsed_path),
    }


def delete_world_cup_upload(upload_id: str) -> dict:
    return delete_upload(DB_PATH, upload_id)


def reset_world_cup_files() -> dict:
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    return {"success": True, "data_dir": str(DATA_DIR)}
