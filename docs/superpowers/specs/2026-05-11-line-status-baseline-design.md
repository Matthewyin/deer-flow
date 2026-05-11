# 线路状态基线系统设计

> 日期：2026-05-11
> 状态：已批准

## 1. 背景

dedi agent（通过 `network-ops` MCP server + `bandwidth-management` skill 实现）目前可以查询线路信息、评估带宽策略、生成扩缩容邮件，但缺少**实际运行数据的基线对比能力**。当前评估依赖用户手动提供流量数据（如"P95 到了 5M"），无法自动判断线路是否偏离历史正常水平。

本设计增加**每日线路状态数据采集、基线计算（累计移动平均）、基线对比分析**能力，让 dedi agent 能自动发现偏离基线的线路并给出扩缩容建议。

## 2. 数据源

**输入**：HTML 日报文件（由用户手动上传到 data-manager）。

文件内容为包含 ECharts 图表的 HTML 页面，示例文件见 `docs/lineinfo/世界杯基础架构性能分析日报.html`。

**数据结构**：每个 HTML 文件包含多个线路类别（VPDN终端专线、TLS终端专线、北单售票专线、体彩APP专线、互联网线路），每个类别有 3 类图表：

| 图表类型 | chart ID 模式 | 数据内容 | 单位 |
|----------|---------------|----------|------|
| 带宽流量 | `bandwidth_traffic_{类别}` | 每条线路的**峰值**和**均值** | Kbps |
| 带宽利用率 | `bandwidth_percent_{类别}` | 每条线路的**峰值利用率**和**均值利用率** | % |
| 延迟峰值 | `latency_{类别}` | 每条线路的**延迟峰值** | ms |

**线路命名格式**：
- VPDN：`浙江51`、`内蒙21`（省份+编号）
- TLS/北单/体彩APP：`北京-电信<151>`、`北京-联通<6>`（站点-运营商<专线号>）
- 互联网：`亦庄互联网出口-联通` 等

**数据在 ECharts option JSON 中**：`_originalCategories` 为线路名数组，`series` 数组中每个元素包含 `name`（峰值/均值）和 `data`（数值数组），按线路顺序对应。

## 3. 职责划分

遵循项目已有模式：**data-manager 负责采集/解析/保存文件，MCP server 负责入库/分析**。

| 组件 | 职责 | 新增文件 |
|------|------|----------|
| **data-manager** | HTML 上传、解析 ECharts JSON、保存结构化 JSON 到共享 volume | `services/line_status_service.py`、`routers/line_status.py` |
| **network-ops MCP server** | JSON 入库、CMA 基线计算、基线对比分析、扩缩容建议 | `tools/line_status_ingest.py`、`tools/line_status_compare.py`、`tools/line_status_history.py`、`db/line_status_client.py` |
| **bandwidth-management skill** | 新增流程 E：基线对比分析工作流 | 修改 `SKILL.md` |

## 4. 数据流

```
用户上传 HTML 日报
  → POST /api/line-status/upload (data-manager)
  → line_status_service.parse_html() 解析 ECharts JSON
  → 保存到 /app/.deer-flow/line-status/{YYYY-MM-DD}.json
  → 返回解析结果摘要

dedi agent 调用 ensure_line_status_data (network-ops MCP)
  → 扫描 /app/.deer-flow/line-status/ 目录
  → 读取未入库的 JSON 文件
  → 写入 line_status_daily 表
  → 重新计算 CMA 基线，更新 line_status_baseline 表
  → 返回入库条数 + 基线更新数

dedi agent 调用 line_status_compare (network-ops MCP)
  → 查询指定日期的实际值 + 对应基线值
  → 计算偏差百分比
  → 结合 bandwidth_assess 阈值给出扩缩容建议
  → 返回对比结果

dedi agent 调用 line_status_history (network-ops MCP)
  → 查询指定线路的历史时间序列
  → 返回趋势数据
```

## 5. data-manager 新增模块

### 5.1 API 端点

#### POST /api/line-status/upload

接收 HTML 文件，解析后保存结构化 JSON。

**请求**：`multipart/form-data`，字段 `file`（HTML 文件）。

**响应**：
```json
{
  "report_date": "2026-05-10",
  "saved_path": "/app/.deer-flow/line-status/2026-05-10.json",
  "line_categories": {
    "VPDN终端专线": 68,
    "TLS终端专线": 4,
    "北单售票专线": 2,
    "体彩APP专线": 4,
    "互联网线路": 6
  },
  "total_lines": 84
}
```

#### GET /api/line-status/status

返回当前已上传的文件列表和状态。

### 5.2 解析逻辑 (`line_status_service.py`)

**核心算法**：
1. 用 BeautifulSoup 加载 HTML
2. 遍历所有 `<script>` 标签，匹配 `var option_chart_X = {...}` 模式
3. 提取 chart ID 中的类别名（如 `bandwidth_traffic_VPDN终端专线` → 类别 `VPDN终端专线`，类型 `bandwidth_traffic`）
4. 从 option JSON 中提取 `_originalCategories`（线路名数组）和 `series` 数据
5. 按线路名+类别组装结构化数据

