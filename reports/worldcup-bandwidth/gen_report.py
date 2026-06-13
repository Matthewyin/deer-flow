#!/usr/bin/env python3
import datetime as dt
import html
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "backend/.deer-flow/db/network_ops.db"
OUTPUT_PATH = Path(__file__).resolve().with_name("interactive.html")

START_DATE = "2026-06-05"
END_DATE = "2026-06-11"

TARGET_GROUPS = [
    {"name": "混合云TLS售票-腾讯公有云", "line_nos": [151, 152]},
    {"name": "混合云TLS售票-阿里公有云", "line_nos": [153, 154]},
    {"name": "北京单场售票", "line_nos": [5, 6]},
    {"name": "两网三中心-腾讯云（非受控）", "line_nos": [161, 162]},
    {"name": "两网三中心-阿里云（非受控）", "line_nos": [159, 160]},
    {"name": "西五环互联网B区", "line_nos": [201, 202, 203]},
]

CARRIER_COLORS = {
    "电信": "#5470C6",
    "联通": "#EE6666",
    "移动": "#91CC75",
}


def date_range(start: str, end: str) -> list[str]:
    current = dt.date.fromisoformat(start)
    last = dt.date.fromisoformat(end)
    days = []
    while current <= last:
        days.append(current.isoformat())
        current += dt.timedelta(days=1)
    return days


def esc(value) -> str:
    return html.escape("" if value is None else str(value))


def fmt(value, digits: int = 2) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return str(value)


def pct(value) -> str:
    return "-" if value is None else f"{value:.2f}%"


def bandwidth_text(records: list[dict]) -> str:
    values = []
    for record in records:
        value = record.get("bandwidth_mbps")
        if value is not None and value not in values:
            values.append(value)
    return " → ".join(f"{fmt(value, 0)}M" for value in values)


def with_metrics(row: dict) -> dict:
    bandwidth = row.get("bandwidth_mbps") or 0
    in_peak = row.get("in_peak_mbps") or 0
    out_peak = row.get("out_peak_mbps") or 0
    in_avg = row.get("in_avg_mbps") or 0
    out_avg = row.get("out_avg_mbps") or 0
    max_peak = max(in_peak, out_peak)
    max_avg = max(in_avg, out_avg)
    row["max_peak"] = round(max_peak, 4)
    row["max_avg"] = round(max_avg, 4)
    row["peak_util_pct"] = round(max_peak / bandwidth * 100, 4) if bandwidth else None
    row["avg_util_pct"] = round(max_avg / bandwidth * 100, 4) if bandwidth else None
    row["threshold_mbps"] = round(bandwidth * 0.8, 4) if bandwidth else None
    row["line_label"] = f"#{row['line_no']} {row.get('carrier') or ''}".strip()
    return row


def load_records() -> list[dict]:
    target_line_nos = [line_no for group in TARGET_GROUPS for line_no in group["line_nos"]]
    placeholders = ",".join("?" for _ in target_line_nos)
    sql = (
        "SELECT id, report_date, line_group, line_no, province, carrier, usage, "
        "bandwidth_mbps, long_distance_no, in_peak_mbps, in_avg_mbps, in_peak_util_pct, "
        "in_peak_time, out_peak_mbps, out_avg_mbps, out_peak_util_pct, out_peak_time, "
        "latency_avg_ms, bw_peak_baseline_mbps, bw_util_threshold_pct, "
        "latency_baseline_ms, latency_threshold_ms, created_at "
        "FROM bandwidth_lines "
        "WHERE report_date BETWEEN ? AND ? "
        f"AND line_no IN ({placeholders}) "
        "ORDER BY report_date, line_no"
    )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, [START_DATE, END_DATE, *target_line_nos]).fetchall()
    finally:
        conn.close()
    return [with_metrics(dict(row)) for row in rows]


