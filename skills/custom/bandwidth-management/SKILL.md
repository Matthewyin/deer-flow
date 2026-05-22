---
name: bandwidth-management
description: 带宽管理技能。当用户咨询专线带宽相关问题（扩容、缩容、线路查询、流量分析、邮件申请）时加载此技能。触发词：带宽、扩容、缩容、线路、专线、流量、P95。也适用于用户提供流量报表或监控数据的场景。
---

# 带宽管理技能

## 概述

此技能指导你完成带宽策略分析的完整流程：从数据入库、查询分析、到 P95 计算和扩缩容判断，最终生成邮件草稿。

**数据流**：HTML 日报 → data-manager 解析 21 列表格 → JSON 文件（共享 volume）→ `ensure_bandwidth_data` 入库 SQLite → `bandwidth_check` 查询 + P95 计算 + 扩缩容判断 → `bandwidth_report` 生成邮件。

## 触发条件

当用户输入包含以下任何一种情况时，立即加载此技能：
- 提到"带宽"、"专线"、"线路"、"流量"、"扩容"、"缩容"
- 提到具体带宽值如"10M"、"20M"、"5Mbps"
- 提到两端站点如"亦庄到西藏"、"西五环到山东"
- 粘贴流量监控数据或报表
- 询问带宽相关操作流程
- 提到"基线"、"对比"、"偏离"、"趋势分析"、"线路日报"
- 提到"P95"、"利用率"、"带宽评估"

## 可用工具

### 核心带宽工具（新体系，不依赖 MySQL）

| 工具 | 用途 | 数据源 |
|------|------|--------|
| `ensure_bandwidth_data` | 扫描 JSON 文件入库线路带宽数据 | SQLite (bandwidth_lines 表) |
| `bandwidth_check` | 查询线路数据，计算 P95，判断扩缩容 | SQLite (bandwidth_lines 表) |
| `bandwidth_report` | 根据检查结果生成邮件内容（3种模板） | bandwidth_check 结果 |

### 旧版工具（仍可用）

| 工具 | 用途 | 数据源 |
|------|------|--------|
| `line_info_query` | 查询专线线路信息 | MySQL (iteams_db) |
| `bandwidth_assess` | 评估带宽是否需要扩缩容 | SQLite |
| `policy_search` | 搜索带宽策略文档 | ChromaDB RAG |
| `bandwidth_stats` | 查询带宽档位统计 | SQLite + MySQL |
| `email_generate` | 生成邮件草稿 | 代码模板 |
| `ensure_line_status_data` | 入库线路状态数据 | JSON 文件 |
| `line_status_compare` | 实际值 vs 基线对比 | SQLite |
| `line_status_history` | 历史趋势查询 | SQLite |

## 工作流程

### 流程 A：自动带宽评估（推荐，默认流程）

当用户要求"评估带宽"、"看看要不要扩容"、"检查线路"等时使用。

1. **确保数据已入库**：调用 `ensure_bandwidth_data`
   ```
   ensure_bandwidth_data()
   ```

2. **查询并评估**：调用 `bandwidth_check`
   - 默认取 15 天数据
   - 用户指定时间范围时按用户要求取
   ```
   bandwidth_check(days=15)
   # 或指定范围：
   bandwidth_check(start_date="2025-05-01", end_date="2025-05-15")
   # 或指定线路组：
   bandwidth_check(days=15, line_group="VPDN终端专线")
   ```

3. **生成邮件**（如有扩缩容建议）：调用 `bandwidth_report`
   - report_type: "expand"（常态化扩容）、"emergency"（应急扩容）、"shrink"（缩容）
   ```
   bandwidth_report(check_result=<bandwidth_check返回的JSON字符串>, report_type="expand")
   ```

4. **回复用户**：整合检查结果和邮件内容

### 流程 B：自然语言输入（一句话）

示例：`"亦庄到西藏数据端带宽使用到了5M，应该怎么办？"`

1. **理解意图**：提取站点、用途、流量值
2. **查线路信息**：`line_info_query(description="亦庄到西藏数据端")`
3. **评估策略**：`bandwidth_assess(current_bw_mbps=<带宽>, current_traffic_mbps=<流量>)`
4. **查操作流程**：`policy_search(query="扩容操作流程")`
5. **生成邮件**：`email_generate(action=<评估结果>, ...)`

### 流程 C：统计查询
1. `bandwidth_stats(bandwidth="10M")`

### 流程 D：策略咨询
1. `policy_search(query="<用户问题>")`

## 扩缩容判断规则

| 场景 | 条件 | 操作 |
|------|------|------|
| 扩容 | P95 利用率 > 40% | 升至下一档位 |
| 缩容 | P95 流量 < 下一档 × 35% | 降至下一档位 |
| 维持 | 不满足上述条件 | 保持现状 |

带宽档位：2, 4, 6, 8, 10, 20, 30, 40, 50 Mbps

## bandwidth_check 返回结构

```json
{
  "period": {"start": "2025-05-07", "end": "2025-05-21"},
  "total_groups": 6,
  "groups": [
    {
      "group_name": "VPDN终端专线",
      "group_p95_traffic_sum": 45.2,
      "line_count": 3,
      "lines": [
        {
          "long_distance_no": "XX-XXX",
          "bandwidth_mbps": 10,
          "p95_in_util": 42.5,
          "p95_out_util": 38.1,
          "p95_traffic": 4.25,
          "action": "expand",
          "target_bandwidth": 20,
          "province": "西藏",
          "carrier": "电信",
          "usage": "数据端"
        }
      ]
    }
  ]
}
```

action 值：`"expand"`（需扩容）、`"shrink"`（可缩容）、`"maintain"`（维持现状）

## 注意事项

- **数据入库由 data-manager 自动完成**（上传 HTML 时触发解析），skill 只需调用 `ensure_bandwidth_data` 确保入库
- **P95 计算在 MCP 工具层完成**，skill 不需要自行计算
- **邮件模板在 MCP 工具层处理**，支持 3 种类型
- 操作流程详情通过 `policy_search` 获取
- 给出评估结果后，检查调整后是否仍不符合策略，需迭代评估直到符合
