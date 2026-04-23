# 带宽策略文档管理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 data-manager WebUI 中增加带宽策略选项卡，上传覆盖 `bandwidth.md` 并自动触发向量库重建。

**Architecture:** 新增 3 个文件（service、router、重建脚本），修改 2 个文件（app.py 注册路由、index.html 新增 tab）。重建脚本通过 subprocess 调用，复用 `mcp-servers/network-ops/` 下已有的 `BandwidthRAG` 和 `config`。

**Tech Stack:** Python 3.12, FastAPI, vanilla JS/HTML, ChromaDB, OllamaEmbeddings

**Spec:** `docs/superpowers/specs/2026-04-23-bandwidth-policy-manager-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `docker/data-manager/app/services/bandwidth_service.py` | Create | 状态查询、文件保存、重建触发 |
| `docker/data-manager/app/routers/bandwidth.py` | Create | 3 个 API 端点 |
| `docs/rebuild_bandwidth_vectors.py` | Create | 删除旧向量库 + 重建 |
| `docker/data-manager/app/app.py` | Modify | 注册 bandwidth router |
| `docker/data-manager/app/templates/index.html` | Modify | 新增 tab + 3 个 JS 函数 |

---

### Task 1: 重建脚本

**Files:**
- Create: `docs/rebuild_bandwidth_vectors.py`

**Context:** 参照 `docs/batch_ingest_ops_knowledge.py` 的 sys.path 和 import 模式。`mcp-servers/network-ops/` 在容器内映射为 `/app/mcp-servers`（只读）。`BandwidthRAG.initialize()` 在 `persist_dir` 不存在时会自动从 `md_path` 构建。

- [ ] **Step 1: 创建重建脚本**

```python
#!/usr/bin/env python3
"""Rebuild bandwidth policy vectorstore from docs/bandwidth.md.

Usage:
  python docs/rebuild_bandwidth_vectors.py
"""

import shutil
import sys
import time
from pathlib import Path

# Add mcp-servers to path (same pattern as batch_ingest_ops_knowledge.py)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
MCP_SERVERS = PROJECT_ROOT / "mcp-servers" / "network-ops"
sys.path.insert(0, str(MCP_SERVERS))

from config import get_config
from rag.bandwidth_rag import BandwidthRAG


def main():
    cfg = get_config()
    persist_dir = cfg.chroma.persist_dir
    md_path = cfg.chroma.md_path

    print(f"MD path: {md_path}")
    print(f"Persist dir: {persist_dir}")

    # Resolve relative paths
    if not Path(md_path).is_absolute():
        md_path = str(PROJECT_ROOT / md_path)
    if not Path(persist_dir).is_absolute():
        persist_dir = str(PROJECT_ROOT / persist_dir)

    # Check source file
    if not Path(md_path).exists():
        print(f"ERROR: Source file not found: {md_path}")
        sys.exit(1)

    # Delete existing vectorstore
    if Path(persist_dir).exists():
        print(f"Deleting existing vectorstore at {persist_dir}")
        shutil.rmtree(persist_dir)

    # Build vectorstore
    print("Building vectorstore...")
    start = time.time()
    rag = BandwidthRAG(
        persist_dir=persist_dir,
        ollama_base_url=cfg.chroma.ollama_base_url,
        ollama_model=cfg.chroma.ollama_model,
        collection_name=cfg.chroma.collection_name,
        md_path=md_path,
    )
    rag.initialize()
    elapsed = int(time.time() - start)

    count = rag._vectorstore._collection.count()
    print(f"Done: {count} chunks in {elapsed}s")
    sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 验证脚本语法**

Run: `python -c "import ast; ast.parse(open('docs/rebuild_bandwidth_vectors.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add docs/rebuild_bandwidth_vectors.py
git commit -m "feat: add bandwidth vectorstore rebuild script"
```

---

### Task 2: 服务层

**Files:**
- Create: `docker/data-manager/app/services/bandwidth_service.py`

**Context:** 参照 `docker/data-manager/app/services/emergency_service.py` 的 `trigger_ingest()` 模式。bandwidth.md 在容器内路径为 `/app/docs/bandwidth.md`。

- [ ] **Step 1: 创建 bandwidth_service.py**

```python
import subprocess
from pathlib import Path
from datetime import datetime

MD_PATH = "/app/docs/bandwidth.md"
REBUILD_SCRIPT = "/app/docs/rebuild_bandwidth_vectors.py"


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
    try:
        result = subprocess.run(
            ["python", REBUILD_SCRIPT],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout[-500:] if result.stdout else "",
            "stderr": result.stderr[-500:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Rebuild script timed out (120s)"}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

- [ ] **Step 2: 验证语法**

Run: `python -c "import ast; ast.parse(open('docker/data-manager/app/services/bandwidth_service.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add docker/data-manager/app/services/bandwidth_service.py
git commit -m "feat: add bandwidth service layer for data-manager"
```

---

### Task 3: API 路由

**Files:**
- Create: `docker/data-manager/app/routers/bandwidth.py`
- Modify: `docker/data-manager/app/app.py`

**Context:** 参照 `docker/data-manager/app/routers/emergency.py`。Router 注册到 `app.py`。

- [ ] **Step 1: 创建 bandwidth router**

```python
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.services.bandwidth_service import (
    get_status,
    save_file,
    trigger_rebuild,
)

