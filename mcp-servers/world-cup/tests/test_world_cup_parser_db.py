import sys
import zipfile
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.db import (  # noqa: E402
    beijing_now,
    clear_all_data,
    delete_upload,
    get_upload_by_hash,
    import_parsed_data,
    query_records,
    report,
    status,
    summary,
)
from core.normalizer import file_sha256, normalize_date, normalize_number  # noqa: E402
from core.parser import parse_workbook  # noqa: E402
from core.transformer import normalize_workbook_for_import  # noqa: E402


def test_beijing_now_uses_china_timezone():
    assert beijing_now().utcoffset().total_seconds() == 8 * 60 * 60


def _build_workbook(path: Path) -> None:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    ws = wb.create_sheet("每小时数据—TPS、五书")
    ws["A1"] = "日期"
    ws["B1"] = "时段"
    ws["C1"] = "平台TPS"
    ws["D1"] = "平台TPS"
    ws["E1"] = "平台TPS"
    ws["A2"] = "日期"
    ws["B2"] = "时段"
    ws["C2"] = "平台TPS（昨日）"
    ws["D2"] = "平台TPS（今日）"
    ws["E2"] = "平台TPS环比"
    ws.append(["2026年6月1日", "19:00-20:00", 100, 200, "100%"])

    ws = wb.create_sheet("日统计数据—TPS、五书")
    ws.append(["日期", "平台TPS", "平台TPS环比"])
    ws.append(["2026年6月1日", "1,234", "7.56%"])

    ws = wb.create_sheet("周统计数据—TPS、五书")
    ws.append(["周", "平台TPS", "平台TPS环比"])
    ws.append(["2026年第23周", 4321, -0.1])

    ws = wb.create_sheet("两网三端时段")
    ws.append(["日期", "时段", "体彩APP今日注册用户", "竞彩网（包含M站）访问次数同比昨日"])
    ws.append(["2026年6月1日", "20:00-21:00", "2,000", 0.0756])

    ws = wb.create_sheet("两网三端时段(日统计）")
    ws.append(["日期", "体彩APP注册用户", "竞彩网（包含M站）访问次数同比昨日"])
    ws.append(["2026年6月1日", "", "8.88%"])

    wb.save(path)


def _build_two_sheet_workbook(path: Path) -> None:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    ws = wb.create_sheet("每小时数据—TPS、五书")
    ws["A1"] = "日期"
    ws["B1"] = "时段"
    ws["C1"] = "平台TPS"
    ws["D1"] = "平台TPS"
    ws["A2"] = "日期"
    ws["B2"] = "时间"
    ws["C2"] = "平台TPS（昨日）"
    ws["D2"] = "平台TPS（今日）"
    ws.append(["2026年6月1日", "0:00-1:00", "", 23])

    ws = wb.create_sheet("两网三端时段")
    ws.append(["日期", "时间", "体彩APP今日注册用户", "竞彩网（包含M站）访问次数同比昨日"])
    ws.append(["2026年6月1日", "0:00-1:00", "4,350", ""])

    wb.save(path)


def _build_flat_hourly_header_workbook(path: Path) -> None:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    ws = wb.create_sheet("每小时数据—TPS、五书")
    ws.append([
        "日期",
        "时间",
        "平台TPS",
        "竞彩TPS",
        "传足票数",
        "传足销量",
    ])
    ws.append(["2026年5月31日", "0:00-1:00", 23, "", 2680, 75])

    ws = wb.create_sheet("两网三端时段")
    ws.append(["日期", "时间", "体彩APP今日注册用户"])
    ws.append(["2026年6月1日", "0:00-1:00", "4,350"])

    wb.save(path)


