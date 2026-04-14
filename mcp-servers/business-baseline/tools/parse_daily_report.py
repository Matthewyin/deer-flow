import logging
import re
from typing import Optional

from config import get_config
from db.database import get_connection, init_db
from db.models import (
    insert_daily_report,
    insert_metric,
    calculate_and_update_baselines,
    get_latest_report_date,
)

logger = logging.getLogger(__name__)


def _parse_num(s: str) -> Optional[float]:
    if s is None:
        return None
    cleaned = s.replace(",", "").strip()
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _extract_period(text: str) -> tuple[str, str]:
    m = re.search(r"(\d+)月(\d+)日\d+时至(\d+)月(\d+)日\d+时", text)
    if m:
        ms, ds, me, de = m.groups()
        return f"{int(ms)}月{int(ds)}日", f"{int(me)}月{int(de)}日"
    return "", ""


def _extract_report_date(block_text: str) -> Optional[str]:
    period_m = re.search(
        r"(\d{4})年(\d+)月(\d+)日\d+时至\d{4}年(\d+)月(\d+)日\d+时", block_text
    )
    if period_m:
        return f"{period_m.group(1)}-{int(period_m.group(4)):02d}-{int(period_m.group(5)):02d}"
    period_m2 = re.search(r"(\d+)月(\d+)日\d+时至(\d+)月(\d+)日\d+时", block_text)
    if period_m2:
        end_month = int(period_m2.group(3))
        end_day = int(period_m2.group(4))
        year = _infer_year_from_context()
        return f"{year}-{end_month:02d}-{end_day:02d}"
    return None


def _infer_year_from_context() -> int:
    from datetime import datetime

    return datetime.now().year


def _extract_report_time(header_line: str) -> Optional[str]:
    m = re.search(r"(\d{2}:\d{2})", header_line)
    return m.group(1) if m else None


def _parse_block(lines: list[str], report_date: str) -> list[dict]:
    metrics = []
    full_text = "\n".join(lines)

    period_start, period_end = _extract_period(full_text)

    p = re.compile(r"(\d+)、(.+?)[：:]|\n([^d][^\n]*?)[：:]")

    for line in lines:
        line = line.strip()
        if not line or line.startswith("中国体育") or line.startswith("【"):
            continue

        parsed = _parse_numbered_line(line, report_date) or _parse_unnumbered_line(
            line, report_date
        )
        if parsed:
            metrics.extend(parsed)

    return metrics


def _parse_numbered_line(line: str, report_date: str) -> list[dict]:
    m = re.match(r"(\d+)、(.+)", line)
    if not m:
        return []
    num = int(m.group(1))
    content = m.group(2)
    return _dispatch_by_number(num, content, report_date)


def _dispatch_by_number(num: int, content: str, report_date: str) -> list[dict]:
    parsers = {
        1: _parse_terminals,
        2: _parse_lottery_sales,
        3: _parse_sports_football_sales,
        4: _parse_jingcai_sales,
        5: _parse_taopiao_sales,
        6: _parse_lottery_prize,
        7: _parse_sports_football_prize,
        8: _parse_jingcai_prize,
        9: _parse_beidan_prize,
        10: _parse_total_requests,
        11: _parse_lottery_response,
        12: _parse_sports_football_response,
        13: _parse_jingcai_response,
        14: _parse_taopiao_response,
        15: _parse_jikai,
        16: _parse_period_report_response,
        17: _parse_game_period_report_response,
        18: _parse_usap_login,
        19: _parse_info_publish,
        20: _parse_payment_center,
        21: _parse_customer_center,
        22: _parse_order_center,
        23: _parse_marketing_center,
        24: _parse_open_platform,
        25: _parse_sms_service,
        26: _parse_coop_channel,
        27: _parse_cloud_info_publish,
    }
    parser = parsers.get(num)
    return parser(content, report_date) if parser else []


def _mk(
    report_date: str,
    category: str,
    metric_key: str,
    metric_name: str,
    sub_name=None,
    request_count=None,
    tech_failures=None,
    biz_failures=None,
    peak_tps=None,
    avg_response_ms=None,
    max_response_ms=None,
    median_response_ms=None,
    extra_value=None,
    extra_value_2=None,
    unit="",
) -> dict:
    return {
        "report_date": report_date,
        "category": category,
        "metric_key": metric_key,
        "metric_name": metric_name,
        "sub_name": sub_name,
        "request_count": request_count,
        "tech_failures": tech_failures,
        "biz_failures": biz_failures,
        "peak_tps": peak_tps,
        "avg_response_ms": avg_response_ms,
        "max_response_ms": max_response_ms,
        "median_response_ms": median_response_ms,
        "extra_value": extra_value,
        "extra_value_2": extra_value_2,
        "unit": unit,
    }