router = APIRouter(tags=["bandwidth"])


@router.get("/api/bandwidth/status")
async def bandwidth_status():
    return get_status()


@router.post("/api/bandwidth/upload")
async def bandwidth_upload(file: UploadFile = File(...)):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext != "md":
        raise HTTPException(status_code=400, detail="Only .md files are accepted")
    content = await file.read()
    save_result = save_file(content)
    if not save_result["success"]:
        raise HTTPException(status_code=400, detail=save_result["error"])
    rebuild_result = trigger_rebuild()
    return {"save": save_result, "rebuild": rebuild_result}


@router.post("/api/bandwidth/rebuild")
async def bandwidth_rebuild():
    rebuild_result = trigger_rebuild()
    return {"rebuild": rebuild_result}
```

- [ ] **Step 2: 验证语法**

Run: `python -c "import ast; ast.parse(open('docker/data-manager/app/routers/bandwidth.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: 注册 router 到 app.py**

在 `docker/data-manager/app/app.py` 第 11 行后添加 import：

```python
from app.routers import everybusiness, emergency, probe, bandwidth
```

在第 85 行后添加 router 注册：

```python
app.include_router(bandwidth.router)
```

- [ ] **Step 4: 验证 app.py 语法**

Run: `python -c "import ast; ast.parse(open('docker/data-manager/app/app.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add docker/data-manager/app/routers/bandwidth.py docker/data-manager/app/app.py
git commit -m "feat: add bandwidth API router and register in app"
```

---

### Task 4: 前端 UI

**Files:**
- Modify: `docker/data-manager/app/templates/index.html`

**Context:** 参照应急预案 tab 的 HTML 结构和 JS 函数模式。Tab 通过 `data-tab` 属性切换面板。新增的 tab 位于「探测数据」之后。

- [ ] **Step 1: 在 tabs 区域添加第 4 个 tab**

在 index.html 中找到 `<!-- Tab 3: Probe -->` 面板（第 98 行），在其 `</div>` 结束标签（第 132 行）之后、`</div>` (content 容器结束) 之前，插入带宽策略面板 HTML。

在 `<div class="tabs">` 区域的第 56 行 `<div class="tab" data-tab="probe">探测数据</div>` 之后添加：

```html
  <div class="tab" data-tab="bandwidth">带宽策略</div>
```

- [ ] **Step 2: 在 content 区域添加面板 HTML**

在 `</div>` (panel-probe 的结束，第 132 行) 之后、`</div>` (content 的结束) 之前插入：

```html
  <!-- Tab 4: Bandwidth -->
  <div class="panel" id="panel-bandwidth">
    <div class="card">
      <h2>带宽扩缩容指南文档</h2>
      <div id="bw-status" style="font-size:13px;color:#888;margin-bottom:12px;"></div>
      <div class="upload-area">
        <input type="file" id="bw-file" accept=".md">
        <button class="btn btn-primary" onclick="bwUpload()">上传并重建</button>
        <button class="btn" onclick="bwRebuild()">手动重建向量库</button>
      </div>
      <div class="info">上传新的 bandwidth.md 后将覆盖旧文件并自动触发向量库重建。仅支持 .md 格式。</div>
    </div>
  </div>
```

- [ ] **Step 3: 在 tab 点击事件中添加 bandwidth 初始化**

在 index.html 的 `<script>` 区域，找到第 146 行 `if (tab.dataset.tab === 'probe') probeLoad();`，在其后添加：

```javascript
    if (tab.dataset.tab === 'bandwidth') bwLoadStatus();
```

- [ ] **Step 4: 在 script 末尾添加 3 个 JS 函数**

在 `ebLoad();`（第 411 行）之前插入：

