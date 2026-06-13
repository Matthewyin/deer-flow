#!/usr/bin/env python3
"""
网络专线带宽趋势报告生成脚本

使用方法：
  1. 修改下方 === 数据配置区 === 中的 dates、LINES、GROUPS
  2. 修改标题、日期范围等显示文本
  3. 执行: python gen_report.py
  4. 输出 HTML 文件

注意：
  - 兼容 Python 3.10（f-string 中不能有反斜杠）
  - 使用 % 格式化拼接 ECharts option JSON
  - 输出自包含 HTML，仅依赖 ECharts CDN
"""

import json
import argparse
import os
from datetime import datetime

# ============================================================
# === 数据配置区（由 skill 使用者根据查询结果填入） ===
# ============================================================

# X轴日期标签
dates = ["06-05", "06-06", "06-07", "06-08", "06-09", "06-10", "06-11"]

# 报告显示参数
REPORT_TITLE = "各线路组 7天 带宽峰值/均值 & 利用率 & 延迟 趋势报告"
REPORT_PERIOD = "2026-06-05 ~ 2026-06-11"
REPORT_TYPE = "周报"  # "周报" 或 "日报"
REPORT_DATE = datetime.now().strftime("%Y-%m-%d")

THRESHOLD_PCT = 80  # 利用率阈值百分比

# 颜色映射（按运营商）
CARRIER_COLORS = {
    "电信": "#5470C6",
    "联通": "#EE6666",
    "移动": "#91CC75",
}

# 线路数据字典
# 每条线路的 key 为自定义标识，value 为包含以下字段的字典：
#   name: 显示名称（如 "#151 电信"）
#   color: 线条颜色（按运营商映射）
#   carrier: 运营商名称
#   bw: 当前带宽档位（Mbps）
#   ip: 每日入向峰值带宽列表
#   op: 每日出向峰值带宽列表
#   ia: 每日入向均值带宽列表
#   oa: 每日出向均值带宽列表
#   lat: 每日延迟列表（ms）
#   bpbl: 每日峰值基线列表（仅表格展示，不画图）
#   latbl: 每日延迟基线列表（仅表格展示，不画图）
#   bws: 每日带宽档位列表（支持带宽变化场景）
#   usage: 用途描述（用于分组）

LINES = {
    # === 在此填入线路数据 ===
    # 示例：
    # "line1": {
    #     "name": "#151 电信",
    #     "color": "#5470C6",
    #     "carrier": "电信",
    #     "bw": 40,
    #     "ip": [11.23, 13.56, 9.35, 12.17, 11.35, 11.75, 12.01],
    #     "op": [10.58, 12.56, 9.07, 11.91, 11.16, 11.54, 11.54],
    #     "ia": [6.92, 7.80, 6.80, 7.58, 7.01, 7.64, 7.74],
    #     "oa": [6.94, 7.75, 6.70, 7.65, 7.29, 7.69, 8.06],
    #     "lat": [4.09, 4.19, 4.11, 4.08, 4.20, 4.12, 4.18],
    #     "bpbl": [10.79, 11.01, 12.29, 10.82, 11.50, 11.42, 11.58],
    #     "latbl": [4.00, 4.00, 4.00, 4.00, 4.00, 4.00, 4.00],
    #     "bws": [20, 20, 40, 40, 40, 40, 40],
    #     "usage": "混合云TLS售票-腾讯公有云"
    # },
}

# 线路分组列表
# 每个元素为 (组标题, [线路key列表])
GROUPS = [
    # === 在此填入分组信息 ===
    # 示例：
    # ("一、混合云TLS售票-腾讯公有云（2条）", ["line1", "line2"]),
]

# ============================================================
# === 以下为生成逻辑，通常不需要修改 ===
# ============================================================

OUTPUT_PATH = "/mnt/user-data/outputs/带宽曲线报告.html"