def build_groups(records: list[dict]) -> list[dict]:
    expected_dates = date_range(START_DATE, END_DATE)
    by_line_date = {(row["line_no"], row["report_date"]): row for row in records}
    groups = []
    for group_index, group_def in enumerate(TARGET_GROUPS):
        lines = []
        for line_no in group_def["line_nos"]:
            line_records = [by_line_date.get((line_no, day)) for day in expected_dates]
            if any(record is None for record in line_records):
                missing = [day for day, record in zip(expected_dates, line_records) if record is None]
                raise RuntimeError(f"线路 {line_no} 缺少数据：{', '.join(missing)}")
            first = line_records[0]
            lines.append(
                {
                    "line_no": line_no,
                    "line_label": first["line_label"],
                    "carrier": first.get("carrier") or "",
                    "usage": first.get("usage") or "",
                    "line_group": first.get("line_group") or "",
                    "bandwidth_text": bandwidth_text(line_records),
                    "color": CARRIER_COLORS.get(first.get("carrier"), "#3A506B"),
                    "records": line_records,
                }
            )
        values = [record["max_peak"] for line in lines for record in line["records"]]
        thresholds = [
            record["threshold_mbps"]
            for line in lines
            for record in line["records"]
            if record["threshold_mbps"] is not None
        ]
        latencies = [
            record["latency_avg_ms"]
            for line in lines
            for record in line["records"]
            if record["latency_avg_ms"] is not None
        ]
        y_bandwidth = max(values + thresholds) * 1.2 if values or thresholds else 1
        y_latency = max(max(latencies) * 1.3, 1) if latencies else 1
        groups.append(
            {
                "index": group_index,
                "name": group_def["name"],
                "dates": expected_dates,
                "date_labels": [day[5:] for day in expected_dates],
                "lines": lines,
                "y_bandwidth": round(y_bandwidth, 2),
                "y_latency": round(y_latency, 2),
            }
        )
    return groups


def validate(records: list[dict]) -> None:
    expected_dates = date_range(START_DATE, END_DATE)
    dates = sorted({row["report_date"] for row in records})
    line_nos = sorted({row["line_no"] for row in records})
    expected_line_nos = sorted(line_no for group in TARGET_GROUPS for line_no in group["line_nos"])
    if dates != expected_dates:
        raise RuntimeError(f"数据周期不完整：{dates}")
    if line_nos != expected_line_nos:
        raise RuntimeError(f"目标线路不完整：{line_nos}")


def line_info_table(group: dict) -> str:
    rows = []
    for line in group["lines"]:
        rows.append(
            "<tr>"
            f"<td>{esc(line['line_label'])}</td>"
            f"<td>{esc(line['carrier'])}</td>"
            f"<td>{esc(line['bandwidth_text'])}</td>"
            f"<td>{esc(line['usage'])}</td>"
            "</tr>"
        )
    return (
        '<div class="table-wrap small">'
        "<table>"
        "<thead><tr><th>线路</th><th>运营商</th><th>带宽</th><th>用途</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
        "</div>"
    )


def detail_table(group: dict) -> str:
    first_header = ["<th rowspan=\"2\">日期</th>"]
    second_header = []
    fields = [
        "in_peak",
        "out_peak",
        "max_peak",
        "in_avg",
        "out_avg",
        "max_avg",
        "峰值利用率",
        "均值利用率",
        "延迟ms",
        "带宽",
        "峰值基线",
        "延迟基线",
    ]
    for line in group["lines"]:
        first_header.append(f"<th colspan=\"{len(fields)}\">{esc(line['line_label'])}</th>")
        second_header.extend(f"<th>{esc(field)}</th>" for field in fields)

    body_rows = []
    for row_index, day in enumerate(group["dates"]):
        cells = [f"<td>{esc(day)}</td>"]
        for line in group["lines"]:
            record = line["records"][row_index]
            cells.extend(
                [
                    f"<td>{fmt(record.get('in_peak_mbps'))}</td>",
                    f"<td>{fmt(record.get('out_peak_mbps'))}</td>",
                    f"<td>{fmt(record.get('max_peak'))}</td>",
                    f"<td>{fmt(record.get('in_avg_mbps'))}</td>",
                    f"<td>{fmt(record.get('out_avg_mbps'))}</td>",
                    f"<td>{fmt(record.get('max_avg'))}</td>",
                    f"<td>{pct(record.get('peak_util_pct'))}</td>",
                    f"<td>{pct(record.get('avg_util_pct'))}</td>",
                    f"<td>{fmt(record.get('latency_avg_ms'))}</td>",
                    f"<td>{fmt(record.get('bandwidth_mbps'), 0)}M</td>",
                    f"<td>{fmt(record.get('bw_peak_baseline_mbps'))}</td>",
                    f"<td>{fmt(record.get('latency_baseline_ms'))}</td>",
                ]
            )
        body_rows.append(f"<tr>{''.join(cells)}</tr>")

    return (
        '<div class="table-wrap detail">'
        "<table>"
        f"<thead><tr>{''.join(first_header)}</tr><tr>{''.join(second_header)}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
        "</div>"
    )


