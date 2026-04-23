import os
from pathlib import Path
from datetime import datetime

CATEGORIES = {
    "01 系统应急预案": "emergency_system",
    "02 网络应急预案": "emergency_network",
    "03 安全应急预案": "emergency_security",
    "SOP": "sop",
}

DOC_TYPE_TO_DIR = {v: k for k, v in CATEGORIES.items()}

ALLOWED_EXTENSIONS = {".docx", ".pdf", ".xlsx", ".txt", ".md", ".csv"}
RAW_BASE = "/app/docs/ops-knowledge/raw"


def list_categories() -> list[dict]:
    result = []
    for name, doc_type in CATEGORIES.items():
        cat_dir = Path(RAW_BASE) / name
        count = 0
        if cat_dir.exists():
            count = sum(1 for f in cat_dir.iterdir() if f.is_file())
        result.append({"name": name, "doc_type": doc_type, "file_count": count})
    return result


def list_files(category: str) -> list[dict]:
    if category not in CATEGORIES:
        return []
    cat_dir = Path(RAW_BASE) / category
    if not cat_dir.exists():
        return []
    files = []
    for f in sorted(cat_dir.iterdir()):
        if f.is_file():
            stat = f.stat()
            files.append(
                {
                    "filename": f.name,
                    "size": stat.st_size,
                    "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )
    return files


def save_file(category: str, filename: str, file_content: bytes) -> dict:
    if category not in CATEGORIES:
        return {"success": False, "error": f"Invalid category: {category}"}
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return {"success": False, "error": f"Unsupported file type: {ext}"}
    cat_dir = Path(RAW_BASE) / category
    cat_dir.mkdir(parents=True, exist_ok=True)
    dest = cat_dir / filename
    dest.write_bytes(file_content)
    return {"success": True, "path": str(dest), "size": len(file_content)}


def delete_file(category: str, filename: str) -> dict:
    if category not in CATEGORIES:
        return {"success": False, "error": f"Invalid category: {category}"}
    filepath = Path(RAW_BASE) / category / filename
    if not filepath.exists() or not filepath.is_file():
        return {"success": False, "error": "File not found"}
    filepath.unlink()
    return {"success": True, "deleted": filename}


def trigger_ingest() -> dict:
    import urllib.request
    import urllib.error
    import json

    url = "http://deer-flow-gateway:8001/api/management/rebuild-ops-knowledge-vectors"
    try:
        req = urllib.request.Request(url, method="POST", data=b"{}")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=600) as resp:
            body = json.loads(resp.read().decode())
            return {
                "success": body.get("success", False),
                "message": body.get("message", ""),
            }
    except urllib.error.HTTPError as e:
        body_text = e.read().decode() if e.fp else ""
        return {"success": False, "error": f"Gateway returned {e.code}: {body_text}"}
    except urllib.error.URLError as e:
        return {"success": False, "error": f"Cannot reach Gateway: {e.reason}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
