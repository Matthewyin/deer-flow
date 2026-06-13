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
  - 用户未指定时，使用 `line_scope="default"`，默认筛选：混合云TLS售票（4条）、西五环互联网B区（3条）、北京单场售票（2条）、两网三中心到数据中心线路（4条），共 13 条线路。
  - 默认周报必须只调用一次 `network-ops_bandwidth_report_generate`，并且必须只生成一个 HTML 文件。禁止按线路逐条调用、逐条生成文件。
  - 用户指定所有线路时，传 `line_scope="all"`，生成所有匹配线路的报告。
  - 用户指定线路组时，传 `line_group`，如 `TLS终端专线`、`西五环互联网B区线路`。
  - 用户指定业务用途时，传 `usage_keyword`，如 `混合云TLS`、`北京单场`、`本地互联`。
  - 用户指定线路编号时，传 `long_distance_no`，多个编号可用空格、逗号或分号分隔。
  - 用户指定行号时，传 `line_no`，多个编号可用空格、逗号或分号分隔。

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
  line_no=<行号，可空>,
  line_scope=<default/all>,
  group_by="line_group",
  report_type=<周报/日报，可空>,
  output_filename=<HTML文件名>,
  include_html=false
)
```

工具会在内部完成：

- 查询 `network_ops.db.bandwidth_lines`
- 按 `line_scope` 筛选默认周报线路或所有线路
- 按日期和线路补齐数据
- 按 `line_group` 生成图表分组，相同线路组的线路放到同一个图表组中
- 计算 `max_peak = max(in_peak_mbps, out_peak_mbps)`
- 计算 `max_avg = max(in_avg_mbps, out_avg_mbps)`
- 计算峰值利用率和均值利用率
- 调用标准 HTML 渲染脚本生成报告

### 第 3 步：保存并呈现报告

工具返回 `ok: true` 时：

1. 不要调用 `write_file`。
2. 直接调用 `present_files`，参数使用工具返回的 `present_filepaths`。
3. 正常情况下工具不会返回 `html` 全文，避免 HTML 内容进入上下文窗口。

工具返回 `ok: false` 时，直接把错误原因反馈给用户。不要自行改写算法或临时写脚本绕过。

## 禁止事项

1. **禁止先调用 `network-ops_bandwidth_records_query` 再自行整理 `report_config`**。该工具只用于用户明确要求查看原始记录或核查字段，不用于报表生成。
2. **禁止新写 `gen_weekly.py`、Python 生成器或 HTML 拼接脚本**。
3. **禁止复制、读取、改写或直接执行 `scripts/gen_report.py`**。该脚本只作为 `network-ops_bandwidth_report_generate` 的内部渲染实现。
4. **禁止手工计算图表 series、Y 轴、阈值线或总结表**。这些算法必须留在 MCP 工具内部。
5. **禁止为了保存报告而调用 `write_file` 写入 HTML 全文**。报告文件由 MCP 工具生成，Agent 只调用 `present_files` 呈现。
6. **禁止为默认周报按单条线路循环调用报表工具**。默认 13 条线路必须一次调用、一个 HTML 文件。

## 图表生成规则

以下规则由 `network-ops_bandwidth_report_generate` 和底层渲染脚本保证：

- 每个线路组生成 3 张 ECharts 折线图：带宽峰值&均值、利用率、延迟。
- 默认按组名分组，组标题应为 `TLS终端专线`、`北单售票专线` 这类形式，不应按 `usage` 生成 `数据端` 这类分组。
- 带宽图 Y 轴最大值必须等于当前线路组内所有线路、所有日期的最大 `bandwidth_mbps`，不得按峰值流量动态放大。
- 普通周报默认画 80% 阈值线，保留均值和延迟。
- VPDN 专线报表不要使用本技能，应使用 `vpdn_line_report`。
- 延迟图仅画延迟曲线，不画基线。
- 逐日明细表必须展示峰值基线和延迟基线字段。
- 报告末尾附总结汇总表（含 ✅/⚠️/🔴 评估）。
- 自包含 HTML，仅依赖 ECharts CDN。

## 参考文档

- `references/chart_spec.md` — 图表规格详细说明。
- `scripts/gen_report.py` — `network-ops` MCP 工具内部使用的 HTML 渲染脚本，不供 Agent 直接调用。
