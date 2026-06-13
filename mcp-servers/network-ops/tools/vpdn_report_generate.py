from fastmcp import FastMCP

from tools.bandwidth_report_generate import generate_bandwidth_report


_FIXED_LONG_DISTANCE_NOS = (
    "北京广州ETN2827NP",
    "北京广州ETN2631NP",
    "北京广州ETN2830NP",
    "北京广州ETN2635NP",
    "北京成都ETN2718NP",
    "北京成都ETN2533NP",
    "北京本地MSTPBJ1003789166",
    "北京本地45700045",
    "北京南京ETN2419NP",
    "北京南京ETN2420NP",
    "北京南京ETN2586NP",
    "北京南京ETN2585NP",
    "北京西安ETN6019NPH",
    "北京西安ETN2397NP",
    "北京昆明ETN2267NP",
    "北京昆明ETN2182NP",
    "北京昆明ETN2266NP",
    "北京昆明ETN2183NP",
)


def _fixed_lines_text() -> str:
    return " ".join(_FIXED_LONG_DISTANCE_NOS)


def generate_vpdn_report(
    report_scope: str = "fixed",
    days: int = 7,
    start_date: str = "",
    end_date: str = "",
    report_type: str = "周报",
    output_filename: str = "",
    include_html: bool = False,
) -> dict:
    if report_scope not in {"fixed", "other"}:
        return {
            "ok": False,
            "error": "report_scope must be fixed or other",
            "filters": {"report_scope": report_scope},
        }

    fixed_lines = _fixed_lines_text()
    if report_scope == "fixed":
        return generate_bandwidth_report(
            days=days,
            start_date=start_date,
            end_date=end_date,
            long_distance_no=fixed_lines,
            line_scope="all",
            group_by="bandwidth",
            threshold_pcts="35,40",
            report_profile="vpdn",
            report_type=report_type,
            output_filename=output_filename or "VPDN指定线路带宽周报.html",
            include_html=include_html,
        )

    return generate_bandwidth_report(
        days=days,
        start_date=start_date,
        end_date=end_date,
        line_group="VPDN终端专线",
        exclude_long_distance_no=fixed_lines,
        line_scope="all",
        group_by="bandwidth",
        threshold_pcts="35,40",
        report_profile="vpdn",
        report_type=report_type,
        output_filename=output_filename or "VPDN其他专线带宽周报.html",
        include_html=include_html,
    )


def register(mcp: FastMCP):
    @mcp.tool()
    def vpdn_report_generate(
        report_scope: str = "fixed",
        days: int = 7,
        start_date: str = "",
        end_date: str = "",
        report_type: str = "周报",
        output_filename: str = "",
        include_html: bool = False,
    ) -> dict:
        """生成 VPDN 专线 HTML 趋势报告。

        Args:
            report_scope: fixed 表示固定 18 条线路；other 表示除固定 18 条外的其他 VPDN 专线。
            days: 统计天数，默认 7。仅在未提供 start_date 时生效。
            start_date: 开始日期（YYYY-MM-DD），空则根据 days 自动计算。
            end_date: 结束日期（YYYY-MM-DD），空则取最新可用日期。
            report_type: 展示类型，通常为“周报”或“日报”。
            output_filename: 建议保存给用户的 HTML 文件名。
            include_html: 是否在工具结果中返回 HTML 全文。默认 false，避免占满上下文。

        Returns:
            dict: 成功时返回 artifact_path、present_filepaths、line_count、group_count。
        """
        return generate_vpdn_report(
            report_scope=report_scope,
            days=days,
            start_date=start_date,
            end_date=end_date,
            report_type=report_type,
            output_filename=output_filename,
            include_html=include_html,
        )
