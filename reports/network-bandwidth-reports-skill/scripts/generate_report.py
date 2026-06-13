#!/usr/bin/env python3
import argparse
import datetime as dt
import html
import json
import sqlite3
from pathlib import Path


DEFAULT_GROUPS = [
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成 DeerFlow 网络带宽 HTML 报告")
    parser.add_argument("--repo", required=True, help="DeerFlow 仓库根目录")
    parser.add_argument("--days", type=int, default=7, help="报告天数")
    parser.add_argument("--mode", choices=["daily", "weekly", "custom"], default="", help="报告类型")
    parser.add_argument("--end-date", default="", help="截止日期 YYYY-MM-DD；不填则自动取最新完整日期")
    parser.add_argument("--output", required=True, help="输出 HTML 路径")
    parser.add_argument("--groups-json", default="", help="自定义线路组 JSON 文件")
    return parser.parse_args()


def load_groups(path: str) -> list[dict]:
    if not path:
        return DEFAULT_GROUPS
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise RuntimeError("--groups-json 必须是数组")
    for item in data:
        if not item.get("name") or not item.get("line_nos"):
            raise RuntimeError("每个线路组必须包含 name 和 line_nos")
    return data


def date_range(start: str, end: str) -> list[str]:
    current = dt.date.fromisoformat(start)
    last = dt.date.fromisoformat(end)
    days = []
    while current <= last:
        days.append(current.isoformat())
        current += dt.timedelta(days=1)
    return days


def find_complete_dates(conn: sqlite3.Connection, line_nos: list[int]) -> dict[str, int]:
    placeholders = ",".join("?" for _ in line_nos)
    rows = conn.execute(
        "SELECT report_date, COUNT(DISTINCT line_no) AS line_count "
        "FROM bandwidth_lines "
        f"WHERE line_no IN ({placeholders}) "
        "GROUP BY report_date ORDER BY report_date",
        line_nos,
    ).fetchall()
    expected = len(set(line_nos))
    return {row["report_date"]: row["line_count"] for row in rows if row["line_count"] == expected}


def choose_window(complete_dates: dict[str, int], days: int, end_date: str) -> list[str]:
    if days < 1:
        raise RuntimeError("--days 必须大于 0")
    available = sorted(complete_dates)
    if not available:
        raise RuntimeError("没有找到完整日期数据")
    latest = end_date or available[-1]
    if latest not in complete_dates:
        raise RuntimeError(f"截止日期不是完整数据日期：{latest}")
    end = dt.date.fromisoformat(latest)
    start = end - dt.timedelta(days=days - 1)
    selected = date_range(start.isoformat(), end.isoformat())
    missing = [day for day in selected if day not in complete_dates]
    if missing:
        raise RuntimeError("最新完整窗口不连续，缺失日期：" + "、".join(missing))
    return selected


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


def report_mode(mode: str, days: int) -> str:
    if mode:
        return mode
    if days == 1:
        return "daily"
    if days == 7:
        return "weekly"
    return "custom"


def report_title(mode: str, days: int) -> str:
    labels = {
        "daily": f"网络带宽日报（{days}天）",
        "weekly": f"网络带宽周报（{days}天）",
        "custom": f"网络带宽自定义报告（{days}天）",
    }
    return labels[mode]


def with_metrics(row: dict) -> dict:
    bandwidth = row.get("bandwidth_mbps") or 0
    in_peak = row.get("in_peak_mbps") or 0
    out_peak = row.get("out_peak_mbps") or 0
    in_avg = row.get("in_avg_mbps") or 0
    out_avg = row.get("out_avg_mbps") or 0
    row["max_peak"] = round(max(in_peak, out_peak), 4)
    row["max_avg"] = round(max(in_avg, out_avg), 4)
    row["peak_util_pct"] = round(row["max_peak"] / bandwidth * 100, 4) if bandwidth else None
    row["avg_util_pct"] = round(row["max_avg"] / bandwidth * 100, 4) if bandwidth else None
    row["threshold_mbps"] = round(bandwidth * 0.8, 4) if bandwidth else None
    row["line_label"] = f"#{row['line_no']} {row.get('carrier') or ''}".strip()
    return row


def load_records(conn: sqlite3.Connection, dates: list[str], line_nos: list[int]) -> list[dict]:
    line_placeholders = ",".join("?" for _ in line_nos)
    date_placeholders = ",".join("?" for _ in dates)
    sql = (
        "SELECT id, report_date, line_group, line_no, province, carrier, usage, "
        "bandwidth_mbps, long_distance_no, in_peak_mbps, in_avg_mbps, in_peak_util_pct, "
        "in_peak_time, out_peak_mbps, out_avg_mbps, out_peak_util_pct, out_peak_time, "
        "latency_avg_ms, bw_peak_baseline_mbps, bw_util_threshold_pct, latency_baseline_ms, "
        "latency_threshold_ms, created_at "
        "FROM bandwidth_lines "
        f"WHERE report_date IN ({date_placeholders}) AND line_no IN ({line_placeholders}) "
        "ORDER BY report_date, line_no"
    )
    rows = conn.execute(sql, [*dates, *line_nos]).fetchall()
    return [with_metrics(dict(row)) for row in rows]


def bandwidth_text(records: list[dict]) -> str:
    values = []
    for record in records:
        value = record.get("bandwidth_mbps")
        if value is not None and value not in values:
            values.append(value)
    return " → ".join(f"{fmt(value, 0)}M" for value in values)


def build_groups(records: list[dict], groups_config: list[dict], dates: list[str]) -> list[dict]:
    by_line_date = {(row["line_no"], row["report_date"]): row for row in records}
    groups = []
    for index, group_config in enumerate(groups_config):
        lines = []
        for line_no in group_config["line_nos"]:
            line_records = [by_line_date.get((line_no, day)) for day in dates]
            missing = [day for day, record in zip(dates, line_records) if record is None]
            if missing:
                raise RuntimeError(f"线路 {line_no} 缺少数据：" + "、".join(missing))
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
        bandwidth_values = [r["max_peak"] for line in lines for r in line["records"]]
        thresholds = [r["threshold_mbps"] for line in lines for r in line["records"] if r["threshold_mbps"] is not None]
        latencies = [r["latency_avg_ms"] for line in lines for r in line["records"] if r["latency_avg_ms"] is not None]
        groups.append(
            {
                "index": index,
                "name": group_config["name"],
                "dates": dates,
                "date_labels": [day[5:] for day in dates],
                "lines": lines,
                "y_bandwidth": round(max(bandwidth_values + thresholds) * 1.2, 2),
                "y_latency": round(max(max(latencies) * 1.3, 1), 2) if latencies else 1,
            }
        )
    return groups


def render_line_info(group: dict) -> str:
    rows = []
    for line in group["lines"]:
        rows.append(
            "<tr>"
            f"<td>{esc(line['line_label'])}</td><td>{esc(line['carrier'])}</td>"
            f"<td>{esc(line['bandwidth_text'])}</td><td>{esc(line['usage'])}</td>"
            "</tr>"
        )
    return '<div class="table-wrap"><table><thead><tr><th>线路</th><th>运营商</th><th>带宽</th><th>用途</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>"


def render_detail(group: dict) -> str:
    fields = ["in_peak", "out_peak", "max_peak", "in_avg", "out_avg", "max_avg", "峰值利用率", "均值利用率", "延迟ms", "带宽", "峰值基线", "延迟基线"]
    first = ['<th rowspan="2">日期</th>']
    second = []
    for line in group["lines"]:
        first.append(f'<th colspan="{len(fields)}">{esc(line["line_label"])}</th>')
        second.extend(f"<th>{esc(field)}</th>" for field in fields)
    body = []
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
        body.append("<tr>" + "".join(cells) + "</tr>")
    return '<div class="table-wrap detail"><table><thead><tr>' + "".join(first) + "</tr><tr>" + "".join(second) + "</tr></thead><tbody>" + "".join(body) + "</tbody></table></div>"


def render_summary(groups: list[dict]) -> tuple[str, list[dict]]:
    rows = []
    data = []
    for group in groups:
        for line in group["lines"]:
            records = line["records"]
            max_peak = max(record["max_peak"] for record in records)
            max_peak_util = max(record["peak_util_pct"] or 0 for record in records)
            max_avg_util = max(record["avg_util_pct"] or 0 for record in records)
            max_latency = max(record.get("latency_avg_ms") or 0 for record in records)
            if max_peak_util >= 80:
                css = "danger"
                assessment = "超80%阈值"
            elif max_peak_util >= 60:
                css = "warning"
                assessment = "较高"
            else:
                css = "normal"
                assessment = "正常"
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
            }
            data.append(item)
            rows.append(
                f'<tr class="{css}"><td>{esc(group["name"])}</td><td>{esc(line["line_label"])}</td>'
                f'<td>{esc(line["carrier"])}</td><td>{esc(line["bandwidth_text"])}</td>'
                f"<td>{fmt(max_peak)}</td><td>{pct(max_peak_util)}</td><td>{pct(max_avg_util)}</td>"
                f"<td>{fmt(max_latency)}</td><td>{esc(assessment)}</td></tr>"
            )
    return "".join(rows), data