def _parse_terminals(content: str, rd: str) -> list[dict]:
    m = re.search(r"在线终端数[：:]([0-9,]+)台", content)
    total = _parse_num(m.group(1)) if m else None
    m2 = re.search(r"传统终端([0-9,]+)台", content)
    traditional = _parse_num(m2.group(1)) if m2 else None
    m3 = re.search(r"安卓终端([0-9,]+)台", content)
    android = _parse_num(m3.group(1)) if m3 else None
    m4 = re.search(r"平台售票峰值TPS[：:]([0-9,.]+)笔/秒", content)
    platform_tps = _parse_num(m4.group(1)) if m4 else None
    return [
        _mk(
            rd, "终端", "online_terminals", "在线终端数", request_count=total, unit="台"
        ),
        _mk(
            rd,
            "终端",
            "online_terminals",
            "在线终端数",
            sub_name="传统终端",
            extra_value=traditional,
            unit="台",
        ),
        _mk(
            rd,
            "终端",
            "online_terminals",
            "在线终端数",
            sub_name="安卓终端",
            extra_value=android,
            unit="台",
        ),
        _mk(
            rd,
            "终端",
            "platform_peak_tps",
            "平台售票峰值TPS",
            peak_tps=platform_tps,
            unit="笔/秒",
        ),
    ]


def _parse_sale(content: str, rd: str, mk: str, name: str, category: str) -> list[dict]:
    req = (
        _parse_num(re.search(r"请求[：:]([0-9,]+)次", content).group(1))
        if re.search(r"请求[：:]([0-9,]+)次", content)
        else None
    )
    tf = (
        _parse_num(re.search(r"技术失败([0-9,]+)次", content).group(1))
        if re.search(r"技术失败([0-9,]+)次", content)
        else None
    )
    bf = (
        _parse_num(re.search(r"业务失败([0-9,]+)次", content).group(1))
        if re.search(r"业务失败([0-9,]+)次", content)
        else None
    )
    tps = (
        _parse_num(re.search(r"峰值TPS[：:]([0-9,.]+)笔/秒", content).group(1))
        if re.search(r"峰值TPS[：:]([0-9,.]+)笔/秒", content)
        else None
    )
    return [
        _mk(
            rd,
            category,
            mk,
            name,
            request_count=req,
            tech_failures=tf,
            biz_failures=bf,
            peak_tps=tps,
            unit="次",
        )
    ]


def _parse_lottery_sales(c, rd):
    return _parse_sale(c, rd, "lottery_sales", "乐透售票请求", "售票")


def _parse_sports_football_sales(c, rd):
    return _parse_sale(c, rd, "sports_football_sales", "传足售票请求", "售票")


def _parse_jingcai_sales(c, rd):
    return _parse_sale(c, rd, "jingcai_sales", "竞彩售票请求", "售票")


def _parse_taopiao_sales(c, rd):
    return _parse_sale(c, rd, "taopiao_sales", "套票售票请求", "售票")


def _parse_prize(
    content: str, rd: str, mk: str, name: str, category: str
) -> list[dict]:
    req = (
        _parse_num(re.search(r"请求[：:]([0-9,]+)次", content).group(1))
        if re.search(r"请求[：:]([0-9,]+)次", content)
        else None
    )
    tf = (
        _parse_num(re.search(r"技术失败([0-9,]+)次", content).group(1))
        if re.search(r"技术失败([0-9,]+)次", content)
        else None
    )
    bf = (
        _parse_num(re.search(r"业务失败([0-9,]+)次", content).group(1))
        if re.search(r"业务失败([0-9,]+)次", content)
        else None
    )
    tps = (
        _parse_num(re.search(r"峰值TPS[：:]([0-9,.]+)笔/秒", content).group(1))
        if re.search(r"峰值TPS[：:]([0-9,.]+)笔/秒", content)
        else None
    )
    return [
        _mk(
            rd,
            category,
            mk,
            name,
            request_count=req,
            tech_failures=tf,
            biz_failures=bf,
            peak_tps=tps,
            unit="次",
        )
    ]


def _parse_lottery_prize(c, rd):
    return _parse_prize(c, rd, "lottery_prize", "乐透兑奖请求", "兑奖")


def _parse_sports_football_prize(c, rd):
    return _parse_prize(c, rd, "sports_football_prize", "传足兑奖请求", "兑奖")


def _parse_jingcai_prize(c, rd):
    return _parse_prize(c, rd, "jingcai_prize", "竞彩兑奖请求", "兑奖")


