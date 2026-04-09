"""Email template generation tool.

Reads templates from bandwidth.md (the single source of truth), fills in
known fields from line_info and assessment, keeps placeholders for
monitoring / activity / alert data, converts tab-separated tables to
Markdown, and writes the result to a .md file.
"""

import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP

from config import get_config

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# ---------------------------------------------------------------------------
# Template parsing from bandwidth.md
# ---------------------------------------------------------------------------

_TEMPLATE_NAMES = {
    "normal": "模板一",
    "temporary": "模板二",
    "emergency": "模板三",
    "scale_down": "模板四",
}


def _load_templates() -> dict[str, str]:
    """Parse the four email templates from bandwidth.md.

    Returns a dict mapping template key -> raw template text.
    """
    config = get_config()
    md_path = Path(config.chroma.md_path)
    if not md_path.is_absolute():
        md_path = _PROJECT_ROOT / md_path

    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    parts = re.split(r"^-{5,}\s*$", content, flags=re.MULTILINE)
    if len(parts) < 2:
        raise ValueError(
            "bandwidth.md does not contain a '----------' separator before templates"
        )

    template_section = parts[-1]

    result = {}
    for key, marker in _TEMPLATE_NAMES.items():
        # Match from the marker line to the next marker or end-of-string
        pattern = rf"^{re.escape(marker)}[^\n]*\n(.*?)(?=^模板[一二三四][：:]|\Z)"
        m = re.search(pattern, template_section, re.MULTILINE | re.DOTALL)
        if m:
            result[key] = m.group(1).rstrip()
        else:
            logger.warning(f"Template '{marker}' not found in bandwidth.md")

    return result


_templates: Optional[dict[str, str]] = None


def _get_templates() -> dict[str, str]:
    global _templates
    if _templates is None:
        _templates = _load_templates()
    return _templates


# ---------------------------------------------------------------------------
# Tab-separated table -> Markdown table converter
# ---------------------------------------------------------------------------


def _tsv_to_markdown_tables(text: str) -> str:
    """Convert all tab-separated table blocks in *text* to Markdown tables.

    A TSV block is detected when two or more consecutive lines each contain
    at least one tab character.  Header rows are detected heuristically
    (no numeric-only cells) and a separator row is inserted.
    """

    lines = text.split("\n")
    result: list[str] = []
    block: list[str] = []

    def flush_block():
        if len(block) < 2:
            result.extend(block)
            return

        header = [c.strip() for c in block[0].split("\t")]
        data_rows = []
        for row_line in block[1:]:
            cells = [c.strip() for c in row_line.split("\t")]
            while len(cells) < len(header):
                cells.append("")
            cells = cells[: len(header)]
            data_rows.append(cells)

        result.append("| " + " | ".join(header) + " |")
        result.append("| " + " | ".join(":---" for _ in header) + " |")
        for row in data_rows:
            result.append("| " + " | ".join(row) + " |")

    # Lines that start with bullet characters (●, ○, -, *, •) are NOT table rows
    _BULLET_RE = re.compile(r"^[●○•\-\*]\s")

    for line in lines:
        if "\t" in line and not _BULLET_RE.match(line.strip()):
            block.append(line)
        else:
            flush_block()
            block = []
            result.append(line)

    flush_block()
    return "\n".join(result)


# ---------------------------------------------------------------------------
# Field filling
# ---------------------------------------------------------------------------


def _today() -> str:
    return datetime.now().strftime("%Y%m%d")


