#!/usr/bin/env python3
"""生成纯 JS/SVG 交互式线路曲线报告。"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "docker/volumes/deer-flow-data/bandwidth-lines"
OUTPUT_DIR = ROOT / "reports/bandwidth_curve_report_2026-06-12"
OUTPUT_FILE = OUTPUT_DIR / "interactive.html"

GROUPS = [
    ("tls_tencent", "混合云TLS售票-腾讯公有云", [151, 152]),
    ("tls_aliyun", "混合云TLS售票-阿里公有云", [153, 154]),
    ("beijing_single", "北京单场售票", [5, 6]),
    ("three_centers", "两网三中心", [159, 160, 161, 162]),
    ("w5h_b", "西五环互联网B区", [201, 202, 203]),
]

COLORS = ["#1F4E79", "#2F6B3F", "#4B3F72", "#005F73", "#3A506B"]


def safe_float(value) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def capacity_from_peak(row: dict, direction: str) -> float | None:
    peak = safe_float(row.get(f"{direction}_peak_mbps"))
    util = safe_float(row.get(f"{direction}_peak_util_pct"))
    if peak is None or util is None or util <= 0:
        return safe_float(row.get("bandwidth_mbps"))
    return peak / (util / 100)


def latest_seven_dates() -> list[str]:
    return sorted(path.stem for path in DATA_DIR.glob("*.json"))[-7:]


def line_label(row: dict) -> str:
    usage = row.get("usage") or ""
    suffix = ""
    if "阿里云" in usage:
        suffix = " 阿里"
    elif "腾讯云" in usage:
        suffix = " 腾讯"
    return f"#{row['line_no']} {row.get('carrier', '')}{suffix}"


def load_rows(dates: list[str]) -> list[dict]:
    wanted = {line_no for _, _, line_nos in GROUPS for line_no in line_nos}
    rows: list[dict] = []
    for day in dates:
        payload = json.loads((DATA_DIR / f"{day}.json").read_text(encoding="utf-8"))
        for row in payload["lines"]:
            if row.get("line_no") not in wanted:
                continue
            in_peak = safe_float(row.get("in_peak_mbps")) or 0
            out_peak = safe_float(row.get("out_peak_mbps")) or 0
            in_avg = safe_float(row.get("in_avg_mbps")) or 0
            out_avg = safe_float(row.get("out_avg_mbps")) or 0
            in_peak_util = safe_float(row.get("in_peak_util_pct")) or 0
            out_peak_util = safe_float(row.get("out_peak_util_pct")) or 0
            in_capacity = capacity_from_peak(row, "in")
            out_capacity = capacity_from_peak(row, "out")
            in_avg_util = in_avg / in_capacity * 100 if in_capacity else 0
            out_avg_util = out_avg / out_capacity * 100 if out_capacity else 0
            enriched = dict(row)
            enriched["date"] = day
            enriched["short_date"] = date.fromisoformat(day).strftime("%m-%d")
            enriched["label"] = line_label(row)
            enriched["peak_bw_mbps"] = max(in_peak, out_peak)
            enriched["avg_bw_mbps"] = max(in_avg, out_avg)
            enriched["peak_util_pct"] = max(in_peak_util, out_peak_util)
            enriched["avg_util_pct"] = max(in_avg_util, out_avg_util)
            enriched["threshold_bw_mbps"] = (safe_float(row.get("bandwidth_mbps")) or 0) * 0.8
            rows.append(enriched)
    return rows


def make_point(row: dict, value_key: str) -> dict:
    return {
        "date": row["short_date"],
        "fullDate": row["date"],
        "line": row["label"],
        "value": round(float(row[value_key]), 4),
        "bandwidth": row.get("bandwidth_mbps"),
        "inPeak": row.get("in_peak_mbps"),
        "outPeak": row.get("out_peak_mbps"),
        "inAvg": row.get("in_avg_mbps"),
        "outAvg": row.get("out_avg_mbps"),
        "peakBw": round(float(row["peak_bw_mbps"]), 4),
        "avgBw": round(float(row["avg_bw_mbps"]), 4),
        "peakUtil": round(float(row["peak_util_pct"]), 4),
        "avgUtil": round(float(row["avg_util_pct"]), 4),
        "latency": row.get("latency_avg_ms"),
    }


def build_series(group_rows: list[dict], metric: str) -> list[dict]:
    by_line: dict[int, list[dict]] = {}
    for row in group_rows:
        by_line.setdefault(row["line_no"], []).append(row)

    series: list[dict] = []
    for idx, line_no in enumerate(sorted(by_line)):
        items = sorted(by_line[line_no], key=lambda item: item["date"])
        color = COLORS[idx % len(COLORS)]
        label = items[-1]["label"]
        if metric == "bandwidth":
            series.append({"name": f"{label} 峰值", "color": color, "dash": False, "points": [make_point(row, "peak_bw_mbps") for row in items]})
            series.append({"name": f"{label} 均值", "color": color, "dash": True, "points": [make_point(row, "avg_bw_mbps") for row in items]})
        elif metric == "util":
            series.append({"name": f"{label} 峰值利用率", "color": color, "dash": False, "points": [make_point(row, "peak_util_pct") for row in items]})
            series.append({"name": f"{label} 均值利用率", "color": color, "dash": True, "points": [make_point(row, "avg_util_pct") for row in items]})
        elif metric == "latency":
            series.append({"name": f"{label} 延迟", "color": color, "dash": False, "points": [make_point(row, "latency_avg_ms") for row in items]})
    return series


def chart_config(group_key: str, title: str, group_rows: list[dict]) -> list[dict]:
    max_bw = max(float(row["bandwidth_mbps"]) for row in group_rows)
    bw_thresholds = sorted({round(float(row["threshold_bw_mbps"]), 4) for row in group_rows if row["threshold_bw_mbps"]})
    max_latency = max(float(row.get("latency_avg_ms") or 0) for row in group_rows)
    return [
        {
            "id": f"{group_key}_bandwidth",
            "title": f"{title}：带宽峰值与均值",
            "subtitle": "峰值/均值均按入向和出向取最大值；红色虚线为 80%×带宽字段。",
            "unit": "Mbps",
            "yMax": max_bw,
            "series": build_series(group_rows, "bandwidth"),
            "thresholds": [{"name": f"80%阈值 {value:g}M", "value": value} for value in bw_thresholds],
        },
        {
            "id": f"{group_key}_util",
            "title": f"{title}：峰值利用率与均值利用率",
            "subtitle": "峰值利用率取入向/出向较大值；均值利用率按入向/出向均值折算后取较大值。",
            "unit": "%",
            "yMax": 100,
            "series": build_series(group_rows, "util"),
            "thresholds": [{"name": "80%阈值", "value": 80}],
        },
        {
            "id": f"{group_key}_latency",
            "title": f"{title}：平均延迟",
            "subtitle": "延迟取线路日报中的平均延迟；不叠加基线，保持趋势可读。",
            "unit": "ms",
            "yMax": round(max_latency * 1.25, 2) if max_latency else 1,
            "series": build_series(group_rows, "latency"),
            "thresholds": [],
        },
    ]


def build_report_data(rows: list[dict]) -> dict:
    groups = []
    for group_key, title, line_nos in GROUPS:
        group_rows = [row for row in rows if row["line_no"] in line_nos]
        latest_by_line = {}
        for row in group_rows:
            latest_by_line[row["line_no"]] = row
        groups.append(
            {
                "id": group_key,
                "title": title,
                "lines": [
                    {
                        "lineNo": row["line_no"],
                        "label": row["label"],
                        "carrier": row.get("carrier"),
                        "bandwidth": row.get("bandwidth_mbps"),
                        "usage": row.get("usage"),
                    }
                    for row in sorted(latest_by_line.values(), key=lambda item: item["line_no"])
                ],
                "charts": chart_config(group_key, title, group_rows),
            }
        )
    dates = latest_seven_dates()
    return {"dates": [date.fromisoformat(day).strftime("%m-%d") for day in dates], "fullDates": dates, "groups": groups}


HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>线路近7天带宽、利用率与延迟交互报告</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: #f5f7fa;
      color: #1f2430;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      line-height: 1.58;
    }
    main {
      max-width: 1360px;
      margin: 0 auto;
      padding: 28px 24px 56px;
    }
    header {
      background: #fff;
      border: 1px solid #e4e8f0;
      border-radius: 8px;
      padding: 24px 28px;
      box-shadow: 0 2px 12px rgba(31, 36, 48, 0.06);
    }
    h1 { margin: 0 0 8px; font-size: 26px; letter-spacing: 0; }
    h2 { margin: 34px 0 14px; padding-left: 12px; border-left: 4px solid #1f4e79; font-size: 20px; }
    h3 { margin: 0; font-size: 17px; }
    p { color: #626b80; margin: 8px 0 0; }
    .chart-card, .line-table {
      background: #fff;
      border: 1px solid #e4e8f0;
      border-radius: 8px;
      box-shadow: 0 2px 12px rgba(31, 36, 48, 0.05);
    }
    .line-table { width: 100%; border-collapse: collapse; margin-bottom: 18px; overflow: hidden; }
    .line-table th, .line-table td { padding: 8px 10px; border-bottom: 1px solid #edf0f5; text-align: left; font-size: 13px; }
    .line-table th { background: #f3f6fb; color: #263044; }
    .chart-card { position: relative; padding: 18px 18px 12px; margin: 16px 0 22px; }
    .chart-subtitle { color: #6f768a; font-size: 13px; margin-top: 4px; }
    .chart-host { width: 100%; height: 430px; margin-top: 10px; }
    .tooltip {
      position: fixed;
      z-index: 20;
      pointer-events: none;
      background: rgba(255, 255, 255, 0.98);
      border: 1px solid #d9dee9;
      border-radius: 8px;
      box-shadow: 0 8px 26px rgba(31, 36, 48, 0.16);
      padding: 10px 12px;
      min-width: 230px;
      max-width: 340px;
      font-size: 12px;
      display: none;
    }
    .tooltip strong { display: block; color: #1f2430; margin-bottom: 4px; }
    .tooltip div { color: #4e586d; white-space: nowrap; }
    .legend { display: flex; flex-wrap: wrap; gap: 8px 18px; margin-top: 10px; font-size: 12px; color: #3f485c; }
    .legend-item { display: inline-flex; align-items: center; gap: 6px; }
    .legend-line { width: 24px; height: 0; border-top: 3px solid var(--c); }
    .legend-line.dashed { border-top-style: dashed; }
    .note { margin-top: 12px; color: #6f768a; font-size: 13px; }
    svg { width: 100%; height: 100%; display: block; }
    .axis text { fill: #6f768a; font-size: 12px; }
    .axis line, .axis path { stroke: #d7dbe7; }
    .grid line { stroke: #e6e8f0; stroke-width: 1; }
    .series-line { fill: none; stroke-width: 2.4; }
    .point { cursor: crosshair; stroke: #fff; stroke-width: 1.4; }
    .threshold { stroke: #c62828; stroke-width: 2; stroke-dasharray: 7 6; }
    .threshold-label { fill: #c62828; font-size: 12px; font-weight: 600; }
    @media (max-width: 720px) {
      main { padding: 16px 12px 40px; }
      header { padding: 18px; }
      .chart-host { height: 360px; }
    }
  </style>
</head>
<body>
<main>
  <header>
    <h1>线路近7天带宽、利用率与延迟交互报告</h1>
    <p>数据周期：2026-06-05 至 2026-06-11；数据源：docker/volumes/deer-flow-data/bandwidth-lines。</p>
    <p>鼠标移动到曲线点上，可查看该日期、线路、入/出峰值、入/出均值、峰值利用率、均值利用率和延迟。</p>
  </header>
  <div id="report"></div>
</main>
<div id="tooltip" class="tooltip"></div>
<script id="report-data" type="application/json">__DATA__</script>
<script>
const reportData = JSON.parse(document.getElementById("report-data").textContent);
const tooltip = document.getElementById("tooltip");
const NS = "http://www.w3.org/2000/svg";

function el(name, attrs = {}, text = "") {
  const node = document.createElementNS(NS, name);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  if (text) node.textContent = text;
  return node;
}

function fmt(value, unit) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  const n = Number(value);
  const digits = unit === "%" ? 2 : unit === "Mbps" ? 2 : 2;
  return `${n.toFixed(digits)}${unit}`;
}

function pointTooltip(seriesName, point, unit) {
  return `
    <strong>${seriesName}</strong>
    <div>日期：${point.fullDate}</div>
    <div>线路：${point.line}</div>
    <div>当前值：${fmt(point.value, unit)}</div>
    <div>带宽字段：${point.bandwidth}M</div>
    <div>入/出峰值：${point.inPeak ?? "-"} / ${point.outPeak ?? "-"} Mbps</div>
    <div>入/出均值：${point.inAvg ?? "-"} / ${point.outAvg ?? "-"} Mbps</div>
    <div>峰值带宽：${fmt(point.peakBw, "Mbps")}</div>
    <div>均值带宽：${fmt(point.avgBw, "Mbps")}</div>
    <div>峰值利用率：${fmt(point.peakUtil, "%")}</div>
    <div>均值利用率：${fmt(point.avgUtil, "%")}</div>
    <div>平均延迟：${fmt(point.latency, "ms")}</div>
  `;
}

function showTooltip(event, html) {
  tooltip.innerHTML = html;
  tooltip.style.display = "block";
  const pad = 16;
  const rect = tooltip.getBoundingClientRect();
  let x = event.clientX + 14;
  let y = event.clientY + 14;
  if (x + rect.width + pad > window.innerWidth) x = event.clientX - rect.width - 14;
  if (y + rect.height + pad > window.innerHeight) y = event.clientY - rect.height - 14;
  tooltip.style.left = `${x}px`;
  tooltip.style.top = `${y}px`;
}

function hideTooltip() {
  tooltip.style.display = "none";
}

function renderChart(host, config) {
  const width = 1120;
  const height = 410;
  const margin = { top: 24, right: 42, bottom: 44, left: 62 };
  const plotW = width - margin.left - margin.right;
  const plotH = height - margin.top - margin.bottom;
  const dates = reportData.dates;
  const yMax = config.yMax || 1;
  const yTicks = 5;

  const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": config.title });
  host.innerHTML = "";
  host.appendChild(svg);

  const grid = el("g", { class: "grid" });
  svg.appendChild(grid);
  for (let i = 0; i <= yTicks; i++) {
    const y = margin.top + plotH - (plotH * i / yTicks);
    grid.appendChild(el("line", { x1: margin.left, y1: y, x2: margin.left + plotW, y2: y }));
  }

  const axis = el("g", { class: "axis" });
  svg.appendChild(axis);
  axis.appendChild(el("line", { x1: margin.left, y1: margin.top, x2: margin.left, y2: margin.top + plotH }));
  axis.appendChild(el("line", { x1: margin.left, y1: margin.top + plotH, x2: margin.left + plotW, y2: margin.top + plotH }));

  for (let i = 0; i <= yTicks; i++) {
    const value = yMax * i / yTicks;
    const y = margin.top + plotH - (plotH * i / yTicks);
    axis.appendChild(el("text", { x: margin.left - 10, y: y + 4, "text-anchor": "end" }, config.unit === "%" ? `${Math.round(value)}%` : value.toFixed(value >= 10 ? 0 : 1)));
  }

  dates.forEach((date, i) => {
    const x = margin.left + (dates.length === 1 ? plotW / 2 : plotW * i / (dates.length - 1));
    axis.appendChild(el("text", { x, y: margin.top + plotH + 28, "text-anchor": "middle" }, date));
  });

  const xFor = index => margin.left + (dates.length === 1 ? plotW / 2 : plotW * index / (dates.length - 1));
  const yFor = value => margin.top + plotH - (Number(value) / yMax) * plotH;

  for (const threshold of config.thresholds || []) {
    if (threshold.value < 0 || threshold.value > yMax) continue;
    const y = yFor(threshold.value);
    svg.appendChild(el("line", { class: "threshold", x1: margin.left, y1: y, x2: margin.left + plotW, y2: y }));
    svg.appendChild(el("text", { class: "threshold-label", x: margin.left + plotW - 4, y: y - 6, "text-anchor": "end" }, threshold.name));
  }

  for (const series of config.series) {
    const d = series.points.map((point, i) => `${i === 0 ? "M" : "L"} ${xFor(i)} ${yFor(point.value)}`).join(" ");
    svg.appendChild(el("path", {
      d,
      class: "series-line",
      stroke: series.color,
      "stroke-dasharray": series.dash ? "8 6" : "none",
    }));
    series.points.forEach((point, i) => {
      const circle = el("circle", {
        class: "point",
        cx: xFor(i),
        cy: yFor(point.value),
        r: 5,
        fill: series.color,
      });
      circle.addEventListener("mouseenter", event => showTooltip(event, pointTooltip(series.name, point, config.unit)));
      circle.addEventListener("mousemove", event => showTooltip(event, pointTooltip(series.name, point, config.unit)));
      circle.addEventListener("mouseleave", hideTooltip);
      svg.appendChild(circle);
    });
  }
}

function renderLegend(container, config) {
  const legend = document.createElement("div");
  legend.className = "legend";
  for (const series of config.series) {
    const item = document.createElement("span");
    item.className = "legend-item";
    item.innerHTML = `<span class="legend-line ${series.dash ? "dashed" : ""}" style="--c:${series.color}"></span>${series.name}`;
    legend.appendChild(item);
  }
  for (const threshold of config.thresholds || []) {
    const item = document.createElement("span");
    item.className = "legend-item";
    item.innerHTML = `<span class="legend-line dashed" style="--c:#c62828"></span>${threshold.name}`;
    legend.appendChild(item);
  }
  container.appendChild(legend);
}

function render() {
  const root = document.getElementById("report");
  for (const group of reportData.groups) {
    const section = document.createElement("section");
    section.innerHTML = `<h2>${group.title}</h2>`;

    const table = document.createElement("table");
    table.className = "line-table";
    table.innerHTML = `<thead><tr><th>线路</th><th>运营商</th><th>带宽</th><th>用途</th></tr></thead><tbody>${
      group.lines.map(line => `<tr><td>${line.label}</td><td>${line.carrier}</td><td>${line.bandwidth}M</td><td>${line.usage}</td></tr>`).join("")
    }</tbody>`;
    section.appendChild(table);

    for (const chart of group.charts) {
      const card = document.createElement("article");
      card.className = "chart-card";
      card.innerHTML = `<h3>${chart.title}</h3><div class="chart-subtitle">${chart.subtitle}</div><div id="${chart.id}" class="chart-host"></div>`;
      section.appendChild(card);
      renderLegend(card, chart);
      renderChart(card.querySelector(".chart-host"), chart);
    }
    root.appendChild(section);
  }
}

render();
window.addEventListener("resize", () => {
  document.querySelectorAll(".chart-host").forEach((host, index) => {
    const chart = reportData.groups.flatMap(group => group.charts)[index];
    renderChart(host, chart);
  });
});
</script>
</body>
</html>
"""


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dates = latest_seven_dates()
    rows = load_rows(dates)
    report_data = build_report_data(rows)
    html_text = HTML_TEMPLATE.replace("__DATA__", json.dumps(report_data, ensure_ascii=False))
    OUTPUT_FILE.write_text(html_text, encoding="utf-8")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()
