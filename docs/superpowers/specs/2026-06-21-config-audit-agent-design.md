# 设备配置审查 Agent 设计

> 日期：2026-06-21  
> 状态：已批准  
> 范围：新增防火墙配置审查能力，首版覆盖 H3C、Huawei、Hillstone，支持完整配置审查和配置脚本片段审查

## 1. 背景与目标

现有 `FWProcess` 项目已经能处理部分防火墙配置，将 H3C、Huawei、Hillstone 的原始配置整理为 JSON 和 Excel。但它目前是按厂商、设备、脚本分散实现，适合一次性整理，不适合作为 DeerFlow 中可复用、可追溯、可扩展的配置审查能力。

本设计的目标不是单纯生成配置清单，而是在 DeerFlow 中新增一个面向设备配置审查的 Agent。首版先从防火墙开始，后续再扩展到路由器、交换机、负载均衡。

核心目标有两个：

1. **事后标准化检查**：给定一份完整设备配置，先完成配置梳理，再与该设备角色对应的标准模板对比，检查当前配置是否标准、是否有遗漏。
2. **事前配置脚本检查**：给定一段待执行配置脚本，分析脚本意图、命令完整性、配置依赖和潜在错误，判断是否缺少关键配置内容。

配置梳理是这两个目标的事实基础。Agent 必须先拿到结构化配置事实，再进行标准化对比和 LLM 辅助分析。

## 2. 设计原则

1. **MCP 负责事实，Agent 负责判断**  
   MCP server 负责确定性工作：解析配置、归一化模块、生成候选模板、执行字段级差异对比、导出文件。Agent 负责选择流程、解释差异、判断脚本意图、生成可读结论。

2. **标准按角色定义，不按厂商定义**  
   标准模板的主键是 `device_type + standard_zone + role`。厂商、型号、系统版本只影响解析和命令表达，不作为业务标准的最高层分类。

3. **先反推，再人工复核**  
   首版标准模板从现有认可配置中反推，生成 draft。只有经过人工复核并保存为 approved 的模板，才能用于正式审查。

4. **完整配置优先，片段分析复用同一模型**  
   完整配置用于建立设备画像和标准模板。配置脚本片段按同一统一模型解析，但报告必须标注上下文不完整带来的不确定性。

5. **LLM 不作为唯一判定源**  
   LLM 可以参与解释、归纳和风险判断，但不能绕过 MCP 的结构化事实和差异清单直接给审查结论。

## 3. 整体架构

新增能力组命名为 `config-audit`，由三部分组成：

| 组件 | 职责 |
|------|------|
| `mcp-servers/config-audit/` | 解析配置、统一模型、模板反推、模板对比、报告导出 |
| `skills/custom/config-audit/SKILL.md` | 约束 Agent 工作流，要求先调用 MCP 获取结构化事实 |
| `config-audit-agent` | 面向用户的配置审查入口，后续作为自定义 Agent 接入 DeerFlow |

核心数据流：

```text
完整配置 / 配置脚本片段
  -> MCP 识别厂商、设备类型、型号、版本、区域和角色
  -> MCP 解析为统一配置模块
  -> MCP 生成 Excel 事实表
  -> MCP 与 approved 标准模板做差异对比
  -> Agent 基于差异结果做 LLM 分析
  -> MCP/Agent 输出 Markdown 审查报告
```

首版不引入真实设备连接，不自动下发配置，不做图形化模板编辑器。

## 4. 统一配置模型

不同厂商、型号、系统版本的配置语法不同，但审查对象应保持一致。统一模型分为设备画像和配置模块两层。

### 4.1 设备画像

设备画像字段：

| 字段 | 说明 |
|------|------|
| `device_name` | 设备名称 |
| `vendor` | 厂商，如 H3C、Huawei、Hillstone |
| `device_type` | 设备类型，首版固定为 `firewall` |
| `model` | 设备型号，可由配置识别或人工输入 |
| `os_version` | 系统版本，可由配置识别或人工输入 |
| `site_name` | 站点名称，如西五环、亦庄 |
| `local_area_name` | 现网区域名称，如西五环互联网A接入、运营VDI区 |
| `standard_zone` | 标准分类，如互联网边界、DMZ、生产区、管理区、外联区、云连接区 |
| `role` | 设备角色，如边界防火墙、接入防火墙、管理防火墙 |

`site_name` 和 `local_area_name` 保留现网语境；`standard_zone` 和 `role` 用于匹配标准模板。

### 4.2 配置模块

首版统一配置模块：

| 模块 | 内容 |
|------|------|
| `zones` | 安全域、vrouter、vsys 归属 |
| `interfaces` | 接口、IP、所属安全域、状态 |
| `address_objects` | 地址对象、地址组、IP、网段、range |
| `service_objects` | 服务对象、协议、端口 |
| `policy_rules` | 策略规则、源/目的区域、源/目的对象、服务、动作、日志、状态 |
| `nat_rules` | NAT 类型、源/目的、转换地址、匹配区域 |
| `routes` | 静态路由、默认路由、下一跳、出接口 |
| `management_access` | 管理协议、允许来源、AAA/本地用户、登录限制 |
| `logging` | 日志开关、策略日志、syslog、SNMP、告警目标 |
| `unparsed_blocks` | 未识别或未归一化配置块 |

