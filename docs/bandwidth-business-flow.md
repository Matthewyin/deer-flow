# 线路带宽管理系统 — 业务流程文档

> 版本：v2.0（废弃 MySQL 依赖，改为 HTML 直接提取 + SQLite 存储）

---

## 1. 系统目标

从每日 HTML 网络日报中提取线路流量数据，存入 SQLite，按《数据中心网络专线带宽扩缩容指南》自动判断是否需要扩容/缩容，并生成邮件建议。

---

## 2. 数据源

### 2.1 HTML 日报结构

文件示例：`network_report_2026-05-21.html`

**"线路"表格位于第 700-2467 行**，结构：

```html
<div class="base_section">
  <h3 style="text-align:center;">线路</h3>
  <table>
    <tr class="header">
      <td>分组</td><td>专线序号</td>...<td>延迟阈值(ms)</td>
    </tr>
    <tr class="sub_header">
      <td rowspan="69">VPDN终端专线</td>
      <td>39</td>...
    </tr>
    ...
  </table>
</div>
```

### 2.2 分组统计（6 组，83 条线路）

| 分组 | 行数 |
|------|------|
| VPDN终端专线 | 69 |
| TLS终端专线 | 4 |
| 北单售票专线 | 2 |
| 体彩APP专线 | 4 |
| 亦庄互联网B区线路 | 1 |
| 西五环互联网B区线路 | 3 |

### 2.3 21 列字段

| 序号 | 字段名 | 类型 | 示例值 | 备注 |
|------|--------|------|--------|------|
| 1 | 分组 | string | VPDN终端专线 | rowspan 合并，需继承 |
| 2 | 专线序号 | int | 39 | |
| 3 | 省份 | string | HL黑龙江(哈尔滨)23 | 直接取字段值 |
| 4 | 运营商 | string | 联通 | |
| 5 | 用途 | string | 数据端 | |
| 6 | 带宽 | string | 6M | 需解析数值+单位 |
| 7 | 长途线路编号 | string | 北京哈尔滨ONE0132NP | 核心标识字段 |
| 8 | 入峰值(Mbps) | float | 0.05 | |
| 9 | 入均值(Mbps) | float | 0.01 | |
| 10 | 入峰值利用率(%) | float | 0.90 | |
| 11 | 入峰值时间 | string | 18:45 | |
| 12 | 出峰值(Mbps) | float | 0.07 | |
| 13 | 出均值(Mbps) | float | 0.01 | |
| 14 | 出峰值利用率(%) | float | 1.21 | |
| 15 | 出峰值时间 | string | 18:45 | |
| 16 | 延迟均值(ms) | float | 33.92 | |
| 17 | 带宽峰值基线(Mbps) | float | 0.29 | |
| 18 | 带宽利用率阈值(%) | int | 40 | |
| 19 | 延迟基线(ms) | float | 33.14 | |
| 20 | 延迟阈值(ms) | float | 101.64 | |

### 2.4 报告日期

从 HTML 开头的标题区域提取（如 `2026年05月21日`），非入库时间。

---

## 3. 数据流

```
HTML 日报（用户上传到 data-manager）
       │
       ▼
┌─────────────────────────────────────┐
│ data-manager（解析 + 存储）          │
│                                     │
│  1. 定位 <h3>线路</h3> 对应表格      │
│  2. 解析 21 列表格数据               │
│  3. 处理 rowspan 分组继承            │
│  4. 提取报告日期                     │
│  5. 写入 bandwidth_lines SQLite 表   │
└─────────────────────────────────────┘
       │
       ▼
bandwidth_lines 表（SQLite: network_ops.db）
       │
       ▼
┌─────────────────────────────────────┐
│ bandwidth-management skill          │
│ （查询 + 判断 + 生成邮件）           │
│                                     │
│  1. 查询 SQLite（默认 15 天）        │
│  2. 按线路编号聚合                   │
│  3. 计算 P95 利用率                  │
│  4. 对比扩缩容阈值                   │
│  5. 生成邮件建议                     │
└─────────────────────────────────────┘
```

---

## 4. SQLite 表结构

### 4.1 bandwidth_lines 表

> 存储在 `network_ops.db`（与现有表同库）

