---
name: bandwidth-excel-report
description: >
  生成 TLS终端专线、北单售票专线、体彩APP专线、西五环互联网B区线路近 N 天带宽峰值、
  峰值利用率、均值、均值利用率 Excel 表时触发。适用于“生成带宽 Excel”“导出近7天
  每日 sheet”“带宽峰值均值表”等请求。
---

# 带宽峰值均值 Excel 报表

本技能只负责把用户意图转成 `network-ops_bandwidth_excel_report_generate` 工具调用。查询、筛选、计算、Excel 工作簿生成都必须由 `network-ops` MCP 工具完成。

## 默认范围

未特别说明时，使用以下默认值：

- **时间范围**：最近 7 天。
- **线路范围**：固定 13 条线路：
  - TLS终端专线（4条）：151、152、153、154
  - 北单售票专线（2条）：5、6
  - 体彩APP专线（4条）：159、160、161、162
  - 西五环互联网B区线路（3条）：201、202、203
- **输出格式**：一个 `.xlsx` 文件，每天一个 sheet 页。

## 必须调用的工具

```text
network-ops_bandwidth_excel_report_generate(
  days=<天数，默认7>,
  start_date=<开始日期 YYYY-MM-DD，可空>,
  end_date=<结束日期 YYYY-MM-DD，可空>,
  output_filename=<xlsx 文件名，可空>
)
```

工具会在内部完成：

- 查询 `network_ops.db.bandwidth_lines`
- 自动取数据库最新可用日期作为结束日期
- 筛选固定 13 条线路
- 校验 `日期数 × 13` 条记录完整性
- 生成一个 Excel 工作簿
- 每天一个 sheet 页
- 每个 sheet 包含：
  - 线路类型
  - 线路
  - 线路编号
  - 运营商
  - 带宽
  - 阈值（带宽 × 80%）
  - 入向峰值、入向峰值利用率、入向峰值时间点
  - 出向峰值、出向峰值利用率、出向峰值时间点
  - 入向均值、入向均值利用率
  - 出向均值、出向均值利用率

## 结果呈现

工具返回 `ok: true` 时：

1. 不要调用 `write_file`。
2. 不要手工创建 xlsx。
3. 直接使用工具返回的 `present_filepaths` 呈现文件。
4. 如果工具返回 `notes`，简要告知用户。

工具返回 `ok: false` 时，直接反馈 `error`、`period`、`expected_records`、`actual_records`，不要补零或自行拼表。

## 禁止事项

1. 禁止先调用 `network-ops_bandwidth_records_query` 再自行整理 Excel。
2. 禁止在 Agent 侧写 Python、JavaScript 或 shell 脚本生成 Excel。
3. 禁止按线路逐条查询或逐条生成文件。
4. 禁止把每日 sheet 拆成多个 Excel 文件。
5. 禁止伪造源数据没有的均值时间点；工具会以 `-` 展示。