def _effective_date() -> str:
    return (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d")


def _parse_bw(bw_str: str) -> str:
    """Extract numeric part from bandwidth string, e.g. '20 Mbps' -> '20'."""
    nums = re.findall(r"\d+", str(bw_str))
    return nums[0] if nums else str(bw_str)


def _fill_tsv_row(row: str, cells: list[str]) -> str:
    """Replace cells in a tab-separated data row.

    *cells* is a list of values; each value replaces the corresponding
    tab-separated cell.  ``None`` means "keep the original placeholder".
    """
    original = row.split("\t")
    for i, val in enumerate(cells):
        if val is not None and i < len(original):
            original[i] = val
    return "\t".join(original)


def _fill_fields(
    template: str,
    template_type: str,
    line_info: dict,
    assessment: dict,
) -> str:
    """Fill the template with data from line_info and assessment.

    Uses a two-phase approach:
    1. Simple string replacements for scalar placeholders (date, carrier, etc.)
    2. Cell-by-cell TSV row replacement for table data rows, because
       numeric placeholders like [10], [20] are ambiguous across templates.
    """
    site = f"{line_info.get('local_site', '?')}-{line_info.get('remote_name', '?')}"
    purpose = line_info.get("purpose", "[专线用途]")
    carrier = line_info.get("carrier", "[运营商]")
    cur_bw = line_info.get("bandwidth", "?")
    target_bw = assessment.get("target_bw", "?")
    cur_bw_num = _parse_bw(cur_bw)
    target_bw_num = _parse_bw(target_bw)

    # Phase 1: scalar replacements
    scalar_map = {
        "[申请日期YYYYMMDD]": _today(),
        "[申请日期]": _today(),
        "[申请时间]": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "[专线名称]": site,
        "[专线号]": line_info.get("local_line_number", "[专线号]"),
        "[示例：本端数据中心-对端单位]": site,
        "[示例：亦庄-腾讯公有云专线]": site,
        "[示例：省中心管理端]": purpose,
        "[专线用途（业务）]": purpose,
        "[两网三端]": purpose,
        "[TLS售票业务]": purpose,
        "[VPDN售票]": purpose,
        "[电信]": carrier,
        "[运营商]": carrier,
        "[YYYY-MM-DD]": _effective_date(),
    }
    for placeholder, value in scalar_map.items():
        template = template.replace(placeholder, value)

    # Phase 2: TSV data-row replacement (cell-by-cell)
    lines = template.split("\n")
    header_col_count = 0
    new_lines = []
    for line in lines:
        if "\t" not in line:
            new_lines.append(line)
            continue

        cells = line.split("\t")

        # Detect header row (first TSV line, no bracket placeholders)
        if header_col_count == 0 and not any(re.search(r"\[.*?\]", c) for c in cells):
            header_col_count = len(cells)
            new_lines.append(line)
            continue

        # Only process data rows that match the header column count
        has_brackets = any(re.search(r"\[.*?\]", c) for c in cells)
        if has_brackets and len(cells) >= 5:
            filled = _fill_data_row(
                cells,
                template_type,
                line_info,
                assessment,
                cur_bw_num,
                target_bw_num,
                purpose,
                carrier,
                site,
            )
            new_lines.append(filled)
        else:
            new_lines.append(line)

    return "\n".join(new_lines)


def _fill_data_row(
    cells: list[str],
    template_type: str,
    line_info: dict,
    assessment: dict,
    cur_bw_num: str,
    target_bw_num: str,
    purpose: str,
    carrier: str,
    site: str,
) -> str:
    """Fill a single TSV data row based on template type and header context."""

    if template_type == "normal":
        # Header: 专线号 专线名称 专线用途 运营商 现有带宽 申请带宽 当前P95利用率 当前P95流量 调整生效日期
        replacements = {
            0: line_info.get("local_line_number", cells[0]),
            1: site,
            2: purpose,
            3: carrier,
            4: f"{cur_bw_num} Mbps",
            5: f"{target_bw_num} Mbps",
            # 6, 7, 8: keep monitoring placeholders
        }
    elif template_type == "temporary":
        # Header: 专线号 专线名称 专线用途 运营商 现有带宽 申请带宽 预计流量 生效时间 恢复时间
        replacements = {
            0: line_info.get("local_line_number", cells[0]),
            1: site,
            2: purpose,
            3: carrier,
            4: f"{cur_bw_num} Mbps",
            5: f"{target_bw_num} Mbps",
            # 6, 7, 8: keep placeholders (预计流量, 生效时间, 恢复时间)
        }
    elif template_type == "emergency":
        # Header: 专线号 专线名称 专线用途 运营商 现有带宽 申请带宽 当前实时利用率 网络质量状况 要求生效时间
        replacements = {
            0: line_info.get("local_line_number", cells[0]),
            1: site,
            2: purpose,
            3: carrier,
            4: f"{cur_bw_num} Mbps",
            5: f"{target_bw_num} Mbps",
            # 6, 7, 8: keep alert placeholders
        }
    elif template_type == "scale_down":
        # Header: 专线号 专线名称 专线用途 运营商 现有带宽 申请带宽 缩容阈值标准 当前P95利用率 当前P95流量 调整生效日期
        replacements = {
            0: line_info.get("local_line_number", cells[0]),
            1: site,
            2: purpose,
            3: carrier,
            4: f"{cur_bw_num} Mbps",
            5: f"{target_bw_num} Mbps",
            # 6-9: keep monitoring/threshold placeholders
        }
    else:
        replacements = {}

    for idx, val in replacements.items():
        if idx < len(cells):
            cells[idx] = val

    return "\t".join(cells)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _output_dir() -> Path:
    """Return the directory where generated emails are saved."""
    d = _PROJECT_ROOT / ".deer-flow" / "emails"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# MCP registration
# ---------------------------------------------------------------------------


def register(mcp: FastMCP):

    @mcp.tool()
    def email_generate(
        action: str,
        line_info: dict,
        assessment: dict,
        template_type: str = "normal",
    ) -> dict:
        """根据带宽评估结果，从 bandwidth.md 模板生成邮件 Markdown 文件。

        Args:
            action: 评估动作，"scale_up" 或 "scale_down"
            line_info: 线路信息字典，包含 local_site, remote_name, local_line_number, bandwidth, carrier, purpose 等
            assessment: 带宽评估结果字典，来自 bandwidth_assess 工具，包含 action, target_bw, reasoning 等
            template_type: 模板类型。"normal"=常态化扩容, "temporary"=临时扩容, "emergency"=应急扩容, "scale_down"=缩容

        Returns:
            dict: 包含 file_path（生成的 .md 文件路径）、subject、recipients、cc、template_type
        """
        logger.info(f"Generating email for action={action}, type={template_type}")

        if action == "scale_down":
            key = "scale_down"
        elif action == "scale_up":
            if template_type in ("temporary", "emergency"):
                key = template_type
            else:
                key = "normal"
        else:
            return {"message": f"action={action} 不需要生成邮件"}

        templates = _get_templates()
        if key not in templates:
            return {
                "error": f"模板 '{_TEMPLATE_NAMES.get(key, key)}' 在 bandwidth.md 中未找到"
            }

        raw_template = templates[key]
        filled = _fill_fields(raw_template, key, line_info, assessment)
        markdown_content = _tsv_to_markdown_tables(filled)
        subject_match = re.search(r"邮件主题[：:]\s*(.+)", markdown_content)
        subject = subject_match.group(1).strip() if subject_match else "带宽扩缩容申请"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"email_{key}_{timestamp}.md"
        file_path = _output_dir() / filename

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        logger.info(f"Email draft saved to {file_path}")

        return {
            "file_path": str(file_path),
            "subject": subject,
            "recipients": ["李王昊"],
            "cc": [
                "潘处",
                "毅总",
                "许祎恒",
                "霍乾",
                "黄美华",
                "王亮",
                "一线",
                "二线",
                "值班经理",
                "商务",
            ],
            "template_type": key,
            "message": f"邮件草稿已生成：{filename}。请检查并手动补充占位符字段后发送。",
        }