def _build_old_hourly_header_workbook(path: Path) -> None:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    ws = wb.create_sheet("每小时数据—TPS、五书")
    ws.append([
        None,
        None,
        "平台TPS",
        None,
        "竞彩TPS",
        None,
        "传足TPS",
        None,
        "北单TPS",
        None,
        "五书",
        None,
        None,
        None,
        None,
        None,
        "竞彩票数销量",
        None,
        None,
        None,
        "传足票数销量",
        None,
        None,
        None,
        "北单票数销量",
    ])
    ws.append([
        "日期",
        "时间",
        "平台TPS（昨日）",
        "平台TPS（今日）",
        "竞彩TPS（昨日）",
        "竞彩TPS（今日）",
        "传足TPS（昨日）",
        "传足TPS（今日）",
        "北单TPS（昨日）",
        "北单TPS（今日）",
        "超额申请（昨日）",
        "超额申请（今日）",
        "高额预约（昨日）",
        "高额预约（今日）",
        "大额预约（昨日）",
        "大额预约（今日）",
        "竞彩票数（昨日）",
        "竞彩票数（今日）",
        "竞彩销量（昨日）",
        "竞彩销量（今日）",
        "传足票数（昨日）",
        "传足票数（今日）",
        "传足销量（昨日）",
        "传足销量（今日）",
        "北单票数（昨日）",
        "北单票数（今日）",
        "北单销量（昨日）",
        "北单销量（今日）",
        "平台TPS环比",
        "竞彩TPS环比",
        "传足TPS环比",
    ])
    ws.append([
        "2026年6月1日",
        "0:00-1:00",
        10,
        20,
        30,
        "",
        40,
        50,
        60,
        70,
        1,
        2,
        3,
        4,
        5,
        6,
        100,
        200,
        300,
        400,
        500,
        600,
        700,
        800,
        900,
        1000,
        1100,
        1200,
        "100%",
        "计算错误",
        "25%",
    ])

    ws = wb.create_sheet("两网三端时段")
    ws.append(["日期", "时间", "体彩APP今日注册用户", "竞彩网（包含M站）访问次数同比昨日"])
    ws.append(["2026年6月1日", "0:00-1:00", "4,350", ""])

    wb.save(path)


def _corrupt_sheet_dimensions(path: Path) -> None:
    original = path.read_bytes()
    entries: dict[str, bytes] = {}
    with zipfile.ZipFile(path, "r") as zin:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename.startswith("xl/worksheets/sheet"):
                data = data.replace(b'<dimension ref="A1:AE3"/>', b'<dimension ref="A1"/>')
                data = data.replace(b'<dimension ref="A1:D2"/>', b'<dimension ref="A1"/>')
            entries[info.filename] = data
    if not entries:
        path.write_bytes(original)
        return
    with zipfile.ZipFile(path, "w") as zout:
        for name, data in entries.items():
            zout.writestr(name, data)


def test_normalizers_cover_common_excel_values():
    assert normalize_date("2026年6月1日") == "2026-06-01"
    assert normalize_number("1,234.5") == (1234.5, "1,234.5")
    assert normalize_number("7.56%") == (7.56, "7.56%")
    assert normalize_number("") == (0.0, "0")


def test_parser_covers_expected_five_sheets(tmp_path):
    workbook = tmp_path / "world-cup.xlsx"
    _build_workbook(workbook)

    parsed = parse_workbook(workbook, "upload_1", workbook.name)

    assert parsed["sheet_count"] == 5
    assert parsed["record_count"] > 0
    assert parsed["errors"] == []
    assert {r["sheet_name"] for r in parsed["records"]} == {
        "每小时数据—TPS、五书",
        "日统计数据—TPS、五书",
        "周统计数据—TPS、五书",
        "两网三端时段",
        "两网三端时段(日统计）",
    }
    compare = [
        r
        for r in parsed["records"]
        if r["metric_name"] == "竞彩网（包含M站）访问次数" and r["value_role"] == "compare_pct"
    ]
    assert compare
    assert any(r["value_numeric"] == pytest.approx(7.56) for r in compare)
    empty_records = [
        r
        for r in parsed["records"]
        if r["sheet_name"] == "两网三端时段(日统计）" and r["metric_name"] == "体彩APP注册用户"
    ]
    assert empty_records
    assert empty_records[0]["value_numeric"] == 0
    assert empty_records[0]["value_text"] == "0"


def test_parser_accepts_current_two_sheet_workbook_and_zero_fills_empty_cells(tmp_path):
    workbook = tmp_path / "world-cup-two-sheets.xlsx"
    _build_two_sheet_workbook(workbook)

    parsed = parse_workbook(workbook, "upload_1", workbook.name)

    assert parsed["sheet_count"] == 2
    assert parsed["errors"] == []
    assert {r["sheet_name"] for r in parsed["records"]} == {
        "每小时数据—TPS、五书",
        "两网三端时段",
    }
    yesterday_tps = [
        r
        for r in parsed["records"]
        if r["metric_key"] == "platform_tps" and r["value_role"] == "yesterday"
    ]
    assert yesterday_tps
    assert yesterday_tps[0]["value_numeric"] == 0
    assert yesterday_tps[0]["value_text"] == "0"