def load_config(input_path):
    """从 JSON 文件加载报告数据配置。"""
    global dates, REPORT_TITLE, REPORT_PERIOD, REPORT_TYPE, REPORT_DATE, THRESHOLD_PCT, LINES, GROUPS, OUTPUT_PATH

    with open(input_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    dates = cfg["dates"]
    REPORT_TITLE = cfg.get("report_title", REPORT_TITLE)
    REPORT_PERIOD = cfg.get("report_period", REPORT_PERIOD)
    REPORT_TYPE = cfg.get("report_type", REPORT_TYPE)
    REPORT_DATE = cfg.get("report_date", REPORT_DATE)
    THRESHOLD_PCT = cfg.get("threshold_pct", THRESHOLD_PCT)
    LINES = cfg["lines"]

    raw_groups = cfg["groups"]
    GROUPS = [(item["title"], item["lines"]) if isinstance(item, dict) else (item[0], item[1]) for item in raw_groups]

    if cfg.get("output_path"):
        OUTPUT_PATH = cfg["output_path"]


def max_list(a, b):
    """取两个列表逐元素的较大值"""
    return [round(max(x, y), 2) for x, y in zip(a, b)]


def util_list(vals, bws):
    """计算利用率列表（%）"""
    return [round(v / b * 100, 2) if b > 0 else 0 for v, b in zip(vals, bws)]


def pre_compute(lines_dict):
    """预计算衍生字段"""
    for L in lines_dict.values():
        L["mp"] = max_list(L["ip"], L["op"])
        L["ma"] = max_list(L["ia"], L["oa"])
        L["pu"] = util_list(L["mp"], L["bws"])
        L["au"] = util_list(L["ma"], L["bws"])


def optional_num(vals, index):
    """格式化可选数值，缺失时显示横线。"""
    if not vals or index >= len(vals) or vals[index] is None:
        return "-"
    return "%.2f" % vals[index]


def mk_series(name, data, color, ltype="solid", width=2):
    """生成 ECharts series 配置（普通折线）"""
    return (
        "{name:'%s',type:'line',smooth:true,symbol:'circle',symbolSize:5,"
        "lineStyle:{color:'%s',type:'%s',width:%d},"
        "itemStyle:{color:'%s'},data:%s}"
        % (name, color, ltype, width, color, data)
    )


def mk_threshold_markline(yval):
    """生成 80% 利用率阈值 markLine（用于利用率图）"""
    return (
        "markLine:{silent:true,"
        "lineStyle:{color:'#FF4444',type:'dashed',width:2},"
        "data:[{yAxis:%d,label:{formatter:'%d%% 阈值',color:'#FF4444'}}]}"
        % (yval, yval)
    )


def mk_bw_threshold_markline(threshold_mbps, line_name, bw_mbps):
    """生成带宽阈值 markLine（用于带宽图，每条线路一条）"""
    return (
        "markLine:{silent:true,symbol:'none',"
        "lineStyle:{color:'#FF4444',type:'dashed',width:2},"
        "data:[{yAxis:%s,label:{formatter:'%s 80%%(%dM×80%%)',"
        "color:'#FF4444',position:'insideEndTop'}}]}"
        % (threshold_mbps, line_name, bw_mbps)
    )


def mk_chart_js(cid, names, y_max, unit_str, series_arr, first_has_markline=False):
    """通用 ECharts 图表 JS 生成"""
    s_parts = []
    for i, s in enumerate(series_arr):
        entry = s
        if i == 0 and first_has_markline:
            entry = entry.rstrip("}") + "," + mk_threshold_markline(THRESHOLD_PCT) + "}"
        s_parts.append(entry)
    series_str = ",\n        ".join(s_parts)
    return (
        "var c_%(cid)s = echarts.init(document.getElementById('%(cid)s'));\n"
        "c_%(cid)s.setOption({\n"
        "  tooltip:{trigger:'axis',backgroundColor:'rgba(255,255,255,0.95)',"
        "borderColor:'#ddd',textStyle:{color:'#333'}},\n"
        "  legend:{data:%(names)s,top:25,type:'scroll'},\n"
        "  grid:{left:'8%%',right:'5%%',bottom:'12%%',top:'18%%',containLabel:true},\n"
        "  xAxis:{type:'category',data:%(dates)s,axisLabel:{color:'#666'}},\n"
        "  yAxis:{type:'value',max:%(ymax)s,"
        "axisLabel:{color:'#666',formatter:'{value} %(unit)s'},"
        "splitLine:{lineStyle:{type:'dashed',color:'#eee'}}},\n"
        "  series:[\n        %(series)s\n  ]\n"
        "});"
    ) % {
        "cid": cid,
        "names": names,
        "dates": dates,
        "ymax": y_max,
        "unit": unit_str,
        "series": series_str,
    }


# ============================================================
# === HTML 生成 ===
# ============================================================

def generate_html():
    if not LINES or not GROUPS:
        raise ValueError("请通过 --input 指定包含 dates、lines、groups 的 JSON 数据文件")

    pre_compute(LINES)

    cc = 0
    chart_inits = []
    chart_ids = []
    section_htmls = []
    ndays = len(dates)

    for title, line_keys in GROUPS:
        lines = [LINES[k] for k in line_keys]
        p = []
        p.append('<h2>%s</h2>' % title)

        # 线路信息表
        p.append('<table class="info-table"><thead>')
        p.append('<tr><th>线路</th><th>运营商</th><th>带宽</th><th>用途</th></tr>')
        p.append('</thead><tbody>')
        for L in lines:
            p.append(
                '<tr><td>%s</td><td>%s</td><td>%dM</td><td>%s</td></tr>'
                % (L["name"], L["carrier"], L["bw"], L["usage"])
            )
        p.append('</tbody></table>')

        # --- Chart 1: 带宽峰值 & 均值（含 80% 阈值线） ---
        bw_names = []
        bw_series = []
        for L in lines:
            n = L["name"]
            c = L["color"]
            bw_names += [n + " 峰值", n + " 均值"]
            threshold_mbps = round(L["bw"] * 0.8, 2)
            s_peak = (
                "{name:'%s 峰值',type:'line',smooth:true,symbol:'circle',symbolSize:5,"
                "lineStyle:{color:'%s',type:'solid',width:2},"
                "itemStyle:{color:'%s'},data:%s,"
                "%s}"
                % (
                    n, c, c, L["mp"],
                    mk_bw_threshold_markline(threshold_mbps, n, L["bw"])
                )
            )
            bw_series.append(s_peak)
            bw_series.append(mk_series(n + " 均值", L["ma"], c, "dashed", 1.5))

        y_bw = max(max(L.get("bws", [L["bw"]])) for L in lines)

        cid1 = "c%d" % cc; cc += 1; chart_ids.append(cid1)
        chart_inits.append(mk_chart_js(cid1, bw_names, y_bw, "Mbps", bw_series))
        p.append('<h3>%s - 带宽峰值 & 均值</h3>' % title)
        p.append('<div id="%s" class="chart-container"></div>' % cid1)

        # --- Chart 2: 峰值利用率 & 均值利用率（含 80% 阈值线） ---
        ut_names = []
        ut_series = []
        for L in lines:
            n = L["name"]
            c = L["color"]
            ut_names += [n + " 峰值利用率", n + " 均值利用率"]
            ut_series.append(mk_series(n + " 峰值利用率", L["pu"], c, "solid", 2))
            ut_series.append(mk_series(n + " 均值利用率", L["au"], c, "dashed", 1.5))

        cid2 = "c%d" % cc; cc += 1; chart_ids.append(cid2)
        chart_inits.append(
            mk_chart_js(cid2, ut_names, 100, "%", ut_series, first_has_markline=True)
        )
        p.append('<h3>%s - 峰值利用率 & 均值利用率</h3>' % title)
        p.append('<div id="%s" class="chart-container"></div>' % cid2)

        # --- Chart 3: 延迟趋势 ---
        lat_names = []
        lat_series = []
        for L in lines:
            n = L["name"]
            c = L["color"]
            lat_names += [n + " 延迟"]
            lat_series.append(mk_series(n + " 延迟", L["lat"], c, "solid", 2))

        y_lat = round(max(max(L["lat"]) for L in lines) * 1.3, 2)
        y_lat = max(y_lat, 1)

        cid3 = "c%d" % cc; cc += 1; chart_ids.append(cid3)
        chart_inits.append(mk_chart_js(cid3, lat_names, y_lat, "ms", lat_series))
        p.append('<h3>%s - 延迟</h3>' % title)
        p.append('<div id="%s" class="chart-container"></div>' % cid3)

        # --- 逐日明细表 ---
        p.append('<h3>逐日明细</h3>')
        p.append('<div class="table-wrapper"><table class="data-table"><thead><tr>')
        p.append('<th>日期</th>')
        for L in lines:
            n = L["name"]
            p.append(
                '<th>%s in_peak</th><th>%s out_peak</th><th>%s max_peak</th>'
                '<th>%s in_avg</th><th>%s out_avg</th><th>%s max_avg</th>'
                '<th>%s 峰值利用率</th><th>%s 均值利用率</th>'
                '<th>%s 延迟ms</th><th>%s 峰值基线</th><th>%s 延迟基线</th><th>带宽</th>' % tuple([n] * 11)
            )
        p.append('</tr></thead><tbody>')

        for i in range(ndays):
            p.append('<tr><td>%s</td>' % dates[i])
            for L in lines:
                p.append(
                    '<td>%.2f</td><td>%.2f</td><td>%.2f</td>'
                    '<td>%.2f</td><td>%.2f</td><td>%.2f</td>'
                    '<td>%.2f%%</td><td>%.2f%%</td>'
                    '<td>%.2f</td><td>%s</td><td>%s</td><td>%dM</td>'
                    % (
                        L["ip"][i], L["op"][i], L["mp"][i],
                        L["ia"][i], L["oa"][i], L["ma"][i],
                        L["pu"][i], L["au"][i],
                        L["lat"][i],
                        optional_num(L.get("bpbl"), i),
                        optional_num(L.get("latbl"), i),
                        L["bws"][i]
                    )
                )
            p.append('</tr>')
        p.append('</tbody></table></div>')

        section_htmls.append("\n".join(p))

    # --- 总结汇总表 ---
    summ = ['<h2>总结</h2>']
    summ.append('<table class="data-table"><thead><tr>')
    summ.append(
        '<th>线路</th><th>运营商</th><th>带宽</th><th>最大峰值</th>'
        '<th>最大峰值利用率</th><th>最大均值利用率</th><th>最大延迟</th><th>评估</th>'
    )
    summ.append('</tr></thead><tbody>')

    for title, line_keys in GROUPS:
        for k in line_keys:
            L = LINES[k]
            mx_p = max(L["mp"])
            mx_pu = max(L["pu"])
            mx_au = max(L["au"])
            mx_lat = max(L["lat"])

            if mx_pu >= THRESHOLD_PCT:
                st = "🔴 超%d%%阈值" % THRESHOLD_PCT
            elif mx_pu >= 60:
                st = "⚠️ 较高（60~%d%%）" % THRESHOLD_PCT
            else:
                st = "✅ 正常"

            cls = ""
            if "🔴" in st:
                cls = ' class="danger"'
            elif "⚠️" in st:
                cls = ' class="warning"'

            summ.append(
                '<tr%s><td>%s</td><td>%s</td><td>%dM</td><td>%.2f Mbps</td>'
                '<td>%.2f%%</td><td>%.2f%%</td><td>%.2f ms</td><td>%s</td></tr>'
                % (cls, L["name"], L["carrier"], L["bw"], mx_p, mx_pu, mx_au, mx_lat, st)
            )

    summ.append('</tbody></table>')

    # --- 拼装 JS ---
    resize_calls = " ".join(["c_%s.resize();" % c for c in chart_ids])
    script = (
        "\n".join(chart_inits)
        + "\nwindow.addEventListener('resize',function(){"
        + resize_calls + "});"
    )

    # --- CSS ---
    CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
                 'Microsoft YaHei', sans-serif;
    background: #f5f7fa; color: #333; line-height: 1.6; padding: 20px;
}
.container {
    max-width: 1400px; margin: 0 auto; background: #fff; border-radius: 8px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.08); padding: 30px 40px;
}
h1 {
    text-align: center; font-size: 22px; color: #1a1a2e;
    border-bottom: 3px solid #5470C6; padding-bottom: 15px; margin-bottom: 10px;
}
.meta { text-align: center; color: #888; font-size: 14px; margin-bottom: 30px; }
h2 {
    font-size: 18px; color: #1a1a2e; margin: 35px 0 15px 0;
    padding-left: 12px; border-left: 4px solid #5470C6;
}
h3 { font-size: 15px; color: #444; margin: 20px 0 10px 0; }
.chart-container {
    width: 100%; height: 420px; margin: 10px 0 25px 0;
    border: 1px solid #e8e8e8; border-radius: 6px; background: #fafbfc;
}
.info-table, .data-table {
    width: 100%; border-collapse: collapse; margin: 10px 0 20px 0; font-size: 12px;
}
.info-table th, .data-table th {
    background: #f0f3f8; color: #333; font-weight: 600; padding: 8px;
    border: 1px solid #ddd; text-align: center; white-space: nowrap;
    position: sticky; top: 0; z-index: 1;
}
.info-table td, .data-table td {
    padding: 5px 8px; border: 1px solid #ddd; text-align: center; white-space: nowrap;
}
.info-table tbody tr:hover, .data-table tbody tr:hover { background: #f5f8ff; }
.table-wrapper { overflow-x: auto; max-height: 450px; overflow-y: auto; }
.legend-section {
    margin: 20px 0; padding: 15px; background: #f8f9fa; border-radius: 6px;
}
.legend-item {
    display: inline-flex; align-items: center; margin-right: 20px;
    margin-bottom: 8px; font-size: 13px;
}
.legend-line {
    width: 30px; height: 0; display: inline-block; margin-right: 6px;
    vertical-align: middle;
}
.legend-dot {
    width: 14px; height: 14px; border-radius: 3px; margin-right: 6px;
    display: inline-block;
}
.warning td { background: #fff3e0 !important; }
.danger td { background: #ffebee !important; }
"""

    # --- 拼装 HTML ---
    html_parts = [
        '<!DOCTYPE html><html lang="zh-CN"><head>',
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        '<title>%s</title>' % REPORT_TITLE,
        '<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>',
        '<style>', CSS, '</style>',
        '</head><body><div class="container">',
        '<h1>%s</h1>' % REPORT_TITLE,
        '<p class="meta">数据周期: %s &nbsp;|&nbsp; 报告生成时间: %s</p>' % (REPORT_PERIOD, REPORT_DATE),
        '<div class="legend-section">',
        '<strong>线型说明：</strong><br>',
        '<span class="legend-item"><span class="legend-line" style="border-top:2px solid #5470C6;"></span>实线 = 峰值</span>',
        '<span class="legend-item"><span class="legend-line" style="border-top:2px dashed #5470C6;"></span>虚线 = 均值</span>',
        '<br><strong>颜色：</strong>',
        '<span class="legend-item"><span class="legend-dot" style="background:#5470C6;"></span>电信</span>',
        '<span class="legend-item"><span class="legend-dot" style="background:#EE6666;"></span>联通</span>',
        '<span class="legend-item"><span class="legend-dot" style="background:#91CC75;"></span>移动</span>',
        '<br><strong>阈值线：</strong>',
        '<span class="legend-item"><span style="color:#FF4444;font-weight:bold;">- - -</span> %d%% 利用率阈值</span>' % THRESHOLD_PCT,
        '</div>',
        "\n".join(section_htmls),
        "\n".join(summ),
        '</div>',
        '<script>', script, '</script>',
        '</body></html>',
    ]

    html = "\n".join(html_parts)

    output_dir = os.path.dirname(OUTPUT_PATH)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print("HTML报告已生成: %s" % OUTPUT_PATH)
    print("共 %d 个图表, %d 条线路" % (cc, sum(len(g[1]) for g in GROUPS)))
    return OUTPUT_PATH


def main():
    parser = argparse.ArgumentParser(description="生成网络专线带宽趋势 HTML 报告")
    parser.add_argument("--input", required=True, help="报告数据 JSON 文件路径")
    parser.add_argument("--output", help="HTML 输出路径")
    args = parser.parse_args()

    load_config(args.input)
    if args.output:
        global OUTPUT_PATH
        OUTPUT_PATH = args.output
    generate_html()


if __name__ == "__main__":
    main()
