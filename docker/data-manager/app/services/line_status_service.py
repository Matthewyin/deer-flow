"""线路状态 HTML 日报解析服务。

解析包含 ECharts 图表的 HTML 日报，提取线路带宽/利用率/延迟数据，
保存为结构化 JSON 文件供 MCP server 入库。
"""

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SHARED_DATA_DIR = os.environ.get("SHARED_DATA_DIR", "/app/.deer-flow")

# 图表 ID 前缀到数据类型的映射
CHART_TYPES = {
    "bandwidth_traffic_": "traffic",   # 带宽流量 Kbps
    "bandwidth_percent_": "util",       # 带宽利用率 %
    "latency_": "latency",              # 延迟 ms
}


def _extract_date(filename: str, html_content: bytes = b"") -> str:
    """从文件名或 HTML 内容中提取报告日期，格式 YYYY-MM-DD。

    优先从文件名提取，其次从 HTML 内容中查找【YYYY-MM-DD】模式。
    """
    m = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    if m:
        return m.group(1)
    # 从 HTML 内容提取，匹配【2026-05-10】等中文日期标记
    if html_content:
        text = html_content.decode("utf-8", errors="ignore")
        m = re.search(r"【(\d{4}-\d{2}-\d{2})】", text)
        if m:
            return m.group(1)
    return datetime.now().strftime("%Y-%m-%d")


def _parse_chart_option(option_json: dict, chart_type: str) -> list[dict]:
    """解析单个 ECharts option JSON，提取线路数据。

    返回按线路顺序的数据列表，每项包含 line_name 和对应指标。
    """
    categories = option_json.get("_originalCategories", [])
    if not categories:
        return []

    series_list = option_json.get("series", [])

    peak_data = None
    avg_data = None
    for s in series_list:
        if s.get("type") != "bar":
            continue
        name = s.get("name", "")
        if "峰值" in name or "peak" in name.lower():
            peak_data = s.get("data", [])
        elif "均值" in name or "平均" in name or "avg" in name.lower():
            avg_data = s.get("data", [])

    results = []
    for i, line_name in enumerate(categories):
        entry = {"line_name": line_name}

        if chart_type == "traffic":
            entry["traffic_peak_kbps"] = _safe_num(peak_data, i)
            entry["traffic_avg_kbps"] = _safe_num(avg_data, i)
        elif chart_type == "util":
            entry["util_peak_pct"] = _safe_num(peak_data, i)
            entry["util_avg_pct"] = _safe_num(avg_data, i)
        elif chart_type == "latency":
            # 延迟图表只有峰值
            entry["latency_peak_ms"] = _safe_num(peak_data, i)

        results.append(entry)

    return results


def _safe_num(data_list: list | None, index: int) -> float | None:
    """安全提取数值，越界或 None 返回 None。"""
    if data_list is None or index >= len(data_list):
        return None
    val = data_list[index]
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def parse_html(html_content: bytes, filename: str) -> dict:
    """解析 HTML 日报，提取所有线路类别的状态数据。

    Args:
        html_content: HTML 文件原始字节
        filename: 原始文件名，用于提取日期

    Returns:
        结构化数据字典，按线路类别分组
    """
    soup = BeautifulSoup(html_content, "html.parser")
    report_date = _extract_date(filename, html_content)

    # 收集所有 chart 的 div id → (category, chart_type) 映射
    chart_map: dict[str, tuple[str, str]] = {}
    for div in soup.find_all("div", id=True):
        div_id = div["id"]
        for prefix, ctype in CHART_TYPES.items():
            if div_id.startswith(prefix):
                category = div_id[len(prefix):]
                chart_map[div_id] = (category, ctype)
                break

    # 从 script 标签提取 option JSON 并匹配 chart id
    # line_name → {field: value} 的中间结构，按类别分组
    category_data: dict[str, dict[str, dict]] = {}

    for script in soup.find_all("script"):
        text = script.string or ""
        # 匹配 var option_chart_N = {...}
        for m in re.finditer(r"var\s+(option_chart_\d+)\s*=\s*(\{.+?\})\s*;", text, re.DOTALL):
            var_name = m.group(1)
            json_str = m.group(2)

            try:
                option = json.loads(json_str)
            except json.JSONDecodeError:
                logger.warning(f"JSON 解析失败: {var_name}")
                continue

            # 通过 script 在 HTML 中的上下文找到对应的 chart id
            # 直接从 option 中无法知道 chart id，需要从 HTML 结构推断
            # 策略：扫描 option 前后紧邻的 div id
            chart_id = _find_chart_id_for_var(text, var_name, chart_map)
            if not chart_id:
                continue

            category, chart_type = chart_map[chart_id]
            if category not in category_data:
                category_data[category] = {}

            entries = _parse_chart_option(option, chart_type)
            for entry in entries:
                line_name = entry["line_name"]
                if line_name not in category_data[category]:
                    category_data[category][line_name] = {"line_name": line_name}
                category_data[category][line_name].update(
                    {k: v for k, v in entry.items() if k != "line_name" and v is not None}
                )

    # 转换为目标格式
    line_categories: dict[str, list[dict]] = {}
    for category, lines in category_data.items():
        line_categories[category] = sorted(lines.values(), key=lambda x: x["line_name"])

    return {
        "report_date": report_date,
        "source_file": filename,
        "parsed_at": datetime.now().isoformat(),
        "line_categories": line_categories,
    }