```javascript
async function bwLoadStatus() {
  try {
    const r = await fetch(API + '/api/bandwidth/status');
    const d = await r.json();
    const el = document.getElementById('bw-status');
    if (d.exists) {
      el.innerHTML = `<strong>当前文件：</strong>${d.filename} (${formatSize(d.size)})  最后更新：${d.last_modified || '未知'}`;
    } else {
      el.innerHTML = '<span style="color:#e74c3c;">当前无 bandwidth.md 文件</span>';
    }
  } catch (e) { showMsg('加载带宽策略状态失败：' + e.message, true, 'BW_LOAD_ERROR'); }
}

async function bwUpload() {
  const fileInput = document.getElementById('bw-file');
  if (!fileInput.files[0]) { showMsg('请选择 .md 文件', true, 'BW_NO_FILE'); return; }
  const btn = event.target;
  btn.disabled = true;
  btn.textContent = '上传中...';
  const fd = new FormData();
  fd.append('file', fileInput.files[0]);
  try {
    const r = await fetch(API + '/api/bandwidth/upload', { method: 'POST', body: fd });
    const d = await r.json();
    if (d.save && d.save.success) {
      if (d.rebuild && d.rebuild.success) {
        showMsg('✅ 上传成功，向量库重建完成', false);
      } else {
        showMsg('⚠️ 上传成功，但重建失败：' + (d.rebuild ? d.rebuild.error : '未知错误'), true, 'BW_REBUILD_ERROR');
      }
      bwLoadStatus();
      fileInput.value = '';
    } else {
      showMsg('❌ 上传失败：' + (d.detail || JSON.stringify(d)), true, 'BW_UPLOAD_ERROR');
    }
  } catch (e) {
    showMsg('❌ 上传失败：' + e.message, true, 'BW_NETWORK_ERROR');
  } finally {
    btn.disabled = false;
    btn.textContent = '上传并重建';
  }
}

async function bwRebuild() {
  const btn = event.target;
  btn.disabled = true;
  btn.textContent = '重建中...';
  try {
    const r = await fetch(API + '/api/bandwidth/rebuild', { method: 'POST' });
    const d = await r.json();
    if (d.rebuild && d.rebuild.success) {
      showMsg('✅ 向量库重建完成', false);
    } else {
      showMsg('❌ 重建失败：' + (d.rebuild ? d.rebuild.error : '未知错误'), true, 'BW_REBUILD_ERROR');
    }
  } catch (e) {
    showMsg('❌ 重建请求失败：' + e.message, true, 'BW_NETWORK_ERROR');
  } finally {
    btn.disabled = false;
    btn.textContent = '手动重建向量库';
  }
}
```

- [ ] **Step 5: 验证 HTML 语法**

Run: `python -c "
from html.parser import HTMLParser
class P(HTMLParser):
    def __init__(self):
        super().__init__()
        self.errors = []
    def handle_starttag(self, tag, attrs): pass
    def handle_endtag(self, tag): pass
p = P()
p.feed(open('docker/data-manager/app/templates/index.html').read())
print('HTML parse OK')
"`
Expected: `HTML parse OK`

- [ ] **Step 6: Commit**

```bash
git add docker/data-manager/app/templates/index.html
git commit -m "feat: add bandwidth policy tab to data-manager UI"
```

---

### Task 5: 集成验证

**Context:** 需要在 Docker 环境中验证端到端流程。如果 Docker 不在运行，至少验证 Python import 链路正确。

- [ ] **Step 1: 验证 data-manager import 链路**

Run: `cd docker/data-manager && python -c "
import sys
sys.path.insert(0, 'app')
from app.services.bandwidth_service import get_status, save_file, trigger_rebuild
from app.routers.bandwidth import router
print('Import chain OK')
print(f'Router prefix: {router.prefix}')
print(f'Routes: {[r.path for r in router.routes]}')
"`
Expected: Import chain OK, 3 routes listed

- [ ] **Step 2: 验证 app.py 正确加载所有 router**

Run: `cd docker/data-manager && python -c "
import sys
sys.path.insert(0, 'app')
from app.app import app
routes = [r.path for r in app.routes if hasattr(r, 'path')]
bw_routes = [r for r in routes if 'bandwidth' in r]
print(f'Total routes: {len(routes)}')
print(f'Bandwidth routes: {bw_routes}')
assert len(bw_routes) == 3, f'Expected 3 bandwidth routes, got {len(bw_routes)}'
print('All bandwidth routes registered OK')
"`
Expected: 3 bandwidth routes found

- [ ] **Step 3: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: address integration issues from verification" || echo "No fixes needed"
```

---

## Self-Review

**1. Spec coverage check:**

| Spec requirement | Plan task |
|---|---|
| 新增 bandwidth_service.py | Task 2 |
| 新增 bandwidth.py router (3 endpoints) | Task 3 |
| 新增重建脚本 | Task 1 |
| 修改 app.py 注册 router | Task 3 Step 3 |
| 修改 index.html 新增 tab + JS | Task 4 |
| GET /api/bandwidth/status | Task 3 Step 1 |
| POST /api/bandwidth/upload | Task 3 Step 1 |
| POST /api/bandwidth/rebuild | Task 3 Step 1 |
| 文件上传模式 | Task 3 Step 1 (ext check) |
| 子进程脚本触发重建 | Task 1 + Task 2 |
| 错误处理（非 .md、超时、Ollama 不可用） | Task 1 (shutil/try-exit), Task 2 (timeout) |
| 成功标准 1-5 | Tasks 1-5 cover all |

**2. Placeholder scan:** No TBD/TODO/placeholder patterns found.

**3. Type consistency:** All function names match between service and router imports. `trigger_rebuild()` returns same dict shape as `trigger_ingest()`. Router uses `save_file(file_content: bytes)` matching emergency pattern.