解析优先级：

| 优先级 | 模块 |
|--------|------|
| P0 | `device_profile`、`zones`、`address_objects`、`service_objects`、`policy_rules` |
| P1 | `nat_rules`、`routes` |
| P2 | `interfaces`、`management_access`、`logging` |

首版必须稳定覆盖 P0。P1 尽量覆盖。P2 可以先保留解析接口和部分样本支持。

## 5. 标准模板模型

标准模板不按厂商建立，而按设备职责建立：

```text
device_type + standard_zone + role
```

示例：

```text
firewall + internet_edge + border_firewall
firewall + dmz + border_firewall
firewall + management_zone + management_firewall
```

模板字段：

| 字段 | 说明 |
|------|------|
| `template_id` | 模板唯一标识 |
| `device_type` | 设备类型 |
| `standard_zone` | 标准分类 |
| `role` | 设备角色 |
| `version` | 模板版本 |
| `status` | `draft` 或 `approved` |
| `source_configs` | 来源配置文件或设备名 |
| `reviewed_by` | 复核人 |
| `reviewed_at` | 复核时间 |
| `required_modules` | 必须存在的模块 |
| `expected_patterns` | 应符合的配置模式 |
| `vendor_overrides` | 厂商、型号或版本差异 |

模板内容分三类：

1. **`required_modules`**  
   必须存在的模块，例如安全域、策略日志、默认拒绝策略、管理访问限制。

2. **`expected_patterns`**  
   应符合的模式，例如策略必须开启日志、管理来源不能是 any、边界策略不能全放通。

3. **`reference_baseline`**  
   从认可配置反推得到的候选标准。该内容必须人工复核后才能进入 approved 模板。

标准模板反推流程：

```text
认可的完整配置
  -> MCP 解析为统一配置模型
  -> MCP 抽取共同模块和关键模式
  -> MCP 生成 draft 候选模板
  -> Agent 用 LLM 解释候选模板含义
  -> 用户人工复核
  -> MCP 保存 approved 正式模板
```

## 6. MCP 工具接口

首版 `config-audit` MCP server 提供以下工具。

### 6.1 `config_audit_parse_config`

用途：完整配置梳理。

输入：

- 完整配置文件路径或配置文本
- 厂商、型号、版本、区域等元数据，可选

输出：

- 统一配置模型 JSON
- 解析覆盖率
- 未识别配置块摘要

### 6.2 `config_audit_parse_snippet`

用途：事前配置脚本片段分析。

输入：

- 配置脚本片段
- 目标设备画像或标准模板 ID

输出：

- 片段涉及的配置模块
- 命令意图
- 可能依赖的上下文
- 不确定性说明

### 6.3 `config_audit_infer_template`

用途：从现有认可配置反推候选标准模板。

输入：

- 一份或多份已认可完整配置的结构化结果
- 标准分类
- 设备角色

输出：

- draft 候选模板
- 反推依据
- 需要人工确认的问题清单

### 6.4 `config_audit_review_template`

用途：人工复核后固化模板。

输入：

- draft 候选模板
- 人工确认或修改内容

输出：

- approved 模板版本
- 模板保存路径

### 6.5 `config_audit_compare_config`

用途：事后标准化检查。

输入：

- 完整配置结构化结果
- approved 标准模板

输出：

- 缺失项
- 异常项
- 风险项
- 匹配项

### 6.6 `config_audit_check_snippet`

用途：事前配置命令检查。

输入：

- 片段结构化结果
- 目标 approved 标准模板
- 当前完整配置，可选

输出：

- 脚本缺失内容
- 命令顺序或依赖问题
- 与标准不一致项
- 上下文不足项

### 6.7 `config_audit_export_report`

用途：导出审查结果。

输入：

- 结构化配置结果
- 差异结果
- Agent 分析结论

输出：

- Excel 文件路径
- Markdown 报告路径

## 7. Agent 工作流

### 7.1 完整配置梳理

```text
用户上传完整配置
  -> Agent 调用 config_audit_parse_config
  -> MCP 返回设备画像、配置模块、未识别块
  -> Agent 调用 config_audit_export_report 生成 Excel 事实表
  -> Agent 返回模块统计和附件路径
```

### 7.2 标准模板反推

```text
用户指定认可样本
  -> Agent 调用 config_audit_parse_config
  -> Agent 调用 config_audit_infer_template
  -> Agent 用 LLM 解释候选模板含义
  -> 用户人工确认或修改
  -> Agent 调用 config_audit_review_template 保存 approved 模板
```

### 7.3 事后标准化检查

```text
用户上传完整配置并指定区域/角色
  -> Agent 调用 config_audit_parse_config
  -> Agent 调用 config_audit_compare_config
  -> Agent 基于差异清单做 LLM 分析
  -> Agent 调用 config_audit_export_report 输出 Excel + Markdown
```

### 7.4 事前配置脚本检查