def summary_rows(groups: list[dict]) -> tuple[str, list[dict]]:
    rows = []
    summary = []
    for group in groups:
        for line in group["lines"]:
            records = line["records"]
            max_peak = max(record["max_peak"] for record in records)
            max_peak_util = max(record["peak_util_pct"] or 0 for record in records)
            max_avg_util = max(record["avg_util_pct"] or 0 for record in records)
            max_latency = max(record.get("latency_avg_ms") or 0 for record in records)
            if max_peak_util >= 80:
                level = "danger"
                assessment = "🔴 超80%阈值"
            elif max_peak_util >= 60:
                level = "warning"
                assessment = "⚠️ 较高"
            else:
                level = "normal"
                assessment = "✅ 正常"
            item = {
                "group": group["name"],
                "line": line["line_label"],
                "carrier": line["carrier"],
                "bandwidth": line["bandwidth_text"],
                "max_peak": round(max_peak, 2),
                "max_peak_util": round(max_peak_util, 2),
                "max_avg_util": round(max_avg_util, 2),
                "max_latency": round(max_latency, 2),
                "assessment": assessment,
                "level": level,
            }
            summary.append(item)
            rows.append(
                f"<tr class=\"{level}\">"
                f"<td>{esc(group['name'])}</td>"
                f"<td>{esc(line['line_label'])}</td>"
                f"<td>{esc(line['carrier'])}</td>"
                f"<td>{esc(line['bandwidth_text'])}</td>"
                f"<td>{fmt(max_peak)}</td>"
                f"<td>{pct(max_peak_util)}</td>"
                f"<td>{pct(max_avg_util)}</td>"
                f"<td>{fmt(max_latency)}</td>"
                f"<td>{esc(assessment)}</td>"
                "</tr>"
            )
    return "".join(rows), summary


