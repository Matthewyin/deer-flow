#!/usr/bin/env python3
import argparse
import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path


DEFAULT_LINE_COUNT = 13
DEFAULT_GROUP_COUNT = 6


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="验证 network-bandwidth-reports 技能生成结果")
    parser.add_argument("--repo", required=True, help="DeerFlow 仓库根目录")
    parser.add_argument("--days", type=int, default=7, help="主要验证天数")
    parser.add_argument("--end-date", default="", help="可选截止日期 YYYY-MM-DD")
    return parser.parse_args()


def extract_payload(html_text: str) -> dict:
    marker = "const reportData = "
    start = html_text.find(marker)
    if start < 0:
        raise AssertionError("HTML 缺少 reportData")
    start += len(marker)
    end = html_text.find(";\nconst chartInstances", start)
    if end < 0:
        raise AssertionError("HTML reportData 结束标记异常")
    return json.loads(html_text[start:end])


def expected_latest_window(repo: Path, days: int, end_date: str) -> tuple[str, str]:
    db_path = repo / "backend/.deer-flow/db/network_ops.db"
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT report_date, COUNT(DISTINCT line_no) AS line_count "
            "FROM bandwidth_lines "
            "WHERE line_no IN (5,6,151,152,153,154,159,160,161,162,201,202,203) "
            "GROUP BY report_date ORDER BY report_date"
        ).fetchall()
    finally:
        conn.close()
    complete = [row[0] for row in rows if row[1] == DEFAULT_LINE_COUNT]
    if not complete:
        raise AssertionError("数据库没有完整目标线路日期")
    end = end_date or complete[-1]
    if end not in complete:
        raise AssertionError(f"截止日期不是完整日期：{end}")
    selected = complete[complete.index(end) - days + 1 : complete.index(end) + 1]
    if len(selected) != days:
        raise AssertionError(f"完整日期不足 {days} 天")
    return selected[0], selected[-1]


def run_generator(repo: Path, days: int, mode: str, end_date: str, output: Path) -> tuple[dict, str]:
    script = Path(__file__).resolve().with_name("generate_report.py")
    cmd = [
        sys.executable,
        str(script),
        "--repo",
        str(repo),
        "--days",
        str(days),
        "--mode",
        mode,
        "--output",
        str(output),
    ]
    if end_date:
        cmd.extend(["--end-date", end_date])
    result = subprocess.run(cmd, text=True, capture_output=True, check=True)
    if not output.exists():
        raise AssertionError(f"生成器没有输出 HTML：{output}")
    return json.loads(result.stdout), output.read_text(encoding="utf-8")


def assert_report(repo: Path, days: int, mode: str, end_date: str, tmpdir: Path) -> dict:
    output = tmpdir / f"network-bandwidth-{mode}-{days}.html"
    summary, html_text = run_generator(repo, days, mode, end_date, output)
    payload = extract_payload(html_text)
    start, end = expected_latest_window(repo, days, end_date)

    checks = {
        "period_start": payload["period"]["start"] == start,
        "period_end": payload["period"]["end"] == end,
        "mode": payload["mode"] == mode,
        "days": payload["days"] == days,
        "line_count": payload["line_count"] == DEFAULT_LINE_COUNT,
        "record_count": payload["record_count"] == days * DEFAULT_LINE_COUNT,
        "chart_count_payload": payload["chart_count"] == DEFAULT_GROUP_COUNT * 3,
        "chart_divs": html_text.count('class="chart"') == DEFAULT_GROUP_COUNT * 3,
        "no_png": ".png" not in html_text.lower(),
        "echarts_550": "echarts@5.5.0" in html_text,
        "resize_listener": 'window.addEventListener("resize"' in html_text,
        "no_baseline_series": "基线趋势" not in html_text and "baseline series" not in html_text.lower(),
        "bandwidth_threshold": "threshold_mbps" in html_text,
        "util_threshold": "80% 阈值" in html_text,
        "tooltip_details": all(key in html_text for key in ["入向峰值", "出向峰值", "平均延迟", "峰值利用率", "均值利用率"]),
        "summary_matches_stdout": summary["record_count"] == payload["record_count"],
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise AssertionError(f"{mode}/{days} eval 失败：" + "、".join(failed))
    return {
        "mode": mode,
        "days": days,
        "output": str(output),
        "period": payload["period"],
        "line_count": payload["line_count"],
        "record_count": payload["record_count"],
        "chart_count": payload["chart_count"],
    }


def main() -> None:
    args = parse_args()
    repo = Path(args.repo).expanduser().resolve()
    cases = [(args.days, "custom" if args.days not in (1, 7) else ("daily" if args.days == 1 else "weekly"))]
    if args.days != 1:
        cases.append((1, "daily"))
    if args.days != 7:
        cases.append((7, "weekly"))

    results = []
    with tempfile.TemporaryDirectory(prefix="network-bandwidth-eval-") as temp:
        tmpdir = Path(temp)
        for days, mode in cases:
            results.append(assert_report(repo, days, mode, args.end_date, tmpdir))
    print(json.dumps({"status": "pass", "cases": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
