# 带宽策略文档管理设计

> 统一入口：在 data-manager WebUI 中增加带宽策略选项卡，上传覆盖旧文件并自动触发向量库重建。

## 背景

当前 `docs/bandwidth.md` 是 bandwidth 策略搜索工具（`policy_search`）的唯一数据源。修改该文件后，向量库不会自动更新——`BandwidthRAG.initialize()` 仅在 `persist_dir` 不存在时才从 md 文件构建向量库。

应急预案（ops-knowledge）已通过 data-manager 提供了完整的上传→入库流程。带宽策略缺少同样的管理入口。

## 决策记录

| 决策项 | 选项 | 结论 |
|--------|------|------|
| 文档管理方式 | 文本编辑器 / 文件上传 / 两者 | **文件上传**（与应急预案 tab 一致） |
| 重建触发机制 | 进程内调用 / 子进程脚本 / 删目录惰性重建 | **子进程脚本**（解耦，好维护） |

## 架构

### 新增文件

| 文件 | 说明 |
|------|------|
| `docker/data-manager/app/services/bandwidth_service.py` | 服务层：文件保存、状态查询、重建触发 |
| `docker/data-manager/app/routers/bandwidth.py` | API 路由：3 个端点 |
| `docs/rebuild_bandwidth_vectors.py` | 重建脚本：删除旧向量库→读取 md→chunk→embed→写入（放在 docs/ 下因为该目录已映射到容器内 /app/docs/） |

### 修改文件

| 文件 | 变更 |
|------|------|
| `docker/data-manager/app/app.py` | 注册 bandwidth router |
| `docker/data-manager/app/templates/index.html` | 新增 tab + JS 函数 |

### 不修改的文件

- `mcp-servers/network-ops/` 下所有代码（纯复用）
- `extensions_config.json`（路径不变）
- Docker 配置文件

## 数据流

```
用户上传 bandwidth.md (.md)
  → POST /api/bandwidth/upload
  → bandwidth_service.save_file()
      覆盖 /app/docs/bandwidth.md
  → bandwidth_service.trigger_rebuild()
      subprocess.run(["python", "/app/docs/rebuild_bandwidth_vectors.py"])
      → 脚本内部：
          1. import mcp-servers/network-ops/config.py (get_config)
          2. import mcp-servers/network-ops/rag/bandwidth_rag.py (BandwidthRAG)
          3. shutil.rmtree(persist_dir)  删除旧向量库
          4. BandwidthRAG.initialize()   从新 md 构建向量库
          5. 输出结果 JSON
  → 返回 {save: {...}, rebuild: {...}} 到前端
  → 前端显示成功/失败消息
```

## API 端点

### GET /api/bandwidth/status

返回当前 bandwidth.md 的文件信息。

```json
{
  "filename": "bandwidth.md",
  "size": 12345,
  "last_modified": "2026-04-23T10:00:00",
  "exists": true
}
```

### POST /api/bandwidth/upload

接收 .md 文件，覆盖 `docs/bandwidth.md`，触发重建。

- Content-Type: `multipart/form-data`
- 字段: `file`（.md 文件）
- 返回:

```json
{
  "save": {"success": true, "path": "/app/docs/bandwidth.md", "size": 12345},
  "rebuild": {"success": true, "chunks": 12, "elapsed": 8}
}
```

### POST /api/bandwidth/rebuild

手动触发重建（用现有文件），不上传新文件。

```json
{
  "rebuild": {"success": true, "chunks": 12, "elapsed": 8}
}
```

## 重建脚本 (docs/rebuild_bandwidth_vectors.py)

与 `docs/batch_ingest_ops_knowledge.py` 模式一致，放在 `docs/` 目录下（因为 data-manager Docker volume 已映射 `../docs:/app/docs`）：

1. 通过 `sys.path` 引入 `mcp-servers/network-ops/` 模块（容器内 `/app/mcp-servers`）
2. 调用 `get_config()` 获取配置
3. 删除 `chroma.persist_dir` 目录（如果存在）
4. 调用 `BandwidthRAG.initialize()` 从 `chroma.md_path` 构建
5. 输出 chunk 数量和耗时
6. 返回退出码 0（成功）/ 1（失败）

data-manager bandwidth_service 中引用路径：`REBUILD_SCRIPT = "/app/docs/rebuild_bandwidth_vectors.py"`

## UI 设计

在 index.html 的 tabs 区域增加第 4 个 tab：

- Tab 名称：**带宽策略**
- 面板布局（参照应急预案 tab）：
  - 卡片标题：「带宽扩缩容指南文档」
  - 当前文件信息：文件名、大小、最后修改时间
  - 文件上传区：file input（accept=".md"）+ 「上传并重建」按钮
  - 手动重建按钮：「手动重建向量库」
  - 提示文字：「上传新的 bandwidth.md 后将覆盖旧文件并自动触发向量库重建。仅支持 .md 格式。」

JS 函数：
- `bwLoadStatus()` — 加载文件状态
- `bwUpload()` — 上传文件并触发重建
- `bwRebuild()` — 手动触发重建

## 错误处理

| 场景 | 处理 |
|------|------|
| 上传非 .md 文件 | 拒绝，返回 400 |
| bandwidth.md 文件不存在 | status 返回 exists=false，重建时返回错误 |
| 重建脚本超时 | 120s 超时，返回失败 |
| Ollama 服务不可用 | 脚本捕获异常，返回失败信息 |
| 向量库目录删除失败 | 脚本捕获异常，返回失败信息 |

## 成功标准

1. 用户通过 data-manager 上传新的 bandwidth.md → 旧文件被覆盖
2. 上传后自动触发重建 → 向量库包含新文件的 chunks
3. dedi agent 调用 policy_search → 返回新文件中的内容
4. 手动重建按钮可用 → 用现有文件重建向量库
5. 重建结果（成功/失败、chunks 数量）显示在前端