def _find_chart_id_for_var(script_text: str, var_name: str, chart_map: dict) -> str | None:
    """从 script 上下文中找到与 var 关联的 chart div id。

    策略：option JSON 之前通常有 echarts.init(document.getElementById('chart_id'))。
    在 script 标签全文中搜索 getElementById 调用，找到最近的一个。
    """
    # 搜索所有 getElementById 调用和 var 定义的位置
    elem_pattern = re.compile(r"getElementById\(['\"]([^'\"]+)['\"]\)")
    var_pos = script_text.find(var_name + " =")
    if var_pos == -1:
        var_pos = script_text.find(var_name + "=")

    # 找到 var 定义之前最近的 getElementById
    best_id = None
    best_dist = float("inf")
    for m in elem_pattern.finditer(script_text):
        div_id = m.group(1)
        if div_id in chart_map:
            dist = var_pos - m.start()
            if 0 < dist < best_dist:
                best_dist = dist
                best_id = div_id

    return best_id


def _td_text(td) -> str:
    return td.get_text(strip=True)


def _parse_bandwidth(text: str) -> int | None:
    if not text:
        return None
    m = re.search(r"(\d+)", text)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def _to_float(text: str) -> float | None:
    if not text:
        return None
    try:
        return float(text)
    except (ValueError, TypeError):
        return None


def _to_int(text: str) -> int | None:
    if not text:
        return None
    try:
        return int(text)
    except (ValueError, TypeError):
        try:
            return int(float(text))
        except (ValueError, TypeError):
            return None


def parse_line_table(html_content: bytes, filename: str) -> dict:
    """解析 HTML 中 21 列线路明细表格。

    第一列「分组」存在 rowspan，仅在分组首行出现；后续同组行省略第一个 <td>，
    需要维护 current_group 状态跨行延续。
    """
    soup = BeautifulSoup(html_content, "html.parser")
    report_date = _extract_date(filename, html_content)

    target_table = None
    for section in soup.find_all("div", class_="base_section"):
        h3 = section.find("h3")
        if h3 and h3.get_text(strip=True) == "线路":
            target_table = section.find("table")
            break

    if target_table is None:
        raise ValueError("未找到「线路」明细表格")

    lines: list[dict] = []
    current_group: str | None = None

    for tr in target_table.find_all("tr"):
        classes = tr.get("class") or []
        if "header" in classes and "sub_header" not in classes:
            continue
        tds = tr.find_all("td", recursive=False)
        if not tds:
            continue

        first_td = tds[0]
        if first_td.has_attr("rowspan"):
            current_group = _td_text(first_td)
            cells = tds[1:]
        else:
            cells = tds

        if len(cells) < 19:
            continue

        line = {
            "line_group": current_group,
            "line_no": _to_int(_td_text(cells[0])),
            "province": _td_text(cells[1]),
            "carrier": _td_text(cells[2]),
            "usage": _td_text(cells[3]),
            "bandwidth_mbps": _parse_bandwidth(_td_text(cells[4])),
            "long_distance_no": _td_text(cells[5]),
            "in_peak_mbps": _to_float(_td_text(cells[6])),
            "in_avg_mbps": _to_float(_td_text(cells[7])),
            "in_peak_util_pct": _to_float(_td_text(cells[8])),
            "in_peak_time": _td_text(cells[9]),
            "out_peak_mbps": _to_float(_td_text(cells[10])),
            "out_avg_mbps": _to_float(_td_text(cells[11])),
            "out_peak_util_pct": _to_float(_td_text(cells[12])),
            "out_peak_time": _td_text(cells[13]),
            "latency_avg_ms": _to_float(_td_text(cells[14])),
            "bw_peak_baseline_mbps": _to_float(_td_text(cells[15])),
            "bw_util_threshold_pct": _to_int(_td_text(cells[16])),
            "latency_baseline_ms": _to_float(_td_text(cells[17])),
            "latency_threshold_ms": _to_float(_td_text(cells[18])),
        }
        lines.append(line)

    return {
        "report_date": report_date,
        "source_file": filename,
        "parsed_at": datetime.now().isoformat(),
        "total_lines": len(lines),
        "lines": lines,
    }


