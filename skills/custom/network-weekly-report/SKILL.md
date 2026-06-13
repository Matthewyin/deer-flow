---
name: network-weekly-report
description: >
  生成网络专线带宽 HTML 趋势报告（含交互式 ECharts 图表）。当用户要求生成网络周报、带宽周报、
  带宽趋势报告、带宽曲线报告、网络日报、带宽日报时触发此技能。也适用于"生成本周带宽报告"、
  "看一下最近7天/15天的专线流量趋势"、"出一份带宽报表"、"帮我做一份网络监控报告"等场景。
  只要涉及专线带宽监控数据可视化和 HTML 报告生成，都应使用此技能。
---

# 网络专线带宽趋势报告生成器

生成交互式 HTML 带宽趋势报告，包含 ECharts 折线图、逐日明细表和总结汇总表。

## 工作流程

### 第 1 步：确定查询参数

与用户确认报告参数（如果用户没有明确指定）：

- **时间范围**：默认取最近 7 天。用户可自定义天数（如 3 天、15 天、30 天）。
  - 结束日期取今天或昨天（今天是 `{current_date}`）
  - 开始日期 = 结束日期 - (天数 - 1)
- **线路筛选**：默认查询以下线路：
  - 混合云TLS售票-腾讯公有云2条线路
  - 混合云TLS售票-阿里公有云2条线路
  - 北京单场售票2条线路
  - 两网三中心4条线路
  - 西五环互联网B区3条线路。
用户可指定线路组（如"只看 TLS 相关",或所有线路）
- **报告类型**：
  - **周报**（默认）：7 天数据，标题含"周报"
  - **日报**：1 天或最近 2-3 天数据，标题含"日报"

### 第 2 步：查询数据

调用 `network-ops_bandwidth_records_query` 工具获取原始数据。调用时使用以下参数：

```
start_date: <开始日期 YYYY-MM-DD>
end_date: <结束日期 YYYY-MM-DD>
limit: 500
```

该工具返回的每条记录包含以下关键字段：

| 字段 | 说明 |
|------|------|
| `report_date` | 报告日期 |
| `line_group` | 线路组名 |
| `line_no` | 线路编号 |
| `carrier` | 运营商 |
| `usage` | 用途描述 |
| `bandwidth_mbps` | 当日带宽档位 |
| `in_peak_mbps` | 入向峰值带宽 |
| `out_peak_mbps` | 出向峰值带宽 |
| `in_avg_mbps` | 入向均值带宽 |
| `out_avg_mbps` | 出向均值带宽 |
| `latency_avg_ms` | 平均延迟 |
| `bw_peak_baseline_mbps` | 峰值基线 |
| `latency_baseline_ms` | 延迟基线 |

### 第 3 步：组织数据结构

将原始记录按线路组织。每条线路生成一个数据字典：

```python
{
    "name": "#151 电信",       # 线路编号 + 运营商
    "color": "#5470C6",        # 按运营商映射颜色
    "carrier": "电信",
    "bw": 20,                  # 当前带宽档位（取最后一天的 bandwidth_mbps）
    "ip": [...],               # 每日 in_peak_mbps
    "op": [...],               # 每日 out_peak_mbps
    "ia": [...],               # 每日 in_avg_mbps
    "oa": [...],               # 每日 out_avg_mbps
    "lat": [...],              # 每日 latency_avg_ms
    "bpbl": [...],             # 每日 bw_peak_baseline_mbps
    "bws": [...],              # 每日 bandwidth_mbps
    "usage": "混合云TLS售票-腾讯公有云"
}
```

**衍生计算**（每条线路）：

- `max_peak[i]` = `max(in_peak_mbps[i], out_peak_mbps[i])` — 取入向/出向峰值较大值
- `max_avg[i]` = `max(in_avg_mbps[i], out_avg_mbps[i])` — 取入向/出向均值较大值
- `peak_util[i]` = `max_peak[i] / bandwidth_mbps[i] × 100` — 峰值利用率（%）
- `avg_util[i]` = `max_avg[i] / bandwidth_mbps[i] × 100` — 均值利用率（%）

**线路分组**：按 `usage` 字段将线路归类到组。每组生成一套图表 + 明细表。

**颜色映射**（按运营商）：
- 电信 → `#5470C6`
- 联通 → `#EE6666`
- 移动 → `#91CC75`

### 第 4 步：生成 Python 脚本

读取 `scripts/gen_report.py`（本 skill 附带的报告生成脚本），将组织好的数据填入脚本中的 `LINES` 字典和 `GROUPS` 列表，设置好 `dates`、标题、日期范围等参数，然后执行脚本生成 HTML。

**脚本使用方法**：

1. 复制 `scripts/gen_report.py` 到工作目录
2. 修改脚本中的以下硬编码数据区域：
   - `dates` 列表：X 轴日期标签
   - `LINES` 字典：所有线路数据
   - `GROUPS` 列表：分组信息
   - 标题、副标题中的日期范围和报告类型
3. 执行脚本：`python gen_report.py`
4. 输出文件默认写到 `/mnt/user-data/outputs/带宽曲线报告.html`

**脚本生成规则**（详见 `references/chart_spec.md`）：

- 每个线路组生成 3 张 ECharts 折线图：带宽峰值&均值、利用率、延迟
- 带宽图：Y 轴最大值必须等于当前线路组内所有线路、所有日期的最大 `bandwidth_mbps`，不得按峰值流量动态放大
- 带宽图：每条线路有红色虚线 80% 带宽阈值 markLine
- 利用率图：第一条 series 上有 80% 阈值 markLine
- 延迟图：仅画延迟曲线，无基线
- 每组附逐日明细表
- 报告末尾附总结汇总表（含 ✅/⚠️/🔴 评估）
- 自包含 HTML，仅依赖 ECharts CDN

### 第 5 步：呈现报告

将生成的 HTML 文件通过 `present_files` 呈现给用户。

如果用户需要调整（修改颜色、增减图表、调整阈值等），直接修改脚本中的对应部分并重新执行。

---

## 关键约束

1. **不画基线**：`bw_peak_baseline_mbps` 和 `latency_baseline_ms` 只在数据明细表中展示，不作为曲线出现在任何图表中。
2. **80% 阈值**：带宽图阈值 = `带宽 × 80%`（Mbps），利用率图阈值 = `80%`。不做其他阈值。
3. **带宽图 Y 轴**：最大值必须等于当前线路组内所有线路、所有日期的最大 `bandwidth_mbps`，不得使用 `max_peak × 1.2` 或其他动态放大值。
4. **max_peak/max_avg 取双向较大值**：`max(in, out)`，不是简单取单方向。
5. **带宽可能变化**：同一线路在不同日期的 bandwidth_mbps 可能不同（如扩容 20M→40M），阈值 markLine 使用当前带宽计算，Y 轴上限取该组全周期最大带宽。
6. **Python 3.10 兼容**：f-string 中不能包含反斜杠。脚本使用 `%` 格式化拼接 ECharts option JSON。
7. **单文件 HTML**：所有 CSS/JS 内嵌，仅依赖 ECharts CDN。
8. **响应式**：window resize 事件触发所有 ECharts 实例 resize()。

## 参考文档

- `references/chart_spec.md` — 图表规格详细说明（颜色、线型、ECharts 配置、样式规范）
- `scripts/gen_report.py` — 报告生成脚本模板
