#!/usr/bin/env python3
"""生成指定线路组近 7 天带宽、利用率和延迟曲线报告。"""

from __future__ import annotations

import csv
import html
import json
import os
from collections import defaultdict
from datetime import date
from pathlib import Path

os.environ.setdefault("XDG_CACHE_HOME", "/private/tmp")
os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/matplotlib-cache")
Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.font_manager import FontProperties

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "docker/volumes/deer-flow-data/bandwidth-lines"
OUTPUT_DIR = ROOT / "reports/bandwidth_curve_report_2026-06-12"

GROUPS = [
    ("tls_tencent", "混合云TLS售票-腾讯公有云", [151, 152]),
    ("tls_aliyun", "混合云TLS售票-阿里公有云", [153, 154]),
    ("beijing_single", "北京单场售票", [5, 6]),
    ("three_centers", "两网三中心", [159, 160, 161, 162]),
    ("w5h_b", "西五环互联网B区", [201, 202, 203]),
]

COLORS = ["#1F4E79", "#2F6B3F", "#4B3F72", "#005F73", "#3A506B"]
RED = "#C62828"
INK = "#1F2430"
MUTED = "#6F768A"
GRID = "#E6E8F0"
PANEL = "#FFFFFF"
SURFACE = "#FCFCFD"

FONT_PATHS = [
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
]


def font_prop(size: int, weight: str = "normal") -> FontProperties:
    for path in FONT_PATHS:
        if Path(path).exists():
            return FontProperties(fname=path, size=size, weight=weight)
    return FontProperties(size=size, weight=weight)


FONT = font_prop(10)
TITLE_FONT = font_prop(15, "bold")
SUBTITLE_FONT = font_prop(10)
LEGEND_FONT = font_prop(8)


def latest_seven_dates() -> list[str]:
    files = sorted(p.stem for p in DATA_DIR.glob("*.json"))
    return files[-7:]


def line_label(row: dict) -> str:
    usage = row.get("usage") or ""
    suffix = ""
    if "阿里云" in usage:
        suffix = " 阿里"
    elif "腾讯云" in usage:
        suffix = " 腾讯"
    return f"#{row['line_no']} {row.get('carrier', '')}{suffix}"


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
            enriched["report_date"] = day
            enriched["date_obj"] = date.fromisoformat(day)
            enriched["label"] = line_label(row)
            enriched["peak_bw_mbps"] = max(in_peak, out_peak)
            enriched["avg_bw_mbps"] = max(in_avg, out_avg)
            enriched["peak_util_pct"] = max(in_peak_util, out_peak_util)
            enriched["avg_util_pct"] = max(in_avg_util, out_avg_util)
            enriched["threshold_bw_mbps"] = (safe_float(row.get("bandwidth_mbps")) or 0) * 0.8
            rows.append(enriched)
    return rows


def setup_axis(ax, ylabel: str) -> None:
    ax.set_facecolor(PANEL)
    ax.grid(True, axis="y", color=GRID, linewidth=0.8)
    ax.grid(False, axis="x")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#D7DBE7")
    ax.spines["bottom"].set_color("#D7DBE7")
    ax.tick_params(colors=MUTED, labelsize=9)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontproperties(FONT)
    ax.set_ylabel(ylabel, fontproperties=FONT, color=INK)
    locator = mdates.DayLocator()
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))


def add_header(fig, ax, title: str, subtitle: str) -> None:
    left = ax.get_position().x0
    fig.text(left, 0.985, title, ha="left", va="top", fontproperties=TITLE_FONT, color=INK)
    fig.text(left, 0.94, subtitle, ha="left", va="top", fontproperties=SUBTITLE_FONT, color=MUTED)
    fig.subplots_adjust(top=0.82, bottom=0.14, left=0.08, right=0.98)


def legend(ax, columns: int) -> None:
    handles, labels = ax.get_legend_handles_labels()
    unique: dict[str, object] = {}
    for handle, label in zip(handles, labels):
        if label not in unique:
            unique[label] = handle
    leg = ax.legend(
        unique.values(),
        unique.keys(),
        loc="lower left",
        bbox_to_anchor=(0, 1.01),
        frameon=False,
        ncol=columns,
        borderaxespad=0,
        prop=LEGEND_FONT,
    )
    for text in leg.get_texts():
        text.set_color(INK)