**输出 JSON 格式**：
```json
{
  "report_date": "2026-05-10",
  "source_file": "世界杯基础架构性能分析日报.html",
  "parsed_at": "2026-05-11T10:00:00",
  "line_categories": {
    "VPDN终端专线": [
      {
        "line_name": "浙江51",
        "traffic_peak_kbps": 8629,
        "traffic_avg_kbps": 4880,
        "util_peak_pct": 100,
        "util_avg_pct": 61.01,
        "latency_peak_ms": 191
      }
    ],
    "TLS终端专线": [
      {
        "line_name": "北京-电信<151>",
        "traffic_peak_kbps": 23274,
        "traffic_avg_kbps": 15276,
        "util_peak_pct": 100,
        "util_avg_pct": 76.38,
        "latency_peak_ms": 9
      }
    ]
  }
}
```

**保存路径**：`{SHARED_DATA_DIR}/line-status/{YYYY-MM-DD}.json`，其中 `SHARED_DATA_DIR` 为环境变量，默认 `/app/.deer-flow`。

## 6. network-ops MCP Server 新增

### 6.1 数据库表

新增 2 张表到现有 `network_ops.db`：

```sql
CREATE TABLE IF NOT EXISTS line_status_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date TEXT NOT NULL,
    line_category TEXT NOT NULL,
    line_name TEXT NOT NULL,
    traffic_peak_kbps REAL,
    traffic_avg_kbps REAL,
    util_peak_pct REAL,
    util_avg_pct REAL,
    latency_peak_ms REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(report_date, line_category, line_name)
);

CREATE TABLE IF NOT EXISTS line_status_baseline (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    line_category TEXT NOT NULL,
    line_name TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    sample_count INTEGER NOT NULL,
    avg_traffic_peak_kbps REAL,
    avg_traffic_avg_kbps REAL,
    avg_util_peak_pct REAL,
    avg_util_avg_pct REAL,
    avg_latency_peak_ms REAL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(line_category, line_name, as_of_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_date ON line_status_daily(report_date);
CREATE INDEX IF NOT EXISTS idx_daily_line ON line_status_daily(line_category, line_name);
CREATE INDEX IF NOT EXISTS idx_baseline_line ON line_status_baseline(line_category, line_name);
```

### 6.2 MCP 工具

#### `ensure_line_status_data`

**功能**：扫描共享 volume 中的新 JSON 文件，入库并更新基线。

**输入**：无参数。

**输出**：
```json
{
  "new_files": 1,
  "lines_ingested": 84,
  "baselines_updated": 84,
  "latest_date": "2026-05-10"
}
```

**逻辑**：
1. 扫描 `/app/.deer-flow/line-status/` 目录
2. 对比 `line_status_daily` 表中已有的 `report_date`，找出新文件
3. 读取 JSON → 逐条 INSERT OR IGNORE 到 `line_status_daily`
4. 对每条新入库的线路，重新计算 CMA 基线：
   - `avg_X = SUM(X) / COUNT(*)` over all historical days for that (line_category, line_name)
   - UPSERT 到 `line_status_baseline`

#### `line_status_compare`

**功能**：指定日期的实际值 vs 基线值对比，输出扩缩容建议。

**输入**：
- `date`（可选，默认最近一天）
- `line_category`（可选，筛选线路类别）
- `line_name`（可选，筛选具体线路）

**输出**：
```json
{
  "compare_date": "2026-05-10",
  "baseline_as_of": "2026-05-10",
  "results": [
    {
      "line_category": "TLS终端专线",
      "line_name": "北京-电信<151>",
      "actual": {
        "traffic_peak_kbps": 23274,
        "util_peak_pct": 100,
        "latency_peak_ms": 9
      },
      "baseline": {
        "avg_traffic_peak_kbps": 20000,
        "avg_util_peak_pct": 85,
        "avg_latency_peak_ms": 10,
        "sample_count": 5
      },
      "deviation_pct": {
        "traffic_peak": 16.37,
        "util_peak": 17.65,
        "latency_peak": -10.0
      },
      "recommendation": "scale_up",
      "reason": "利用率峰值较基线高 17.65%，已达 100%"
    }
  ],
  "summary": {
    "total_lines": 84,
    "scale_up": 5,
    "scale_down": 2,
    "normal": 77
  }
}
```

**扩缩容判定规则**：
- `util_peak_pct` 偏差 > +20% 且实际值 > 40% → **scale_up**
- `util_avg_pct` 偏差 < -30% 且实际值 < 15% → **scale_down**
- `latency_peak_ms` 偏差 > +50% → **attention**（网络质量关注）
- 其他 → **normal**

#### `line_status_history`

**功能**：查询指定线路的历史趋势数据。

**输入**：
- `line_name`（必填）
- `line_category`（可选）
- `days`（可选，默认 30）