def _parse_beidan_prize(c, rd):
    return _parse_prize(c, rd, "beidan_prize", "北单兑奖请求", "兑奖")


def _parse_total_requests(content: str, rd: str) -> list[dict]:
    req = (
        _parse_num(re.search(r"请求[：:]([0-9,]+)次", content).group(1))
        if re.search(r"请求[：:]([0-9,]+)次", content)
        else None
    )
    return [_mk(rd, "全局", "total_requests", "所有请求", request_count=req, unit="次")]


def _parse_response(
    content: str, rd: str, mk: str, name: str, category: str
) -> list[dict]:
    avg = (
        _parse_num(re.search(r"平均([0-9,.]+)毫秒", content).group(1))
        if re.search(r"平均([0-9,.]+)毫秒", content)
        else None
    )
    mx = (
        _parse_num(re.search(r"最大([0-9,.]+)毫秒", content).group(1))
        if re.search(r"最大([0-9,.]+)毫秒", content)
        else None
    )
    med = (
        _parse_num(re.search(r"中值([0-9,.]+)毫秒", content).group(1))
        if re.search(r"中值([0-9,.]+)毫秒", content)
        else None
    )
    return [
        _mk(
            rd,
            category,
            mk,
            name,
            avg_response_ms=avg,
            max_response_ms=mx,
            median_response_ms=med,
            unit="毫秒",
        )
    ]


def _parse_lottery_response(c, rd):
    return _parse_response(
        c, rd, "lottery_sales_response", "乐透售票请求响应时间", "响应时间"
    )


def _parse_sports_football_response(c, rd):
    return _parse_response(
        c, rd, "sports_football_sales_response", "传足售票请求响应时间", "响应时间"
    )


def _parse_jingcai_response(c, rd):
    return _parse_response(
        c, rd, "jingcai_sales_response", "竞彩售票请求响应时间", "响应时间"
    )


def _parse_taopiao_response(c, rd):
    return _parse_response(
        c, rd, "taopiao_sales_response", "套票售票请求响应时间", "响应时间"
    )


def _parse_jikai(content: str, rd: str) -> list[dict]:
    results = []
    m_all = re.search(r"即开请求数（全部）[：:]([0-9,]+)次", content)
    m_all_fail = re.search(r"即开请求数（全部）.*?请求失败([0-9,]+)次", content)
    m_all_avg = re.search(r"即开请求数（全部）.*?平均([0-9,.]+)毫秒", content)
    m_all_max = re.search(r"即开请求数（全部）.*?最大([0-9,.]+)毫秒", content)
    if m_all:
        results.append(
            _mk(
                rd,
                "即开",
                "jikai_requests",
                "即开请求数",
                sub_name="全部",
                request_count=_parse_num(m_all.group(1)),
                biz_failures=_parse_num(m_all_fail.group(1)) if m_all_fail else 0,
                avg_response_ms=_parse_num(m_all_avg.group(1)) if m_all_avg else None,
                max_response_ms=_parse_num(m_all_max.group(1)) if m_all_max else None,
                unit="次",
            )
        )

    m_prize = re.search(r"即开请求数（兑奖）[：:]([0-9,]+)次", content)
    m_prize_fail = re.search(r"即开请求数（兑奖）.*?请求失败([0-9,]+)次", content)
    m_prize_avg = re.search(r"即开请求数（兑奖）.*?平均([0-9,.]+)毫秒", content)
    m_prize_max = re.search(r"即开请求数（兑奖）.*?最大([0-9,.]+)毫秒", content)
    if m_prize:
        results.append(
            _mk(
                rd,
                "即开",
                "jikai_requests",
                "即开请求数",
                sub_name="兑奖",
                request_count=_parse_num(m_prize.group(1)),
                biz_failures=_parse_num(m_prize_fail.group(1)) if m_prize_fail else 0,
                avg_response_ms=_parse_num(m_prize_avg.group(1))
                if m_prize_avg
                else None,
                max_response_ms=_parse_num(m_prize_max.group(1))
                if m_prize_max
                else None,
                unit="次",
            )
        )
    return results


def _parse_single_response(
    content: str, rd: str, mk: str, name: str, category: str
) -> list[dict]:
    avg = (
        _parse_num(re.search(r"平均([0-9,.]+)毫秒", content).group(1))
        if re.search(r"平均([0-9,.]+)毫秒", content)
        else None
    )
    return [_mk(rd, category, mk, name, avg_response_ms=avg, unit="毫秒")]


def _parse_period_report_response(c, rd):
    return _parse_single_response(
        c, rd, "period_report_response", "查询时段报表接口响应时间", "报表接口"
    )