def series_by_line(rows: list[dict]) -> dict[int, list[dict]]:
    grouped: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["line_no"]].append(row)
    return {line_no: sorted(items, key=lambda r: r["report_date"]) for line_no, items in grouped.items()}


def latest_rows(rows: list[dict]) -> list[dict]:
    latest_day = max(row["report_date"] for row in rows)
    return [row for row in rows if row["report_date"] == latest_day]


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0


def draw_bandwidth_chart(group_key: str, title: str, rows: list[dict], out_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(12.8, 7.2), dpi=160, facecolor=SURFACE)
    by_line = series_by_line(rows)
    for idx, (line_no, items) in enumerate(by_line.items()):
        color = COLORS[idx % len(COLORS)]
        x = [item["date_obj"] for item in items]
        label = items[-1]["label"]
        ax.plot(x, [item["peak_bw_mbps"] for item in items], color=color, marker="o", linewidth=1.8, label=f"{label} 峰值")
        ax.plot(x, [item["avg_bw_mbps"] for item in items], color=color, marker="s", linewidth=1.5, linestyle="--", label=f"{label} 均值")

    latest = latest_rows(rows)
    thresholds = sorted({round(row["threshold_bw_mbps"], 2) for row in rows if row["threshold_bw_mbps"] > 0})
    for value in thresholds:
        ax.axhline(value, color=RED, linestyle=(0, (5, 4)), linewidth=1.3, label=f"80%阈值 {value:g}M")

    y_max = max(row["bandwidth_mbps"] for row in rows)
    ax.set_ylim(0, y_max)
    setup_axis(ax, "带宽 Mbps")
    add_header(fig, ax, f"{title}：带宽峰值与均值", "峰值/均值均按入向和出向取最大值；红色虚线为 80%×带宽字段。")
    legend(ax, min(4, max(2, len(by_line))))
    path = out_dir / f"{group_key}_bandwidth.png"
    fig.savefig(path, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    return path


def draw_util_chart(group_key: str, title: str, rows: list[dict], out_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(12.8, 7.2), dpi=160, facecolor=SURFACE)
    by_line = series_by_line(rows)
    for idx, (line_no, items) in enumerate(by_line.items()):
        color = COLORS[idx % len(COLORS)]
        x = [item["date_obj"] for item in items]
        label = items[-1]["label"]
        ax.plot(x, [item["peak_util_pct"] for item in items], color=color, marker="o", linewidth=1.8, label=f"{label} 峰值利用率")
        ax.plot(x, [item["avg_util_pct"] for item in items], color=color, marker="s", linewidth=1.5, linestyle="--", label=f"{label} 均值利用率")

    ax.axhline(80, color=RED, linestyle=(0, (5, 4)), linewidth=1.4, label="80%阈值")

    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter())
    setup_axis(ax, "利用率")
    add_header(fig, ax, f"{title}：峰值利用率与均值利用率", "峰值利用率取入向/出向较大值；均值利用率按入向/出向均值折算后取较大值。")
    legend(ax, min(4, max(2, len(by_line))))
    path = out_dir / f"{group_key}_utilization.png"
    fig.savefig(path, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    return path


def draw_latency_chart(group_key: str, title: str, rows: list[dict], out_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(12.8, 7.2), dpi=160, facecolor=SURFACE)
    by_line = series_by_line(rows)
    for idx, (line_no, items) in enumerate(by_line.items()):
        color = COLORS[idx % len(COLORS)]
        x = [item["date_obj"] for item in items]
        label = items[-1]["label"]
        ax.plot(x, [safe_float(item.get("latency_avg_ms")) or 0 for item in items], color=color, marker="o", linewidth=1.8, label=label)

    max_latency = max(safe_float(row.get("latency_avg_ms")) or 0 for row in rows)
    ax.set_ylim(0, max_latency * 1.25)
    setup_axis(ax, "延迟 ms")
    add_header(fig, ax, f"{title}：平均延迟", "延迟取线路日报中的平均延迟；不叠加基线，保持趋势可读。")
    legend(ax, min(4, max(2, len(by_line))))
    path = out_dir / f"{group_key}_latency.png"
    fig.savefig(path, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    return path


def write_csv(rows: list[dict], out_dir: Path) -> Path:
    path = out_dir / "chart_data.csv"
    fields = [
        "report_date", "line_no", "label", "usage", "bandwidth_mbps",
        "peak_bw_mbps", "avg_bw_mbps", "peak_util_pct", "avg_util_pct",
        "latency_avg_ms", "bw_peak_baseline_mbps", "latency_baseline_ms",
        "threshold_bw_mbps",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in sorted(rows, key=lambda r: (r["line_no"], r["report_date"])):
            writer.writerow({field: row.get(field) for field in fields})
    return path


def write_html(dates: list[str], image_map: dict[str, dict[str, Path]], csv_path: Path, out_dir: Path) -> Path:
    sections = []
    for _, title, _ in GROUPS:
        imgs = image_map[title]
        sections.append(
            f"""
            <section>
              <h2>{html.escape(title)}</h2>
              <figure><img src="{imgs['bandwidth'].name}" alt="{html.escape(title)} 带宽图"><figcaption>带宽峰值、均值与 80% 带宽阈值。</figcaption></figure>
              <figure><img src="{imgs['util'].name}" alt="{html.escape(title)} 利用率图"><figcaption>峰值利用率、均值利用率与 80% 利用率阈值。</figcaption></figure>
              <figure><img src="{imgs['latency'].name}" alt="{html.escape(title)} 延迟图"><figcaption>平均延迟趋势。</figcaption></figure>
            </section>
            """
        )

    doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>线路近7天带宽、利用率与延迟曲线报告</title>
  <style>
    body {{ margin: 0; background: #f6f7fb; color: #1f2430; font-family: "Heiti SC", "Hiragino Sans", "Songti SC", sans-serif; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 24px 56px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    h2 {{ margin: 36px 0 16px; font-size: 22px; }}
    p, li, figcaption {{ color: #5d6577; line-height: 1.65; }}
    .meta {{ margin-bottom: 24px; }}
    .note {{ background: #fff; border: 1px solid #e6e8f0; border-radius: 8px; padding: 16px 20px; }}
    figure {{ margin: 18px 0 28px; background: #fff; border: 1px solid #e6e8f0; border-radius: 8px; padding: 14px; }}
    img {{ display: block; width: 100%; height: auto; }}
    a {{ color: #1f4e79; }}
  </style>
</head>
<body>
<main>
  <h1>线路近7天带宽、利用率与延迟曲线报告</h1>
  <p class="meta">数据周期：{dates[0]} 至 {dates[-1]}；生成日期：2026-06-12；数据源：docker/volumes/deer-flow-data/bandwidth-lines。</p>
  <div class="note">
    <p>口径说明：峰值带宽取 max(入向峰值, 出向峰值)，均值带宽取 max(入向均值, 出向均值)。峰值利用率取入向/出向峰值利用率较大值；均值利用率按入向/出向均值和对应方向容量折算后取较大值。</p>
    <p>为保持图表可读性，本版不叠加峰值基线、均值基线和延迟基线。带宽图红色虚线为 80%×带宽字段，利用率图红色虚线为 80%。明细数据见 <a href="{csv_path.name}">{csv_path.name}</a>。</p>
  </div>
  {''.join(sections)}
</main>
</body>
</html>
"""
    path = out_dir / "index.html"
    path.write_text(doc, encoding="utf-8")
    return path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dates = latest_seven_dates()
    rows = load_rows(dates)
    by_group = {title: [row for row in rows if row["line_no"] in line_nos] for _, title, line_nos in GROUPS}
    image_map: dict[str, dict[str, Path]] = {}
    for group_key, title, _line_nos in GROUPS:
        group_rows = by_group[title]
        image_map[title] = {
            "bandwidth": draw_bandwidth_chart(group_key, title, group_rows, OUTPUT_DIR),
            "util": draw_util_chart(group_key, title, group_rows, OUTPUT_DIR),
            "latency": draw_latency_chart(group_key, title, group_rows, OUTPUT_DIR),
        }
    csv_path = write_csv(rows, OUTPUT_DIR)
    html_path = write_html(dates, image_map, csv_path, OUTPUT_DIR)
    print(html_path)


if __name__ == "__main__":
    main()
