---
name: network-weekly-report
description: >
  生成网络专线带宽 HTML 趋势报告（含交互式 ECharts 图表）。当用户要求生成网络周报、带宽周报、
  带宽趋势报告、带宽曲线报告、网络日报、带宽日报时触发此技能。也适用于"生成本周带宽报告"、
  "看一下最近7天/15天的专线流量趋势"、"出一份带宽报表"、"帮我做一份网络监控报告"等场景。
  只要涉及专线带宽监控数据可视化和 HTML 报告生成，都应使用此技能。
---

# 网络专线带宽趋势报告生成器

本技能只负责把用户意图转成 `network-ops` MCP 工具参数。查询、数据整理、图表数据结构生成和 HTML 渲染都必须由 `network-ops_bandwidth_report_generate` 完成。

## 工作流程

### 第 1 步：确定报告参数

如果用户没有明确指定，使用以下默认值：

- **时间范围**：最近 7 天。
  - `end_date` 留空时，工具会自动取数据库中最新可用日期。
  - `start_date` 留空时，工具会按 `days` 自动计算。
- **报告类型**：
  - 7 天及以上默认 `周报`
  - 1 到 3 天默认 `日报`
- **线路筛选**：
  - 用户未指定时，不传筛选条件，生成所有匹配线路的报告。
  - 用户指定线路组时，传 `line_group`，如 `TLS终端专线`、`西五环互联网B区线路`。
  - 用户指定业务用途时，传 `usage_keyword`，如 `混合云TLS`、`北京单场`、`本地互联`。
  - 用户指定线路编号时，传 `long_distance_no`，多个编号可用空格、逗号或分号分隔。

### 第 2 步：调用 network-ops 报表工具

必须调用：

```text
network-ops_bandwidth_report_generate(
  days=<天数>,
  start_date=<开始日期 YYYY-MM-DD，可空>,
  end_date=<结束日期 YYYY-MM-DD，可空>,
  line_group=<线路组关键词，可空>,
  usage_keyword=<用途关键词，可空>,
  long_distance_no=<线路编号，可空>,
  report_type=<周报/日报，可空>,
  output_filename=<HTML文件名>
)
```

工具会在内部完成：

- 查询 `network_ops.db.bandwidth_lines`
- 按日期和线路补齐数据
- 按 `usage` 生成图表分组
- 计算 `max_peak = max(in_peak_mbps, out_peak_mbps)`
- 计算 `max_avg = max(in_avg_mbps, out_avg_mbps)`
- 计算峰值利用率和均值利用率
- 调用标准 HTML 渲染脚本生成报告

### 第 3 步：保存并呈现报告

工具返回 `ok: true` 时：

1. 将返回的 `html` 原样写入 `suggested_output_path`，通常是 `/mnt/user-data/outputs/带宽曲线报告.html`。
2. 调用 `present_files` 呈现该 HTML 文件。

工具返回 `ok: false` 时，直接把错误原因反馈给用户。不要自行改写算法或临时写脚本绕过。

## 禁止事项

1. **禁止先调用 `network-ops_bandwidth_records_query` 再自行整理 `report_config`**。该工具只用于用户明确要求查看原始记录或核查字段，不用于报表生成。
2. **禁止新写 `gen_weekly.py`、Python 生成器或 HTML 拼接脚本**。
3. **禁止复制、读取、改写或直接执行 `scripts/gen_report.py`**。该脚本只作为 `network-ops_bandwidth_report_generate` 的内部渲染实现。
4. **禁止手工计算图表 series、Y 轴、阈值线或总结表**。这些算法必须留在 MCP 工具内部。

## 图表生成规则

以下规则由 `network-ops_bandwidth_report_generate` 和底层渲染脚本保证：

- 每个线路组生成 3 张 ECharts 折线图：带宽峰值&均值、利用率、延迟。
- 带宽图 Y 轴最大值必须等于当前线路组内所有线路、所有日期的最大 `bandwidth_mbps`，不得按峰值流量动态放大。
- 带宽图每条线路有红色虚线 80% 带宽阈值 markLine。
- 利用率图第一条 series 上有 80% 阈值 markLine。
- 延迟图仅画延迟曲线，不画基线。
- 逐日明细表必须展示峰值基线和延迟基线字段。
- 报告末尾附总结汇总表（含 ✅/⚠️/🔴 评估）。
- 自包含 HTML，仅依赖 ECharts CDN。

## 参考文档

- `references/chart_spec.md` — 图表规格详细说明。
- `scripts/gen_report.py` — `network-ops` MCP 工具内部使用的 HTML 渲染脚本，不供 Agent 直接调用。