def render_html(groups: list[dict], records: list[dict], mode: str, days: int, repo: Path, output: Path) -> str:
    generated_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    title = report_title(mode, days)
    summary_rows, summary_data = render_summary(groups)
    sections = []
    for group in groups:
        index = group["index"]
        sections.append(
            f'<section><h2>{index + 1}、{esc(group["name"])}</h2>'
            + "<h3>线路信息</h3>"
            + render_line_info(group)
            + f'<h3>带宽峰值 & 均值趋势</h3><div class="chart" id="chart_bw_{index}"></div>'
            + f'<h3>峰值利用率 & 均值利用率趋势</h3><div class="chart" id="chart_util_{index}"></div>'
            + f'<h3>延迟趋势</h3><div class="chart" id="chart_latency_{index}"></div>'
            "<h3>逐日明细</h3>" + render_detail(group) + "</section>"
        )
    payload = {
        "mode": mode,
        "days": days,
        "period": {"start": groups[0]["dates"][0], "end": groups[0]["dates"][-1]},
        "generated_at": generated_at,
        "source": str(repo / "backend/.deer-flow/db/network_ops.db"),
        "groups": groups,
        "summary": summary_data,
        "record_count": len(records),
        "line_count": len({row["line_no"] for row in records}),
        "chart_count": len(groups) * 3,
        "output": str(output),
    }
    data_json = json.dumps(payload, ensure_ascii=False)
    return """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
*{box-sizing:border-box}body{margin:0;background:#f5f7fa;color:#1f2933;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;font-size:14px;line-height:1.6}.page{max-width:1400px;margin:28px auto;padding:30px 40px;background:#fff;border-radius:8px;box-shadow:0 2px 12px rgba(0,0,0,.08)}h1{margin:0 0 12px;padding-bottom:14px;border-bottom:3px solid #5470C6;text-align:center;font-size:22px}.subtitle{text-align:center;color:#5b6472;font-size:13px}.note{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:18px 0;padding:14px 16px;border:1px solid #e8e8e8;background:#fafbfc;border-radius:8px}h2{margin:35px 0 14px;padding-left:12px;border-left:4px solid #5470C6;font-size:18px}h3{margin:20px 0 10px;color:#444;font-size:15px}.chart{width:100%;height:420px;margin:8px 0 18px;border:1px solid #e8e8e8;background:#fafbfc}.table-wrap{width:100%;overflow:auto;border:1px solid #e2e6ee;border-radius:6px}.detail{max-height:450px}table{width:100%;min-width:880px;border-collapse:collapse;font-size:12px}th,td{padding:7px 8px;border:1px solid #e3e7ef;text-align:center;white-space:nowrap}th{position:sticky;top:0;z-index:1;background:#f0f3f8}.detail thead tr:nth-child(2) th{top:33px}tbody tr:hover{background:#f5f8ff}.warning{background:#fff3e0}.danger{background:#ffebee}.tooltip-title{margin-bottom:6px;font-weight:700}.tooltip-block{margin:6px 0;padding-bottom:6px;border-bottom:1px solid #eee}@media(max-width:900px){.page{margin:0;padding:20px 14px;border-radius:0}.note{grid-template-columns:1fr}h1{font-size:19px}}
</style>
</head>
<body>
<main class="page">
<h1>__TITLE__</h1>
<p class="subtitle">数据周期：__START__ 至 __END__ ｜ 报告生成时间：__GENERATED_AT__ ｜ 数据源：network_ops.db / bandwidth_lines</p>
<div class="note"><div>线型：实线=峰值，虚线=均值</div><div>颜色：电信蓝、联通红、移动绿</div><div>阈值线：红色虚线 80%</div></div>
__SECTIONS__
<section><h2>总结汇总表</h2><div class="table-wrap"><table><thead><tr><th>分组</th><th>线路</th><th>运营商</th><th>带宽</th><th>最大峰值</th><th>最大峰值利用率</th><th>最大均值利用率</th><th>最大延迟</th><th>评估</th></tr></thead><tbody>__SUMMARY__</tbody></table></div></section>
</main>
<script>
const reportData = __DATA__;
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
    rows.push(`<div class="tooltip-block">${param.marker}<b>${param.seriesName}</b><br>` +
      `线路：${meta.line_label}<br>带宽字段：${formatValue(meta.bandwidth_mbps, "M")}<br>` +
      `入向峰值 / 出向峰值：${formatValue(meta.in_peak_mbps, " Mbps")} / ${formatValue(meta.out_peak_mbps, " Mbps")}<br>` +
      `入向均值 / 出向均值：${formatValue(meta.in_avg_mbps, " Mbps")} / ${formatValue(meta.out_avg_mbps, " Mbps")}<br>` +
      `峰值带宽：${formatValue(meta.max_peak, " Mbps")}<br>均值带宽：${formatValue(meta.max_avg, " Mbps")}<br>` +
      `峰值利用率：${formatValue(meta.peak_util_pct, "%")}<br>均值利用率：${formatValue(meta.avg_util_pct, "%")}<br>` +
      `平均延迟：${formatValue(meta.latency_avg_ms, " ms")}</div>`);
  });
  return rows.join("");
}
function baseOption(title, yName, yMax, series) {
  return {title:{text:title,left:"center",top:0,textStyle:{fontSize:14,color:"#333"}},tooltip:{trigger:"axis",backgroundColor:"rgba(255,255,255,0.95)",borderColor:"#ddd",textStyle:{color:"#333"},formatter:tooltipFormatter},legend:{top:25,type:"scroll"},grid:{left:"8%",right:"5%",bottom:"12%",top:"18%",containLabel:true},xAxis:{type:"category",boundaryGap:false,data:[]},yAxis:{type:"value",name:yName,min:0,max:yMax},series};
}
function dataPoint(record, field) { return { value: record[field], meta: record }; }
function bandwidthOption(group) {
  const series = [];
  group.lines.forEach((line) => {
    series.push({name:`${line.line_label} 峰值`,type:"line",smooth:true,symbol:"circle",symbolSize:5,lineStyle:{width:2,type:"solid",color:line.color},itemStyle:{color:line.color},data:line.records.map((record)=>dataPoint(record,"max_peak"))});
    series.push({name:`${line.line_label} 均值`,type:"line",smooth:true,symbol:"circle",symbolSize:4,lineStyle:{width:1.5,type:"dashed",color:line.color},itemStyle:{color:line.color},data:line.records.map((record)=>dataPoint(record,"max_avg"))});
    series.push({name:`${line.line_label} 80%(${line.bandwidth_text}×80%)`,type:"line",step:"end",symbol:"none",silent:true,lineStyle:{width:2,type:"dashed",color:"#FF4444"},itemStyle:{color:"#FF4444"},endLabel:{show:true,formatter:`${line.line_label} 80%`,color:"#FF4444"},data:line.records.map((record)=>({value:record.threshold_mbps}))});
  });
  const option = baseOption(`${group.name}：带宽峰值 & 均值`, "Mbps", group.y_bandwidth, series);
  option.xAxis.data = group.date_labels;
  return option;
}
function utilOption(group) {
  const series = [];
  group.lines.forEach((line) => {
    series.push({name:`${line.line_label} 峰值利用率`,type:"line",smooth:true,symbol:"circle",symbolSize:5,lineStyle:{width:2,type:"solid",color:line.color},itemStyle:{color:line.color},data:line.records.map((record)=>dataPoint(record,"peak_util_pct"))});
    series.push({name:`${line.line_label} 均值利用率`,type:"line",smooth:true,symbol:"circle",symbolSize:4,lineStyle:{width:1.5,type:"dashed",color:line.color},itemStyle:{color:line.color},data:line.records.map((record)=>dataPoint(record,"avg_util_pct"))});
  });
  if (series.length) series[0].markLine = {silent:true,symbol:"none",lineStyle:{width:2,type:"dashed",color:"#FF4444"},label:{formatter:"80% 阈值",color:"#FF4444"},data:[{yAxis:80,name:"80% 阈值"}]};
  const option = baseOption(`${group.name}：峰值利用率 & 均值利用率`, "%", 100, series);
  option.xAxis.data = group.date_labels;
  return option;
}
function latencyOption(group) {
  const series = [];
  group.lines.forEach((line) => {
    series.push({name:`${line.line_label} 延迟`,type:"line",smooth:true,symbol:"circle",symbolSize:5,lineStyle:{width:2,type:"solid",color:line.color},itemStyle:{color:line.color},data:line.records.map((record)=>dataPoint(record,"latency_avg_ms"))});
  });
  const option = baseOption(`${group.name}：延迟趋势`, "ms", group.y_latency, series);
  option.xAxis.data = group.date_labels;
  return option;
}
reportData.groups.forEach((group) => {
  [[`chart_bw_${group.index}`, bandwidthOption(group)], [`chart_util_${group.index}`, utilOption(group)], [`chart_latency_${group.index}`, latencyOption(group)]].forEach(([id, option]) => {
    const chart = echarts.init(document.getElementById(id));
    chart.setOption(option);
    chartInstances.push(chart);
  });
});
window.addEventListener("resize", () => chartInstances.forEach((chart) => chart.resize()));
</script>
</body>
</html>
""".replace("__TITLE__", esc(title)).replace("__START__", groups[0]["dates"][0]).replace("__END__", groups[0]["dates"][-1]).replace("__GENERATED_AT__", generated_at).replace("__SECTIONS__", "".join(sections)).replace("__SUMMARY__", summary_rows).replace("__DATA__", data_json)


def main() -> None:
    args = parse_args()
    repo = Path(args.repo).expanduser().resolve()
    db_path = repo / "backend/.deer-flow/db/network_ops.db"
    if not db_path.exists():
        raise RuntimeError(f"找不到数据库：{db_path}")
    output = Path(args.output).expanduser().resolve()
    groups_config = load_groups(args.groups_json)
    line_nos = [line_no for group in groups_config for line_no in group["line_nos"]]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        complete_dates = find_complete_dates(conn, line_nos)
        dates = choose_window(complete_dates, args.days, args.end_date)
        records = load_records(conn, dates, line_nos)
    finally:
        conn.close()
    expected_records = len(set(line_nos)) * args.days
    if len(records) != expected_records:
        raise RuntimeError(f"记录数不匹配：期望 {expected_records}，实际 {len(records)}")
    groups = build_groups(records, groups_config, dates)
    mode = report_mode(args.mode, args.days)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_html(groups, records, mode, args.days, repo, output), encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "mode": mode,
        "days": args.days,
        "period": {"start": dates[0], "end": dates[-1]},
        "line_count": len(set(line_nos)),
        "record_count": len(records),
        "chart_count": len(groups) * 3,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
