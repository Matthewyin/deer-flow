import logging
from typing import Optional

from config import get_config
from db.database import get_connection, init_db
from db.models import get_all_baselines

logger = logging.getLogger(__name__)

INTERPRETATIONS = {
    "online_terminals": "在线终端数：反映系统同时在线的终端设备总量。传统终端为实体投注机，安卓终端为移动设备。",
    "platform_peak_tps": "平台售票峰值TPS：反映系统在峰值时段每秒处理的售票交易数，是核心容量指标。",
    "lottery_sales": "乐透售票请求：数字型彩票（如大乐透、排列三/五）的售票请求量。技术失败率应趋近于0。",
    "sports_football_sales": "传足售票请求：传统足球彩票的售票请求量。业务失败通常因投注截止或额度限制。",
    "jingcai_sales": "竞彩售票请求：竞彩彩票（竞彩足球/篮球）的售票请求量。通常请求量最大。",
    "taopiao_sales": "套票售票请求：套票产品的售票请求量，请求量通常较小。",
    "taocan_sales": "套餐票售票请求：套餐票产品的售票请求量，属于附加产品。",
    "lottery_prize": "乐透兑奖请求：数字型彩票的兑奖请求量。技术失败率应趋近于0。",
    "sports_football_prize": "传足兑奖请求：传统足球彩票的兑奖请求量。",
    "jingcai_prize": "竞彩兑奖请求：竞彩彩票的兑奖请求量。",
    "beidan_prize": "北单兑奖请求：北京单场彩票的兑奖请求量。",
    "total_requests": "所有请求：平台全量请求总数，反映整体负载水平。",
    "lottery_sales_response": "乐透售票请求响应时间：数字型彩票售票的平均/最大/中值响应时间，单位毫秒。平均应低于100ms。",
    "sports_football_sales_response": "传足售票请求响应时间：传足售票的响应时间指标。",
    "jingcai_sales_response": "竞彩售票请求响应时间：竞彩售票的响应时间指标。",
    "taopiao_sales_response": "套票售票请求响应时间：套票售票的响应时间指标。",
    "taocan_sales_response": "套餐票售票请求响应时间：套餐票售票的响应时间指标。",
    "jikai_requests": "即开请求数：即开票（刮刮乐）的请求量。分「全部」和「兑奖」两个子维度。",
    "period_report_response": "查询时段报表接口响应时间：报表查询接口性能，通常在30ms以内。",
    "game_period_report_response": "查询游戏时段报表接口响应时间：游戏维度报表查询性能，通常在25ms以内。",
    "usap_login": "USAP登陆：统一安全认证平台的登录统计，包含成功和失败次数。失败率应低于5%。",
    "info_publish_center": "信息发布中心-标准数据发布接口：数据发布服务的请求量和响应时间。",
    "payment_center": "支付中心：支付服务的请求量和响应时间。涉及资金交易，响应时间需重点关注。",
    "customer_center": "客户中心：客户管理服务的请求量和响应时间。",
    "order_center": "订单中心：订单管理服务的请求量和响应时间。",
    "marketing_center": "营销中心：营销活动相关服务的请求量。分「所有请求」「MKC抽奖-全部」「MKC抽奖-过门槛」三个子维度。",
    "open_platform": "开放平台：开放API服务的请求量和响应时间。面向第三方接入。",
    "sms_service": "短信公共服务：短信发送服务的请求量和响应时间。响应时间应在5ms以内。",
    "coop_channel": "合作渠道商户系统：合作渠道的请求量和响应时间。由于涉及外部系统，响应时间波动较大。",
    "cloud_info_publish": "信息发布系统云上：云上信息发布服务的请求量和响应时间。",
}


def get_interpretation_impl(metric_key: Optional[str] = None) -> dict:
    cfg = get_config()
    init_db(cfg.sqlite.db_path)
    conn = get_connection(cfg.sqlite.db_path)

    baselines = get_all_baselines(conn, metric_key)
    conn.close()

    results = []
    for bl in baselines:
        mk = bl["metric_key"]
        interp = INTERPRETATIONS.get(mk, f"{mk}：暂无解读标准。")
        results.append(
            {
                "metric_key": mk,
                "sub_name": bl.get("sub_name"),
                "interpretation": interp,
                "baseline_info": {
                    "avg_request_count": bl.get("avg_request_count"),
                    "avg_peak_tps": bl.get("avg_peak_tps"),
                    "avg_response_ms": bl.get("avg_response_ms"),
                    "sample_count": bl.get("sample_count"),
                },
            }
        )

    return {
        "metric_count": len(results),
        "interpretations": results,
    }


def register(mcp):
    @mcp.tool()
    def get_interpretation(metric_key: Optional[str] = None) -> dict:
        """获取指标的解读标准和基线参考值。返回每个指标的业务含义说明和对应基线数据。

        Args:
            metric_key: 指标键名，为空则返回全部指标的解读

        Returns:
            dict: {metric_count, interpretations: [{metric_key, interpretation, baseline_info}]}
        """
        return get_interpretation_impl(metric_key)
