import hashlib
import re
from datetime import datetime
from typing import Any


METRIC_KEY_MAP = {
    "平台TPS": "platform_tps",
    "竞彩TPS": "jingcai_tps",
    "传足TPS": "chuanzu_tps",
    "北单TPS": "beidan_tps",
    "超额申请": "over_quota_apply",
    "高额预约": "high_value_reservation",
    "大额预约": "large_value_reservation",
    "竞彩票数": "jingcai_ticket_count",
    "竞彩销量": "jingcai_sales",
    "传足票数": "chuanzu_ticket_count",
    "传足票数万": "chuanzu_ticket_count_wan",
    "传足销量": "chuanzu_sales",
    "传足销量万": "chuanzu_sales_wan",
    "北单票数": "beidan_ticket_count",
    "北单销量": "beidan_sales",
    "体彩APP注册用户": "app_registered_users",
    "体彩APP今日注册用户": "app_registered_users",
    "小程序注册用户": "miniapp_registered_users",
    "小程序今日注册用户": "miniapp_registered_users",
    "竞彩网（包含M站）访问次数": "jingcai_web_visits",
    "竞彩网（包含M站）访问人数": "jingcai_web_users",
    "体彩APP安卓页面访问次数": "app_android_page_views",
    "ios页面访问次数": "ios_page_views",
}


def file_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_date(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return text


def normalize_number(value: Any) -> tuple[float | None, str | None]:
    if value is None:
        return 0.0, "0"
    if isinstance(value, bool):
        return float(value), str(value)
    if isinstance(value, (int, float)):
        return float(value), str(value)

    text = str(value).strip()
    if text == "":
        return 0.0, "0"
    cleaned = text.replace(",", "").replace("，", "")
    if cleaned.endswith("%"):
        try:
            return float(cleaned[:-1]), text
        except ValueError:
            return None, text
    try:
        return float(cleaned), text
    except ValueError:
        return None, text


def infer_value_role(header: str) -> str:
    if "同比" in header or "环比" in header:
        return "compare_pct"
    if "昨日" in header:
        return "yesterday"
    if "今日" in header:
        return "today"
    return "current"


def normalize_metric_name(header: str) -> str:
    text = str(header or "").strip()
    text = text.replace("（昨日）", "").replace("（今日）", "")
    text = text.replace("(昨日)", "").replace("(今日)", "")
    text = text.replace("同比昨日", "")
    text = text.replace(" 环比", "环比").replace("环比", "")
    text = text.replace("今日", "")
    return text.strip()


def metric_key(metric_name: str) -> str:
    if metric_name in METRIC_KEY_MAP:
        return METRIC_KEY_MAP[metric_name]
    digest = hashlib.sha1(metric_name.encode("utf-8")).hexdigest()[:10]
    return f"metric_{digest}"


def infer_unit(metric_name: str, value_role: str) -> str:
    if value_role == "compare_pct":
        return "%"
    if "TPS" in metric_name:
        return "TPS"
    if "销量万" in metric_name or "票数万" in metric_name:
        return "万"
    if "销量" in metric_name:
        return ""
    if "票数" in metric_name:
        return "票"
    if "用户" in metric_name or "人数" in metric_name:
        return "人"
    if "访问次数" in metric_name:
        return "次"
    return ""


def sheet_slug(sheet_name: str) -> str:
    if "每小时数据" in sheet_name:
        return "tps_wushu_hourly"
    if "日统计数据" in sheet_name:
        return "tps_wushu_daily"
    if "周统计数据" in sheet_name:
        return "tps_wushu_weekly"
    if "两网三端时段(日统计" in sheet_name:
        return "channels_daily"
    if "两网三端时段" in sheet_name:
        return "channels_hourly"
    digest = hashlib.sha1(sheet_name.encode("utf-8")).hexdigest()[:8]
    return f"sheet_{digest}"
