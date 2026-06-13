---
name: vpdn-segment-report
description: >
  生成 VPDN 专线分组带宽趋势 HTML 报表。用户要求对指定 VPDN 线路、重点 VPDN 线路、
  北京广州/北京成都/北京南京/北京西安/北京昆明/北京本地等 VPDN 专线生成设定日期区间报表，
  或要求“指定线路一份、其他 VPDN 专线一份”“每条线路一套图”“两份 HTML 不合并”时使用。
---

# VPDN 专线分组报表

本技能只负责固定调用 `network-ops_bandwidth_report_generate`。必须生成两份 HTML：

1. 指定 18 条线路一份 HTML。
2. 除指定 18 条线路外，其他所有 VPDN 专线一份 HTML。

两份 HTML 不能合并。每份 HTML 内部必须按带宽大小归类，相同带宽的线路放到同一组图表中。

## 固定线路清单

将以下线路作为“指定线路”：

```text
北京广州ETN2827NP
北京广州ETN2631NP
北京广州ETN2830NP
北京广州ETN2635NP
北京成都ETN2718NP
北京成都ETN2533NP
北京本地MSTPBJ1003789166
北京本地45700045
北京南京ETN2419NP
北京南京ETN2420NP
北京南京ETN2586NP
北京南京ETN2585NP
北京西安ETN6019NPH
北京西安ETN2397NP
北京昆明ETN2267NP
北京昆明ETN2182NP
北京昆明ETN2266NP
北京昆明ETN2183NP
```

## 工作流程

### 第 1 步：确定日期区间

- 用户指定 `start_date` / `end_date` 时，按用户日期执行。
- 用户只给天数时，传 `days`。
- 用户未给日期时，默认最近 7 天。

### 第 2 步：生成指定线路报表

只调用一次：

```text
network-ops_bandwidth_report_generate(
  days=<天数>,
  start_date=<开始日期 YYYY-MM-DD，可空>,
  end_date=<结束日期 YYYY-MM-DD，可空>,
  long_distance_no="<固定线路清单，使用空格连接>",
  line_scope="all",
  group_by="bandwidth",
  threshold_pcts="35,40",
  report_type="周报",
  output_filename="VPDN指定线路带宽周报.html",
  include_html=false
)
```

要求：

- 只生成一个 HTML。
- 相同带宽的线路放到同一组图表中。
- 每套图包含峰值、峰值利用率、延迟图表。
- 带宽图和利用率图必须按 35% 与 40% 画两条阈值线。
- HTML 中展示长途线路编号字段，不展示“线路”字段。
- 逐日明细表必须转置：日期作为字段名，线路指标作为记录名。

### 第 3 步：生成其他 VPDN 专线报表

只调用一次：

```text
network-ops_bandwidth_report_generate(
  days=<天数>,
  start_date=<开始日期 YYYY-MM-DD，可空>,
  end_date=<结束日期 YYYY-MM-DD，可空>,
  line_group="VPDN终端专线",
  exclude_long_distance_no="<固定线路清单，使用空格连接>",
  line_scope="all",
  group_by="bandwidth",
  threshold_pcts="35,40",
  report_type="周报",
  output_filename="VPDN其他专线带宽周报.html",
  include_html=false
)
```

要求：

- 只生成一个 HTML。
- 排除固定线路清单中的 18 条线路。
- 相同带宽的线路放到同一组图表中。
- 每套图包含峰值、峰值利用率、延迟图表。
- 带宽图和利用率图必须按 35% 与 40% 画两条阈值线。
- HTML 中展示长途线路编号字段，不展示“线路”字段。
- 逐日明细表必须转置：日期作为字段名，线路指标作为记录名。

### 第 4 步：呈现文件

两个工具调用都返回 `ok: true` 后，合并两个结果的 `present_filepaths`，调用一次 `present_files` 呈现两份 HTML。

如果其中任一工具返回 `ok: false`，直接反馈错误原因，不要自行写脚本、不要改写 HTML、不要调用 `write_file`。

## 禁止事项

1. 禁止按单条线路循环调用工具。指定线路报表必须一次调用生成一个 HTML。
2. 禁止把两类报表合并到同一个 HTML。
3. 禁止调用 `network-ops_bandwidth_records_query` 后自行整理数据。
4. 禁止新写 Python/HTML 脚本。
5. 禁止使用 `write_file` 写入 HTML 全文。
6. 禁止使用 `group_by="line"` 生成本技能报表；必须使用 `group_by="bandwidth"`。
