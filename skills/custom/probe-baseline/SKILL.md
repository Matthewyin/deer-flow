---
name: probe-baseline
description: 远程探测基线分析技能。当用户查询网络探测结果、基线对比、延迟分析、ICMP/TCP/TLS/DNS/MTR状态时加载此技能。触发词：探测、基线、延迟、RTT、丢包、TLS握手、DNS解析、MTR、网络质量、探测报告。
---

# 远程探测基线分析技能

## 概述
此技能指导你完成远程探测基线分析的完整流程：先保障最新数据可用，再做基线对比和报告生成。

## 触发条件
- 提到"探测"、"基线"、"延迟"、"RTT"、"丢包"
- 提到"TLS"、"SSL证书"、"握手时间"
- 提到"DNS解析"、"域名解析"
- 提到"MTR"、"路由追踪"、"网络路径"
- 提到"探测报告"、"网络质量"
- 询问某个region或domain的探测状态
- 要求对比当前数据与基线

## 可用工具
| 工具 | 用途 | 数据源 |
|------|------|--------|
| `ensure_probe_data` | 检查最新探测指标，必要时触发采集、解析入库、更新基线 | data-manager + SQLite |
| `collect_probe_data` | 从6台ECS增量采集探测数据 | SSH → ECS /root/tools/.../probe_lottery/ |
| `parse_probe_results` | 解析JSON探测结果入库 | .deer-flow/probe/raw/ → SQLite |
| `init_baseline` | 初始化基线（取最近N次平均值） | SQLite probe_metrics |
| `update_baseline` | 动态调整基线（滑动窗口加权平均） | SQLite probe_baseline |
| `compare_with_baseline` | 基线对比（偏差分析） | SQLite probe_metrics + probe_baseline |
| `generate_probe_report` | 生成Markdown探测报告 | SQLite |

## 工作流程

### 流程 A：日常探测报告
1. 用户："生成今天的探测报告" 或定时任务触发
2. ensure_probe_data() → 确认最新数据已入库
3. compare_with_baseline() → 基线对比
4. generate_probe_report() → 生成报告

### 流程 B：特定Region查询
1. 用户："呼和浩特到g3jstls的探测情况怎么样"
2. ensure_probe_data(regions=["hhht"]) → 确认该节点最新数据
3. compare_with_baseline(region="hhht", domain="g3jstls.lottery-it.com")
4. 整合结果回复

### 流程 C：基线初始化
1. 用户："初始化杭州的基线"
2. init_baseline(region="hz", domain="g3jstls.lottery-it.com:8443")
3. init_baseline(region="hz", domain="sso-mobile.lottery-sports.com:443")

### 流程 D：手动更新基线
1. 用户："更新所有基线"
2. update_baseline() for each region+domain combo

### 流程 E：异常排查
1. 用户报告某个region延迟高
2. ensure_probe_data(regions=["hhht"]) → 采集并解析缺失数据
3. compare_with_baseline(region="hhht") → 对比
4. 如需强制重新采集，再使用 collect_probe_data + parse_probe_results
5. 整合分析结果

## 6个探测节点
| Region代码 | 城市 | IP地址 |
|-----------|------|--------|
| hhht | 呼和浩特 | 39.104.209.139 |
| wh | 武汉 | 47.122.115.139 |
| hz | 杭州 | 116.62.131.213 |
| wlcb | 乌兰察布 | 8.130.82.52 |
| qd | 青岛 | 120.27.112.200 |
| cd | 成都 | 47.108.239.135 |

## 2个探测目标
| 域名 | 端口 | TLS类型 | 解析IP数 |
|------|------|---------|----------|
| g3jstls.lottery-it.com | 8443 | 双向SSL | 2 |
| sso-mobile.lottery-sports.com | 443 | 单向SSL | 1 |

## 语义理解要点
- "呼和浩特延迟怎么样" → compare_with_baseline(region="hhht")
- "探测报告" → generate_probe_report()
- "最新数据到哪天" → ensure_probe_data()，以返回的 latest_metric 为准
- "采集数据" → ensure_probe_data() 优先；明确要求强制采集时才用 collect_probe_data()
- "基线有问题" → compare_with_baseline() 查看偏差
- "网络质量" → compare_with_baseline()
- "TLS证书快过期" → compare_with_baseline() 关注tls相关指标
- "丢包率" → compare_with_baseline() 关注packet_loss_pct

## 注意事项
- 基线数据存储在SQLite中，不使用RAG
- 判断“最新日期”必须调用 ensure_probe_data 或查询 probe_metrics，不能引用记忆中的历史日期
- 采集是增量的，不会重复下载已有数据
- 基线对比阈值：RTT/TCP/TLS/DNS >30%为WARNING，>50%为CRITICAL
- 报告保存在 .deer-flow/probe/reports/ 目录
- 本系统与其他系统（带宽管理、运维知识库）完全独立