def save_bandwidth_data(data: dict) -> dict:
    report_date = data["report_date"]
    save_dir = Path(SHARED_DATA_DIR) / "bandwidth-lines"
    save_dir.mkdir(parents=True, exist_ok=True)

    save_path = save_dir / f"{report_date}.json"
    content = json.dumps(data, ensure_ascii=False, indent=2)
    save_path.write_text(content, encoding="utf-8")

    return {
        "report_date": report_date,
        "saved_path": str(save_path),
        "total_lines": data.get("total_lines", 0),
    }


def save_parsed_data(data: dict) -> dict:
    """保存解析后的数据到共享 volume。

    Returns:
        保存结果，包含 saved_path 和统计信息
    """
    report_date = data["report_date"]
    save_dir = Path(SHARED_DATA_DIR) / "line-status"
    save_dir.mkdir(parents=True, exist_ok=True)

    save_path = save_dir / f"{report_date}.json"
    content = json.dumps(data, ensure_ascii=False, indent=2)
    save_path.write_text(content, encoding="utf-8")

    # 统计
    line_categories = data.get("line_categories", {})
    cat_counts = {cat: len(lines) for cat, lines in line_categories.items()}
    total = sum(cat_counts.values())

    return {
        "report_date": report_date,
        "saved_path": str(save_path),
        "line_categories": cat_counts,
        "total_lines": total,
    }


def get_status() -> dict:
    """返回已上传的文件列表和状态。"""
    status_dir = Path(SHARED_DATA_DIR) / "line-status"
    if not status_dir.exists():
        return {"files": [], "total": 0}

    files = []
    for f in sorted(status_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            cat_counts = {cat: len(lines) for cat, lines in data.get("line_categories", {}).items()}
            files.append({
                "date": f.stem,
                "source_file": data.get("source_file", ""),
                "total_lines": sum(cat_counts.values()),
                "line_categories": cat_counts,
                "parsed_at": data.get("parsed_at", ""),
            })
        except (json.JSONDecodeError, KeyError):
            files.append({"date": f.stem, "error": "解析失败"})

    return {"files": files, "total": len(files)}


def delete_files(dates: list[str]) -> dict:
    """批量删除指定日期的 JSON 文件。

    同时清理 network_ops.db 中对应日期的入库记录（如果数据库可访问）。
    """
    status_dir = Path(SHARED_DATA_DIR) / "line-status"
    bw_dir = Path(SHARED_DATA_DIR) / "bandwidth-lines"
    deleted = []
    not_found = []

    for date_str in dates:
        fp = status_dir / f"{date_str}.json"
        bw_fp = bw_dir / f"{date_str}.json"
        any_deleted = False
        if fp.exists():
            fp.unlink()
            any_deleted = True
        if bw_fp.exists():
            bw_fp.unlink()
            any_deleted = True
        if any_deleted:
            deleted.append(date_str)
        else:
            not_found.append(date_str)

    # 清理 network_ops.db 中对应日期的入库记录
    db_path = Path("/app/backend/.deer-flow/db/network_ops.db")
    if db_path.exists() and dates:
        try:
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            placeholders = ",".join("?" for _ in dates)
            conn.execute(f"DELETE FROM line_status_baseline WHERE report_date IN ({placeholders})", dates)
            conn.execute(f"DELETE FROM line_status_daily WHERE report_date IN ({placeholders})", dates)
            conn.execute(f"DELETE FROM bandwidth_lines WHERE report_date IN ({placeholders})", dates)
            conn.commit()
            conn.close()
        except Exception:
            pass  # 数据库不可用时静默忽略

    return {"deleted": deleted, "not_found": not_found}