```sql
CREATE TABLE IF NOT EXISTS bandwidth_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date TEXT NOT NULL,           -- 报告日期 YYYY-MM-DD
    line_group TEXT NOT NULL,            -- 分组（如 VPDN终端专线）
    line_no INTEGER NOT NULL,            -- 专线序号
    province TEXT,                       -- 省份（如 HL黑龙江(哈尔滨)23）
    carrier TEXT,                        -- 运营商（联通/电信）
    usage TEXT,                          -- 用途（数据端/本地互联）
    bandwidth_mbps INTEGER,              -- 带宽数值（6M → 6）
    long_distance_no TEXT,               -- 长途线路编号（核心标识）
    in_peak_mbps REAL,                   -- 入峰值(Mbps)
    in_avg_mbps REAL,                    -- 入均值(Mbps)
    in_peak_util_pct REAL,              -- 入峰值利用率(%)
    in_peak_time TEXT,                   -- 入峰值时间
    out_peak_mbps REAL,                  -- 出峰值(Mbps)
    out_avg_mbps REAL,                   -- 出均值(Mbps)
    out_peak_util_pct REAL,             -- 出峰值利用率(%)
    out_peak_time TEXT,                  -- 出峰值时间
    latency_avg_ms REAL,                -- 延迟均值(ms)
    bw_peak_baseline_mbps REAL,         -- 带宽峰值基线(Mbps)
    bw_util_threshold_pct INTEGER,      -- 带宽利用率阈值(%)
    latency_baseline_ms REAL,           -- 延迟基线(ms)
    latency_threshold_ms REAL,          -- 延迟阈值(ms)
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(report_date, long_distance_no)  -- 每天每条线路唯一
);
```

### 4.2 索引

```sql
CREATE INDEX IF NOT EXISTS idx_bl_date ON bandwidth_lines(report_date);
CREATE INDEX IF NOT EXISTS idx_bl_ldn ON bandwidth_lines(long_distance_no);
CREATE INDEX IF NOT EXISTS idx_bl_date_ldn ON bandwidth_lines(report_date, long_distance_no);
```

---

## 5. data-manager 解析逻辑

### 5.1 解析流程

```
输入：HTML 文件
  │
  ├─ 1. 提取报告日期（从 HTML 标题区域）
  │
  ├─ 2. 定位 <div class="base_section"> 中
  │     <h3> 包含 "线路" 的表格
  │
  ├─ 3. 遍历 <tr class="sub_header"> 数据行
  │     ├─ 处理 rowspan：空 <td> 继承上一行分组名
  │     ├─ 解析 21 列字段值
  │     └─ 带宽字段：解析 "6M" → 6
  │
  ├─ 4. 去重检查（report_date + long_distance_no）
  │
  └─ 5. 批量 INSERT 到 bandwidth_lines 表
```

### 5.2 关键解析规则

| 字段 | 解析规则 |
|------|----------|
| 分组 | rowspan 继承；非 rowspan 行直接取值 |
| 带宽 | `"6M"` → `6`，`"300M"` → `300`，`"2M"` → `2` |
| 省份 | 直接取 HTML 字段值，不做正则提取 |
| 长途线路编号 | 直接取值，作为核心标识（可能为空） |
| 报告日期 | 从 HTML 标题提取，非文件上传时间 |

---

## 6. bandwidth-management skill 判断逻辑

### 6.1 查询参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 时间范围 | 最近 15 个自然日 | 用户可指定固定日期范围 |
| 统计周期 | 15 天 | 剔除春节、国庆等休市期 |
| 数据源 | bandwidth_lines 表 | 不再查 MySQL |

### 6.2 判断流程