def _parse_game_period_report_response(c, rd):
    return _parse_single_response(
        c, rd, "game_period_report_response", "查询游戏时段报表接口响应时间", "报表接口"
    )


def _parse_usap_login(content: str, rd: str) -> list[dict]:
    success = (
        _parse_num(re.search(r"成功数[：:]([0-9,]+)次", content).group(1))
        if re.search(r"成功数[：:]([0-9,]+)次", content)
        else None
    )
    fail = (
        _parse_num(re.search(r"失败数[：:]([0-9,]+)次", content).group(1))
        if re.search(r"失败数[：:]([0-9,]+)次", content)
        else None
    )
    return [
        _mk(
            rd,
            "USAP",
            "usap_login",
            "USAP登陆",
            request_count=success,
            biz_failures=fail,
            unit="次",
        )
    ]


def _parse_center(
    content: str, rd: str, mk: str, name: str, category: str
) -> list[dict]:
    req = (
        _parse_num(re.search(r"请求数[：:]([0-9,]+)次", content).group(1))
        if re.search(r"请求数[：:]([0-9,]+)次", content)
        else None
    )
    avg = (
        _parse_num(re.search(r"平均([0-9,.]+)毫秒", content).group(1))
        if re.search(r"平均([0-9,.]+)毫秒", content)
        else None
    )
    mx = (
        _parse_num(re.search(r"最大([0-9,.]+)毫秒", content).group(1))
        if re.search(r"最大([0-9,.]+)毫秒", content)
        else None
    )
    med = (
        _parse_num(re.search(r"中值([0-9,.]+)毫秒", content).group(1))
        if re.search(r"中值([0-9,.]+)毫秒", content)
        else None
    )
    return [
        _mk(
            rd,
            category,
            mk,
            name,
            request_count=req,
            avg_response_ms=avg,
            max_response_ms=mx,
            median_response_ms=med,
            unit="次",
        )
    ]


def _parse_info_publish(c, rd):
    return _parse_center(
        c, rd, "info_publish_center", "信息发布中心-标准数据发布接口", "各中心"
    )


def _parse_payment_center(c, rd):
    return _parse_center(c, rd, "payment_center", "支付中心", "各中心")


def _parse_customer_center(c, rd):
    return _parse_center(c, rd, "customer_center", "客户中心", "各中心")


def _parse_order_center(c, rd):
    return _parse_center(c, rd, "order_center", "订单中心", "各中心")


def _parse_open_platform(c, rd):
    return _parse_center(c, rd, "open_platform", "开放平台", "各中心")


def _parse_sms_service(c, rd):
    return _parse_center(c, rd, "sms_service", "短信公共服务", "各中心")


def _parse_coop_channel(c, rd):
    return _parse_center(c, rd, "coop_channel", "合作渠道商户系统", "各中心")


def _parse_cloud_info_publish(c, rd):
    return _parse_center(c, rd, "cloud_info_publish", "信息发布系统云上", "各中心")


