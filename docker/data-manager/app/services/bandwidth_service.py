from pathlib import Path
from datetime import datetime

MD_PATH = "/app/docs/bandwidth.md"


def get_status() -> dict:
    p = Path(MD_PATH)
    if not p.exists():
        return {"filename": "bandwidth.md", "exists": False, "size": 0, "last_modified": None}
    stat = p.stat()
    return {
        "filename": p.name,
        "exists": True,
        "size": stat.st_size,
        "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }


def save_file(file_content: bytes) -> dict:
    ext = Path(MD_PATH).suffix.lower()
    if ext != ".md":
        return {"success": False, "error": f"Expected .md file, got {ext}"}
    Path(MD_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(MD_PATH).write_bytes(file_content)
    return {"success": True, "path": MD_PATH, "size": len(file_content)}


def trigger_rebuild() -> dict:
    import urllib.request
    import urllib.error
    import json

    url = "http://deer-flow-gateway:8001/api/management/rebuild-bandwidth-vectors"
    try:
        req = urllib.request.Request(url, method="POST", data=b"{}")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=120) as resp:
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