```text
用户提供配置脚本片段 + 目标区域/角色
  -> Agent 调用 config_audit_parse_snippet
  -> Agent 调用 config_audit_check_snippet
  -> 如提供当前完整配置，则结合现状判断是否遗漏
  -> Agent 用 LLM 解释风险、缺失和建议补充命令
  -> Agent 输出 Markdown 审查结论，必要时导出 Excel
```

片段分析必须明确标注“基于片段判断”。只有同时提供当前完整配置时，才能做强结论。

## 8. 数据存储

首版使用文件存储，不引入数据库。后续样本和模板数量变多后，再迁移到 SQLite。

建议目录：

```text
mcp-servers/config-audit/
  server.py
  parsers/
    h3c_firewall.py
    huawei_firewall.py
    hillstone_firewall.py
  core/
    model.py
    normalize.py
    template.py
    compare.py
    export.py
  templates/
    draft/
    approved/
  examples/
  tests/

skills/custom/config-audit/
  SKILL.md

backend/.deer-flow/config-audit/
  inputs/
  parsed/
  templates/
    draft/
    approved/
  reports/
```

模板保存路径：

```text
backend/.deer-flow/config-audit/templates/approved/
  firewall/
    internet_edge/
      border_firewall.yaml
    dmz/
      border_firewall.yaml
    management_zone/
      management_firewall.yaml
```

MCP server 内置模板可放在 `mcp-servers/config-audit/templates/`，运行态用户复核模板放在 `backend/.deer-flow/config-audit/templates/`。

## 9. 报告格式

### 9.1 Excel

结构化 Excel 固定包含以下 sheet：

- `device_profile`
- `zones`
- `interfaces`
- `address_objects`
- `service_objects`
- `policy_rules`
- `nat_rules`
- `routes`
- `management_access`
- `logging`
- `unparsed_blocks`
- `findings`

Excel 负责保存事实层和差异层，便于人工复核和归档。

### 9.2 Markdown

Markdown 报告结构：

```text
# 配置审查报告

## 结论摘要
## 设备画像
## 配置模块统计
## 标准模板版本
## 关键缺失项
## 异常与风险项
## 配置脚本检查结果
## LLM 分析说明
## 整改建议
## 附件
```

Markdown 负责保存 Agent 分析结论和整改建议。

### 9.3 差异项字段

差异项统一字段：

| 字段 | 说明 |
|------|------|
| `finding_id` | 问题编号 |
| `severity` | `high`、`medium`、`low`、`info` |
| `module` | 所属模块 |
| `finding_type` | `missing`、`mismatch`、`risky`、`unknown` |
| `expected` | 期望配置 |
| `actual` | 实际配置 |
| `evidence` | 证据 |
| `llm_analysis` | LLM 分析 |
| `recommendation` | 整改建议 |

## 10. 首版范围

首版包含：

- 设备类型：只做 `firewall`
- 厂商：H3C、Huawei、Hillstone
- 输入：完整配置文件、配置脚本片段
- 标准体系：`device_type + standard_zone + role`
- 标准来源：从认可配置反推，人工复核后 approved
- 输出：统一结构化 Excel、Markdown 审查报告
- DeerFlow 集成：`config-audit` MCP server、`config-audit` custom skill、后续 `config-audit-agent`

首版不包含：

- 不做路由器、交换机、负载均衡
- 不做自动下发配置
- 不直接连接真实设备
- 不做图形化模板编辑器
- 不做全量命令语义解释
- 不把 LLM 判断作为唯一审查依据

## 11. 风险与处理

| 风险 | 处理方式 |
|------|----------|
| 厂商配置语法差异大 | 解析器按厂商拆分，统一模型保持稳定 |
| 历史配置反推模板可能继承错误 | draft 必须人工复核，approved 才能用于正式审查 |
| 配置片段缺上下文 | 报告标注片段分析，有完整配置时才做强判断 |
| LLM 误判 | LLM 只解释 MCP 结构化结果，不覆盖确定性差异 |
| 现有脚本重复严重 | 复用解析经验，不继续复制每设备脚本 |

## 12. 测试策略

每个厂商选 1-2 份现有配置作为样本。

解析器测试：

- 能识别设备画像或接收人工元数据
- 能抽取 P0 模块：安全域、地址对象、服务对象、策略规则
- 未识别块进入 `unparsed_blocks`

模板反推测试：

- 从认可样本生成 draft
- 人工确认后保存 approved
- approved 模板可被后续检查读取

配置对比测试：

- 删除或修改一项关键配置后能产生 finding
- finding 包含期望、实际、证据和建议

片段检查测试：

- 缺上下文脚本必须标注不确定性
- 提供当前完整配置和片段时，能判断缺失和依赖问题

报告测试：

- Excel 包含固定 sheet
- Markdown 包含结论、证据、建议和附件路径

## 13. 后续扩展

首版稳定后，再按同一模型扩展：

1. 路由器配置审查
2. 交换机配置审查
3. 负载均衡配置审查
4. SQLite 模板库和审查历史
5. 标准模板差异版本管理
6. Web 端模板复核界面

这些扩展只新增设备类型解析器、模板和 Agent 工作流，不改变首版定义的事实层、模板层、对比层和报告层边界。