```
用户输入："你检查一下哪些线路带宽需要调整"
  │
  ├─ 1. 查询 bandwidth_lines 最近 15 天数据
  │     （或用户指定的日期范围）
  │
  ├─ 2. 按长途线路编号(long_distance_no)分组
  │
  ├─ 3. 每条线路计算：
  │     ├─ P95 入峰值利用率 = percentile(in_peak_util_pct, 95)
  │     ├─ P95 出峰值利用率 = percentile(out_peak_util_pct, 95)
  │     ├─ P95 流量 = percentile(max(in_peak_mbps, out_peak_mbps), 95)
  │     └─ 当前带宽 = bandwidth_mbps
  │
  ├─ 4. 扩容判断：
  │     └─ P95 利用率 > 40% → 建议扩容
  │         └─ 查对照表确定目标带宽
  │
  ├─ 5. 缩容判断：
  │     └─ P95 流量 < 下一档带宽 × 35% → 建议缩容
  │         └─ 查对照表确定目标带宽
  │
  ├─ 6. 延迟检查（辅助指标）：
  │     └─ 延迟均值 > 延迟阈值 → 标记异常
  │
  └─ 7. 生成邮件建议（按 bandwidth.md 模板）
```

### 6.3 带宽配置标准对照表

| 当前带宽 | 扩容触发 (>40%) | 扩容目标 | 缩容触发 (<下一档×35%) | 缩容目标 |
|----------|----------------|----------|----------------------|----------|
| 2M | > 0.8M | 4M | - | - |
| 4M | > 1.6M | 6M | < 0.7M | 2M |
| 6M | > 2.4M | 8M | < 1.4M | 4M |
| 8M | > 3.2M | 10M | < 2.1M | 6M |
| 10M | > 4.0M | 20M | < 2.8M | 8M |
| 20M | > 8.0M | 30M | < 3.5M | 10M |
| 30M | > 12.0M | 40M | < 7.0M | 20M |
| 40M | > 16.0M | 50M | < 10.5M | 30M |

### 6.4 邮件模板

按 bandwidth.md 中的四种模板生成：
- **常态化扩容**：P95 利用率 > 40%，业务自然增长
- **临时扩容**：重大赛事/活动预测
- **应急扩容**：实时监控突发高负载
- **缩容**：P95 流量持续低于下一档 × 35%

---

## 7. MCP server 调整

### 7.1 network-ops MCP server

需要修改的工具：

| 工具 | 变更 |
|------|------|
| `line_status_ingest.py` | 改为调用 bandwidth_lines 表（非原 line_status 表） |
| `line_status_compare.py` | 改为查询 bandwidth_lines + bandwidth.md 规则判断 |
| `line_status_client.py` | 增加 bandwidth_lines 表的 CRUD 方法 |

### 7.2 新增工具（建议）

| 工具 | 职责 |
|------|------|
| `bandwidth_check` | 查询 bandwidth_lines，按规则判断，返回扩缩容建议 |
| `bandwidth_report` | 生成邮件内容（按 bandwidth.md 模板） |

---

## 8. 与旧系统的差异

| 项目 | 旧方案 | 新方案 |
|------|--------|--------|
| 数据来源 | ECharts 图表 JSON | HTML 21 列表格 |
| 标识字段 | line_name（从 ECharts 提取） | long_distance_no（长途线路编号） |
| 存储位置 | line_status 表 | bandwidth_lines 表 |
| 字段数量 | ~6 个 | 20 个（完整 21 列减去分组） |
| MySQL 依赖 | 需要 lines_info 表匹配 | **无 MySQL 依赖** |
| 省份获取 | 正则从 line_name 提取 | 直接取 HTML 字段值 |
| 延迟数据 | 无 | 有（延迟均值 + 基线 + 阈值） |
| 方向分离 | 无（仅有峰值） | 入/出方向分别有峰值+利用率 |

---

## 9. 实施步骤

| 步骤 | 内容 | 涉及文件 |
|------|------|----------|
| 1 | 在 network_ops.db 创建 bandwidth_lines 表 | `mcp-servers/network-ops/db/` |
| 2 | data-manager 增加 21 列表格解析逻辑 | `docker/data-manager/app/services/line_status_service.py` |
| 3 | 解析后写入 bandwidth_lines 表 | 同上 |
| 4 | MCP server 增加 bandwidth 查询工具 | `mcp-servers/network-ops/tools/` |
| 5 | bandwidth-management skill 适配新逻辑 | `skills/custom/bandwidth-management/` |
| 6 | 实现 P95 计算 + 扩缩容判断 | skill 或 MCP tool |
| 7 | 邮件模板生成 | skill |