def render_html(groups: list[dict], records: list[dict]) -> str:
    generated_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary_html, summary = summary_rows(groups)
    sections = []
    cn_numbers = ["一", "二", "三", "四", "五", "六"]
    for group in groups:
        idx = group["index"]
        sections.append(
            f"<section class=\"group-section\">"
            f"<h2>{cn_numbers[idx]}、{esc(group['name'])}</h2>"
            "<h3>线路信息</h3>"
            f"{line_info_table(group)}"
            "<h3>带宽峰值 & 均值趋势</h3>"
            f"<div class=\"chart\" id=\"chart_bw_{idx}\"></div>"
            "<h3>峰值利用率 & 均值利用率趋势</h3>"
            f"<div class=\"chart\" id=\"chart_util_{idx}\"></div>"
            "<h3>延迟趋势</h3>"
            f"<div class=\"chart\" id=\"chart_latency_{idx}\"></div>"
            "<h3>逐日明细</h3>"
            f"{detail_table(group)}"
            "</section>"
        )

    report_payload = {
        "period": {"start": START_DATE, "end": END_DATE},
        "generated_at": generated_at,
        "groups": groups,
        "summary": summary,
        "record_count": len(records),
        "line_count": len({row["line_no"] for row in records}),
    }
    data_json = json.dumps(report_payload, ensure_ascii=False)

    html_text = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>各线路组 7天 带宽峰值/均值 & 利用率 & 延迟 趋势报告</title>
  <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: #f5f7fa;
      color: #1f2933;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
      font-size: 14px;
      line-height: 1.6;
    }
    .page {
      max-width: 1400px;
      margin: 28px auto;
      padding: 30px 40px;
      background: #fff;
      border-radius: 8px;
      box-shadow: 0 2px 12px rgba(0,0,0,0.08);
    }
    h1 {
      margin: 0 0 12px;
      padding-bottom: 14px;
      border-bottom: 3px solid #5470C6;
      text-align: center;
      font-size: 22px;
      font-weight: 700;
    }
    .subtitle {
      margin: 0 0 20px;
      text-align: center;
      color: #5b6472;
      font-size: 13px;
    }
    .legend-note {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin: 18px 0 8px;
      padding: 14px 16px;
      border: 1px solid #e8e8e8;
      background: #fafbfc;
      border-radius: 8px;
    }
    .legend-note div { color: #344054; }
    .swatch {
      display: inline-block;
      width: 28px;
      height: 3px;
      margin: 0 6px;
      vertical-align: middle;
      border-radius: 2px;
    }
    .blue { background: #5470C6; }
    .red { background: #EE6666; }
    .green { background: #91CC75; }
    .threshold { background: #FF4444; border-top: 2px dashed #FF4444; height: 0; }
    h2 {
      margin: 35px 0 14px;
      padding-left: 12px;
      border-left: 4px solid #5470C6;
      color: #172033;
      font-size: 18px;
    }
    h3 {
      margin: 20px 0 10px;
      color: #444;
      font-size: 15px;
    }
    .chart {
      width: 100%;
      height: 420px;
      margin: 8px 0 18px;
      border: 1px solid #e8e8e8;
      background: #fafbfc;
    }
    .table-wrap {
      width: 100%;
      overflow: auto;
      border: 1px solid #e2e6ee;
      border-radius: 6px;
    }
    .table-wrap.detail { max-height: 450px; }
    table {
      width: 100%;
      min-width: 880px;
      border-collapse: collapse;
      font-size: 12px;
    }
    th, td {
      padding: 7px 8px;
      border: 1px solid #e3e7ef;
      text-align: center;
      white-space: nowrap;
    }
    th {
      position: sticky;
      top: 0;
      z-index: 1;
      background: #f0f3f8;
      font-weight: 700;
    }
    .detail thead tr:nth-child(2) th { top: 33px; }
    tbody tr:hover { background: #f5f8ff; }
    tr.warning { background: #fff3e0; }
    tr.danger { background: #ffebee; }
    .summary-table { margin-bottom: 10px; }
    .tooltip-title {
      margin-bottom: 6px;
      font-weight: 700;
      color: #111827;
    }
    .tooltip-block {
      margin: 6px 0;
      padding-bottom: 6px;
      border-bottom: 1px solid #eee;
    }
    @media (max-width: 900px) {
      .page { margin: 0; padding: 20px 14px; border-radius: 0; }
      .legend-note { grid-template-columns: 1fr; }
      h1 { font-size: 19px; }
    }
  </style>
</head>
<body>
  <main class="page">
    <h1>各线路组 7天 带宽峰值/均值 & 利用率 & 延迟 趋势报告</h1>
    <p class="subtitle">数据周期：__START_DATE__ 至 __END_DATE__ ｜ 报告生成时间：__GENERATED_AT__ ｜ 数据源：backend/.deer-flow/db/network_ops.db / bandwidth_lines</p>
    <div class="legend-note">
      <div>线型：实线 = 峰值，虚线 = 均值</div>
      <div>颜色：<span class="swatch blue"></span>电信 <span class="swatch red"></span>联通 <span class="swatch green"></span>移动</div>
      <div>阈值线：<span class="swatch threshold"></span>红色虚线 80% 阈值</div>
    </div>
    __SECTIONS__
    <section class="group-section">
      <h2>总结汇总表</h2>
      <div class="table-wrap summary-table">
        <table>
          <thead>
            <tr><th>分组</th><th>线路</th><th>运营商</th><th>带宽</th><th>最大峰值</th><th>最大峰值利用率</th><th>最大均值利用率</th><th>最大延迟</th><th>评估</th></tr>
          </thead>
          <tbody>__SUMMARY_ROWS__</tbody>
        </table>
      </div>
    </section>
  </main>
  <script>
    const reportData = __REPORT_DATA__;
    const chartInstances = [];

    function formatValue(value, suffix) {
      if (value === null || value === undefined || Number.isNaN(value)) return "-";
      return Number(value).toFixed(2).replace(/\\.00$/, "") + suffix;
    }

    function tooltipFormatter(params) {
      const rows = [`<div class="tooltip-title">${params[0].axisValue}</div>`];
      params.forEach((param) => {
        const meta = param.data && param.data.meta;
        if (!meta) return;
        rows.push(
          `<div class="tooltip-block">${param.marker}<b>${param.seriesName}</b><br>` +
          `线路：${meta.line_label}<br>` +
          `带宽字段：${formatValue(meta.bandwidth_mbps, "M")}<br>` +
          `入向峰值 / 出向峰值：${formatValue(meta.in_peak_mbps, " Mbps")} / ${formatValue(meta.out_peak_mbps, " Mbps")}<br>` +
          `入向均值 / 出向均值：${formatValue(meta.in_avg_mbps, " Mbps")} / ${formatValue(meta.out_avg_mbps, " Mbps")}<br>` +
          `峰值带宽：${formatValue(meta.max_peak, " Mbps")}<br>` +
          `均值带宽：${formatValue(meta.max_avg, " Mbps")}<br>` +
          `峰值利用率：${formatValue(meta.peak_util_pct, "%")}<br>` +
          `均值利用率：${formatValue(meta.avg_util_pct, "%")}<br>` +
          `平均延迟：${formatValue(meta.latency_avg_ms, " ms")}</div>`
        );
      });
      return rows.join("");
    }

    function commonOption(title, yName, yMax, series) {
      return {
        title: { text: title, left: "center", top: 0, textStyle: { fontSize: 14, color: "#333" } },
        tooltip: {
          trigger: "axis",
          backgroundColor: "rgba(255,255,255,0.95)",
          borderColor: "#ddd",
          textStyle: { color: "#333" },
          formatter: tooltipFormatter
        },
        legend: { top: 25, type: "scroll" },
        grid: { left: "8%", right: "5%", bottom: "12%", top: "18%", containLabel: true },
        xAxis: { type: "category", boundaryGap: false, data: [] },
        yAxis: { type: "value", name: yName, min: 0, max: yMax },
        series
      };
    }

    function dataPoint(record, field) {
      return { value: record[field], meta: record };
    }

    function renderBandwidthChart(group) {
      const series = [];
      group.lines.forEach((line) => {
        series.push({
          name: `${line.line_label} 峰值`,
          type: "line",
          smooth: true,
          symbol: "circle",
          symbolSize: 5,
          lineStyle: { width: 2, type: "solid", color: line.color },
          itemStyle: { color: line.color },
          data: line.records.map((record) => dataPoint(record, "max_peak"))
        });
        series.push({
          name: `${line.line_label} 均值`,
          type: "line",
          smooth: true,
          symbol: "circle",
          symbolSize: 4,
          lineStyle: { width: 1.5, type: "dashed", color: line.color },
          itemStyle: { color: line.color },
          data: line.records.map((record) => dataPoint(record, "max_avg"))
        });
        series.push({
          name: `${line.line_label} 80%(${line.bandwidth_text}×80%)`,
          type: "line",
          smooth: false,
          step: "end",
          symbol: "none",
          silent: true,
          lineStyle: { width: 2, type: "dashed", color: "#FF4444" },
          itemStyle: { color: "#FF4444" },
          endLabel: { show: true, formatter: `${line.line_label} 80%`, color: "#FF4444" },
          data: line.records.map((record) => ({ value: record.threshold_mbps }))
        });
      });
      const option = commonOption(`${group.name}：带宽峰值 & 均值`, "Mbps", group.y_bandwidth, series);
      option.xAxis.data = group.date_labels;
      return option;
    }

    function renderUtilChart(group) {
      const series = [];
      group.lines.forEach((line) => {
        series.push({
          name: `${line.line_label} 峰值利用率`,
          type: "line",
          smooth: true,
          symbol: "circle",
          symbolSize: 5,
          lineStyle: { width: 2, type: "solid", color: line.color },
          itemStyle: { color: line.color },
          data: line.records.map((record) => dataPoint(record, "peak_util_pct"))
        });
        series.push({
          name: `${line.line_label} 均值利用率`,
          type: "line",
          smooth: true,
          symbol: "circle",
          symbolSize: 4,
          lineStyle: { width: 1.5, type: "dashed", color: line.color },
          itemStyle: { color: line.color },
          data: line.records.map((record) => dataPoint(record, "avg_util_pct"))
        });
      });
      if (series.length > 0) {
        series[0].markLine = {
          silent: true,
          symbol: "none",
          lineStyle: { width: 2, type: "dashed", color: "#FF4444" },
          label: { formatter: "80% 阈值", color: "#FF4444" },
          data: [{ yAxis: 80, name: "80% 阈值" }]
        };
      }
      const option = commonOption(`${group.name}：峰值利用率 & 均值利用率`, "%", 100, series);
      option.xAxis.data = group.date_labels;
      return option;
    }

    function renderLatencyChart(group) {
      const series = [];
      group.lines.forEach((line) => {
        series.push({
          name: `${line.line_label} 延迟`,
          type: "line",
          smooth: true,
          symbol: "circle",
          symbolSize: 5,
          lineStyle: { width: 2, type: "solid", color: line.color },
          itemStyle: { color: line.color },
          data: line.records.map((record) => dataPoint(record, "latency_avg_ms"))
        });
      });
      const option = commonOption(`${group.name}：延迟趋势`, "ms", group.y_latency, series);
      option.xAxis.data = group.date_labels;
      return option;
    }

    reportData.groups.forEach((group) => {
      [
        [`chart_bw_${group.index}`, renderBandwidthChart(group)],
        [`chart_util_${group.index}`, renderUtilChart(group)],
        [`chart_latency_${group.index}`, renderLatencyChart(group)]
      ].forEach(([id, option]) => {
        const chart = echarts.init(document.getElementById(id));
        chart.setOption(option);
        chartInstances.push(chart);
      });
    });

    window.addEventListener("resize", () => {
      chartInstances.forEach((chart) => chart.resize());
    });
  </script>
</body>
</html>
"""
    return (
        html_text.replace("__START_DATE__", START_DATE)
        .replace("__END_DATE__", END_DATE)
        .replace("__GENERATED_AT__", generated_at)
        .replace("__SECTIONS__", "".join(sections))
        .replace("__SUMMARY_ROWS__", summary_html)
        .replace("__REPORT_DATA__", data_json)
    )


def main() -> None:
    records = load_records()
    validate(records)
    groups = build_groups(records)
    OUTPUT_PATH.write_text(render_html(groups, records), encoding="utf-8")
    print(f"已生成：{OUTPUT_PATH}")
    print(f"数据周期：{START_DATE} 至 {END_DATE}")
    print(f"目标线路数：{len({row['line_no'] for row in records})}")
    print(f"图表数：{len(groups) * 3}")
    print(f"记录数：{len(records)}")


if __name__ == "__main__":
    main()
