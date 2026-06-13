---
name: network-bandwidth-reports
description: Use when 需要基于 DeerFlow 线路带宽数据生成网络日报、周报、世界杯保障带宽趋势 HTML、交互式 ECharts 报告，或需要自定义天数、自动查询最新完整数据、验证报告硬约束
---

# Network Bandwidth Reports

## Overview

本技能用于从 DeerFlow 真实带宽数据自动生成网络带宽日报、周报或自定义天数报告。核心原则：**先自动查询数据，再生成报告，最后跑 eval；不得手工编造数据或只按附件样式静态拼页面。**

## When to Use

- 用户要求生成“带宽曲线报告”“网络日报”“网络周报”“世界杯保障报告”“交互式 HTML 报告”
- 用户要求自定义天数，如最近 3 天、7 天、15 天
- 用户要求自动查询 DeerFlow 数据，而不是粘贴数据
- 用户要求同时覆盖日报和周报
- 用户要求验证、eval、验收报告是否满足硬性约束

不要用于纯文字汇报、Obsidian 工作日志日报周报、非 DeerFlow 数据源的图表报告。

## Quick Reference

| 目标 | 命令 |
| --- | --- |
| 最新完整 7 天周报 | `python3 ~/.agents/skills/network-bandwidth-reports/scripts/generate_report.py --repo /Users/matthewyin/Coding/docker/deer-flow --days 7 --mode weekly --output /tmp/network-bandwidth-weekly.html` |
| 最新完整 1 天日报 | `python3 ~/.agents/skills/network-bandwidth-reports/scripts/generate_report.py --repo /Users/matthewyin/Coding/docker/deer-flow --days 1 --mode daily --output /tmp/network-bandwidth-daily.html` |
| 指定截止日期 | `python3 ~/.agents/skills/network-bandwidth-reports/scripts/generate_report.py --repo /Users/matthewyin/Coding/docker/deer-flow --days 7 --end-date 2026-06-11 --output /tmp/report.html` |
| 跑 eval | `python3 ~/.agents/skills/network-bandwidth-reports/scripts/eval_report.py --repo /Users/matthewyin/Coding/docker/deer-flow --days 7` |

## Required Workflow

1. 明确报告类型：`daily`、`weekly` 或 `custom`。未指定时按用户天数判断：1 天为日报，7 天为周报，其他为自定义。
2. 自动查询数据：优先读取 `backend/.deer-flow/db/network_ops.db` 的 `bandwidth_lines` 表，自动找最新完整 N 天。
3. 只选目标线路：默认 13 条世界杯保障线路：`5,6,151,152,153,154,159,160,161,162,201,202,203`。需要扩展时传 `--groups-json`，不要改脚本源码。
4. 计算口径固定：
   - `max_peak = max(in_peak_mbps, out_peak_mbps)`
   - `max_avg = max(in_avg_mbps, out_avg_mbps)`
   - 峰值利用率和均值利用率都用对应值除以当日 `bandwidth_mbps`
   - 阈值统一为 80%
5. 生成单文件 HTML：CSS 和 JS 内嵌，只允许依赖 ECharts CDN。
6. 跑 eval：生成完成后必须运行 `scripts/eval_report.py`。eval 不通过时不能交付。

## Report Requirements

- 标题必须说明日报、周报或自定义天数。
- 页面必须显示数据周期、生成时间、数据源。
- 每个线路组必须包含线路信息表、带宽峰值/均值图、利用率图、延迟图、逐日明细表。
- 汇总表必须列出线路、运营商、带宽、最大峰值、最大峰值利用率、最大均值利用率、最大延迟、评估。
- 图表不得绘制 `bw_peak_baseline_mbps`、`latency_baseline_ms` 或任何基线曲线。
- 带宽图和利用率图必须有红色 80% 阈值线。
- tooltip 必须能看到日期、线路、带宽、入向/出向峰值、入向/出向均值、峰值、均值、利用率、延迟。

## Eval Gates

eval 必须检查：

- 数据周期为最新完整 N 天，或匹配指定 `--end-date`
- 目标线路数正确
- 记录数等于 `天数 × 线路数`
- 图表数等于 `分组数 × 3`
- HTML 中没有 `.png` 静态图依赖
- HTML 使用 ECharts 5.5.0
- HTML 包含 `window.resize` 图表自适应
- HTML 没有基线 series
- 带宽图和利用率图存在 80% 阈值

## Common Mistakes

| 错误 | 正确做法 |
| --- | --- |
| 直接读取附件提示词里的示例线路后手工写数据 | 从 `network_ops.db.bandwidth_lines` 自动查询 |
| 默认固定 7 天 | 接收 `--days`，自动找最新完整 N 天 |
| 把两网三中心合成一个图表导致周报图表数不稳定 | 默认按 6 个业务分组，每组 3 张图 |
| 把基线画进图表 | 基线只能在明细表展示 |
| 生成后不验证 | 必须跑 `eval_report.py` |
| 发现数据缺失后补零 | 停止交付，报告缺失日期和线路 |

## RED Baseline This Skill Prevents

无本技能时，agent 容易只按附件生成一次 7 天 HTML，并遗漏自定义天数、最新完整日期查询、日报模式、周报模式和 eval。使用本技能时，必须把这些要求收口到脚本参数和 eval gates。