def _parse_marketing_center(content: str, rd: str) -> list[dict]:
    results = []

    m_all = re.search(r"营销中心-请求数（所有请求）[：:]([0-9,]+)次", content)
    if m_all:
        avg = (
            _parse_num(re.search(r"平均([0-9,.]+)毫秒", content).group(1))
            if re.search(r"平均([0-9,.]+)毫秒", content)
            else None
        )
        mx = (
            _parse_num(re.search(r"最大([0-9,.]+)毫秒", content).group(1))
            if re.search(r"最大([0-9,.]+)毫秒", content)
            else None
        )
        med = (
            _parse_num(re.search(r"中值([0-9,.]+)毫秒", content).group(1))
            if re.search(r"中值([0-9,.]+)毫秒", content)
            else None
        )
        results.append(
            _mk(
                rd,
                "各中心",
                "marketing_center",
                "营销中心",
                sub_name="所有请求",
                request_count=_parse_num(m_all.group(1)),
                avg_response_ms=avg,
                max_response_ms=mx,
                median_response_ms=med,
                unit="次",
            )
        )

    m_mkc_all = re.search(r"营销中心-请求数（MKC抽奖-全部）[：:]([0-9,]+)次", content)
    if m_mkc_all:
        avg = (
            _parse_num(
                re.search(r"MKC抽奖-全部.*?平均([0-9,.]+)毫秒", content).group(1)
            )
            if re.search(r"MKC抽奖-全部.*?平均([0-9,.]+)毫秒", content)
            else None
        )
        mx = (
            _parse_num(
                re.search(r"MKC抽奖-全部.*?最大([0-9,.]+)毫秒", content).group(1)
            )
            if re.search(r"MKC抽奖-全部.*?最大([0-9,.]+)毫秒", content)
            else None
        )
        med = (
            _parse_num(
                re.search(r"MKC抽奖-全部.*?中值([0-9,.]+)毫秒", content).group(1)
            )
            if re.search(r"MKC抽奖-全部.*?中值([0-9,.]+)毫秒", content)
            else None
        )
        results.append(
            _mk(
                rd,
                "各中心",
                "marketing_center",
                "营销中心",
                sub_name="MKC抽奖-全部",
                request_count=_parse_num(m_mkc_all.group(1)),
                avg_response_ms=avg,
                max_response_ms=mx,
                median_response_ms=med,
                unit="次",
            )
        )

    m_mkc_gate = re.search(
        r"营销中心-请求数（MKC抽奖-过门槛）[：:]([0-9,]+)次", content
    )
    if m_mkc_gate:
        avg = (
            _parse_num(
                re.search(r"MKC抽奖-过门槛.*?平均([0-9,.]+)毫秒", content).group(1)
            )
            if re.search(r"MKC抽奖-过门槛.*?平均([0-9,.]+)毫秒", content)
            else None
        )
        mx = (
            _parse_num(
                re.search(r"MKC抽奖-过门槛.*?最大([0-9,.]+)毫秒", content).group(1)
            )
            if re.search(r"MKC抽奖-过门槛.*?最大([0-9,.]+)毫秒", content)
            else None
        )
        med = (
            _parse_num(
                re.search(r"MKC抽奖-过门槛.*?中值([0-9,.]+)毫秒", content).group(1)
            )
            if re.search(r"MKC抽奖-过门槛.*?中值([0-9,.]+)毫秒", content)
            else None
        )
        results.append(
            _mk(
                rd,
                "各中心",
                "marketing_center",
                "营销中心",
                sub_name="MKC抽奖-过门槛",
                request_count=_parse_num(m_mkc_gate.group(1)),
                avg_response_ms=avg,
                max_response_ms=mx,
                median_response_ms=med,
                unit="次",
            )
        )

    return results


def _parse_unnumbered_line(line: str, rd: str) -> list[dict]:
    if line.startswith("套餐票售票请求"):
        return _parse_sale(line, rd, "taocan_sales", "套餐票售票请求", "售票")
    if line.startswith("套餐票售票请求响应时间"):
        return _parse_response(
            line, rd, "taocan_sales_response", "套餐票售票请求响应时间", "响应时间"
        )
    if line.startswith("即开请求数"):
        return _parse_jikai(line, rd)
    if line.startswith("营销中心"):
        return _parse_marketing_center(line, rd)
    return []


def parse_daily_report_impl() -> dict:
    cfg = get_config()
    init_db(cfg.sqlite.db_path)
    conn = get_connection(cfg.sqlite.db_path)

    try:
        with open(cfg.file.everybusiness_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
    except OSError as e:
        conn.close()
        return {"error": f"Failed to read file: {e}", "parsed": 0}

    blocks = raw_text.split("XXX技术服务台")
    blocks = [b.strip() for b in blocks if b.strip()]

    total_reports = 0
    total_metrics = 0
    skipped = 0

    for block in blocks:
        lines = block.strip().split("\n")
        if not lines:
            continue

        header_line = lines[0].strip()
        report_date = _extract_report_date(block)
        report_time = _extract_report_time(header_line)

        if not report_date:
            skipped += 1
            continue

        existing = conn.execute(
            "SELECT 1 FROM daily_reports WHERE report_date = ?", (report_date,)
        ).fetchone()
        if existing:
            continue

        period_start, period_end = _extract_period(block)

        insert_daily_report(
            conn, report_date, report_time or "", period_start, period_end, block
        )
        total_reports += 1

        metrics = _parse_block(lines, report_date)
        for m in metrics:
            insert_metric(conn, m)
        total_metrics += len(metrics)

    baseline_result = calculate_and_update_baselines(conn)

    conn.close()
    return {
        "parsed_reports": total_reports,
        "parsed_metrics": total_metrics,
        "skipped_blocks": skipped,
        "baseline_update": baseline_result,
    }


def register(mcp):
    @mcp.tool()
    def parse_daily_report() -> dict:
        """解析 everybusiness 文件中的每日运营数据，提取27项指标入库，
        并自动计算全历史基线。跳过已解析的日期（按 report_date 去重）。

        Returns:
            dict: 解析统计 {parsed_reports, parsed_metrics, skipped_blocks, baseline_update}
        """
        return parse_daily_report_impl()