def test_parser_accepts_flat_hourly_header_workbook(tmp_path):
    workbook = tmp_path / "world-cup-flat-hourly.xlsx"
    _build_flat_hourly_header_workbook(workbook)

    parsed = parse_workbook(workbook, "upload_1", workbook.name)

    assert parsed["errors"] == []
    assert parsed["sheet_count"] == 2
    hourly = [r for r in parsed["records"] if r["sheet_name"] == "每小时数据—TPS、五书"]
    assert {r["metric_key"] for r in hourly} == {
        "platform_tps",
        "jingcai_tps",
        "chuanzu_ticket_count",
        "chuanzu_sales",
    }
    jingcai = [r for r in hourly if r["metric_key"] == "jingcai_tps"]
    assert jingcai[0]["value_numeric"] == 0


def test_normalizer_converts_old_hourly_workbook_to_current_import_shape(tmp_path):
    old_workbook = tmp_path / "world-cup-old.xlsx"
    normalized_workbook = tmp_path / "world-cup-normalized.xlsx"
    _build_old_hourly_header_workbook(old_workbook)
    _corrupt_sheet_dimensions(old_workbook)

    result = normalize_workbook_for_import(old_workbook, normalized_workbook)
    parsed = parse_workbook(normalized_workbook, "upload_1", normalized_workbook.name)

    assert result["normalized"] is True
    assert parsed["errors"] == []
    assert parsed["record_count"] == 15
    hourly = [r for r in parsed["records"] if r["sheet_name"] == "每小时数据—TPS、五书"]
    assert {r["value_role"] for r in hourly} == {"current"}
    values = {r["metric_key"]: r["value_numeric"] for r in hourly}
    assert values == {
        "platform_tps": 20,
        "jingcai_tps": 0,
        "chuanzu_tps": 50,
        "beidan_tps": 70,
        "over_quota_apply": 2,
        "high_value_reservation": 4,
        "large_value_reservation": 6,
        "jingcai_ticket_count": 200,
        "jingcai_sales": 400,
        "chuanzu_ticket_count": 600,
        "chuanzu_sales": 800,
        "beidan_ticket_count": 1000,
        "beidan_sales": 1200,
    }


def test_db_import_query_summary_report_and_delete(tmp_path):
    workbook = tmp_path / "world-cup.xlsx"
    db_path = tmp_path / "world_cup.db"
    _build_workbook(workbook)

    content = workbook.read_bytes()
    parsed = parse_workbook(workbook, "upload_1", workbook.name)
    imported = import_parsed_data(
        str(db_path),
        parsed,
        source_filename=workbook.name,
        file_hash=file_sha256(content),
        raw_file_path=str(workbook),
        parsed_json_path=str(tmp_path / "parsed.json"),
    )

    assert imported["sheet_count"] == 5
    assert imported["uploaded_at"].endswith("+08:00")
    assert status(str(db_path))["metric_count"] == parsed["record_count"]
    assert get_upload_by_hash(str(db_path), file_sha256(content))["upload_id"] == "upload_1"
    cleared = clear_all_data(str(db_path))
    assert cleared["cleared_uploads"] == 1
    assert cleared["cleared_metrics"] == parsed["record_count"]
    assert status(str(db_path))["metric_count"] == 0

    import_parsed_data(
        str(db_path),
        parsed,
        source_filename=workbook.name,
        file_hash=file_sha256(content),
        raw_file_path=str(workbook),
        parsed_json_path=str(tmp_path / "parsed.json"),
    )

    records = query_records(
        str(db_path),
        date="2026-06-01",
        metric_key="platform_tps",
        granularity="hourly",
    )
    assert records["total_matched"] == 3

    data = summary(
        str(db_path),
        date="2026-06-01",
        metric_key="platform_tps",
        granularity="hourly",
        top_n=1,
    )
    assert data["peak_metrics"][0]["value_numeric"] == 200
    all_data = summary(str(db_path), date="2026-06-01")
    assert all_data["empty_value_count"] == 0
    assert all_data["missing_count"] == 0
    markdown = report(str(db_path), date="2026-06-01")["markdown"]
    assert "世界杯保障数据日报" in markdown
    assert "空值项：0" in markdown
    assert "缺失项" not in markdown

    deleted = delete_upload(str(db_path), "upload_1")
    assert deleted["deleted"] is True
    assert status(str(db_path))["metric_count"] == 0