**输出**：
```json
{
  "line_name": "北京-电信<151>",
  "line_category": "TLS终端专线",
  "days_requested": 30,
  "days_available": 5,
  "history": [
    {
      "date": "2026-05-10",
      "traffic_peak_kbps": 23274,
      "util_peak_pct": 100,
      "latency_peak_ms": 9,
      "baseline_traffic_peak_kbps": 20000,
      "baseline_util_peak_pct": 85
    }
  ]
}
```

## 7. bandwidth-management Skill 更新

在 `skills/custom/bandwidth-management/SKILL.md` 中新增：

### 流程 E：基线对比分析

**触发**：当用户要求分析线路运行状况、趋势、是否需要扩缩容，且不需要手动提供流量数据时。

**步骤**：
1. 调用 `ensure_line_status_data` 确保数据已入库
2. 调用 `line_status_compare` 获取对比结果
3. 对建议扩容的线路，调用 `line_info_query` 获取线路基本信息
4. 对建议扩容的线路，调用 `bandwidth_assess` 评估具体带宽档位
5. 综合基线偏差 + 带宽策略，给出最终建议
6. 如需操作，调用 `email_generate` 生成邮件

### 新增工具表格条目

| `ensure_line_status_data` | 入库线路状态数据并更新基线 | JSON 文件 (共享 volume) |
| `line_status_compare` | 实际值 vs 基线对比分析 | SQLite (network_ops.db) |
| `line_status_history` | 查询历史趋势 | SQLite (network_ops.db) |

## 8. 配置变更

### extensions_config.json

在 `network-ops` MCP server 的 `env` 中新增：
```json
{
  "LINE_STATUS_DATA_DIR": "/app/.deer-flow/line-status"
}
```

### docker-compose-dev.yaml

在 langgraph 和 data-manager 的 volumes 中确保共享目录挂载：
```yaml
- docker/volumes/deer-flow-data:/app/.deer-flow
```
（已存在，无需额外修改。`line-status/` 子目录会自动创建。）

## 9. data-manager UI 新增

在 data-manager 的 WebUI 中增加"线路状态"选项卡：
- 上传区域：接受 .html 文件
- 状态显示：已上传的文件列表（日期 + 线路数）
- 类似现有 bandwidth 选项卡的模式

## 10. 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `docker/data-manager/app/services/line_status_service.py` | 新建 | HTML 解析 + JSON 保存 |
| `docker/data-manager/app/routers/line_status.py` | 新建 | 上传 API 端点 |
| `docker/data-manager/app/app.py` | 修改 | 注册 line_status router |
| `docker/data-manager/app/templates/index.html` | 修改 | 增加"线路状态"选项卡 |
| `mcp-servers/network-ops/db/line_status_client.py` | 新建 | SQLite 入库 + 基线计算 |
| `mcp-servers/network-ops/tools/line_status_ingest.py` | 新建 | ensure_line_status_data 工具 |
| `mcp-servers/network-ops/tools/line_status_compare.py` | 新建 | line_status_compare 工具 |
| `mcp-servers/network-ops/tools/line_status_history.py` | 新建 | line_status_history 工具 |
| `mcp-servers/network-ops/server.py` | 修改 | 注册 3 个新工具 |
| `mcp-servers/network-ops/config.py` | 修改 | 增加 LINE_STATUS_DATA_DIR 配置 |
| `skills/custom/bandwidth-management/SKILL.md` | 修改 | 增加流程 E + 工具表条目 |
| `extensions_config.json` | 修改 | network-ops env 增加 LINE_STATUS_DATA_DIR |

## 11. 基线算法详细说明

### 累计移动平均（CMA）

第 N 天的基线值 = (Day1 + Day2 + ... + DayN) / N

**SQL 实现**：
```sql
INSERT OR REPLACE INTO line_status_baseline (
    line_category, line_name, as_of_date, sample_count,
    avg_traffic_peak_kbps, avg_traffic_avg_kbps,
    avg_util_peak_pct, avg_util_avg_pct,
    avg_latency_peak_ms, updated_at
)
SELECT
    line_category,
    line_name,
    :as_of_date,
    COUNT(*),
    AVG(traffic_peak_kbps),
    AVG(traffic_avg_kbps),
    AVG(util_peak_pct),
    AVG(util_avg_pct),
    AVG(latency_peak_ms),
    CURRENT_TIMESTAMP
FROM line_status_daily
WHERE line_category = :line_category
  AND line_name = :line_name
GROUP BY line_category, line_name;
```

每次入库新一天的数据后，对涉及的每条 (line_category, line_name) 组合执行一次上述 SQL，基线自动包含所有历史数据。

## 12. 边界情况处理

| 场景 | 处理方式 |
|------|----------|
| 同一天重复上传 | `UNIQUE(report_date, line_category, line_name)` 保证幂等，`INSERT OR IGNORE` |
| HTML 中图表格式变化 | 解析时做健壮性检查，缺失字段存 NULL |
| 线路名格式不统一 | 保持原始名称，不做标准化（与 MySQL line_info 表的线路名映射由 Agent 智能处理） |
| 无历史基线（第一天） | 基线 = 实际值，偏差 = 0，无扩缩容建议 |
| JSON 文件损坏 | 跳过该文件，记录错误日志 |
