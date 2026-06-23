---
name: config-audit
description: >
  设备配置审查技能。用于防火墙完整配置梳理、标准模板反推、事后标准化检查、
  以及配置脚本片段的事前正确性检查。首版覆盖 H3C、Huawei、Hillstone 防火墙。
---

# 设备配置审查

本技能只约束 Agent 工作流。确定性解析、模板反推、差异对比和报告导出必须调用 `config-audit` MCP 工具完成。

## 核心原则

1. 先调用 MCP 获取结构化事实，再做 LLM 分析。
2. 不要直接凭原始配置文本给最终审查结论。
3. 完整配置检查必须使用 approved 标准模板。
4. 从现有配置反推的模板只能作为 draft，必须人工复核后才能用于正式检查。
5. 配置片段分析必须声明上下文不完整；只有同时提供当前完整配置时，才能做强判断。
6. 所有整改建议只作为审查建议输出，禁止自动下发配置命令。
7. 如果配置来自 data-manager，先调用导入批次工具，不要求用户重复粘贴配置。

## data-manager 导入批次

用户通过 data-manager 的“设备配置”选项卡批量导入配置后：

1. 调用 `config_audit_list_import_batches` 查看可用批次。
2. 让用户确认要处理的 `import_id`，或按用户指定的厂商、设备类型、批次名称筛选。
3. 调用 `config_audit_parse_import_batch` 获取批次摘要，不要请求完整配置对象。
4. 需要反推模板时，调用 `config_audit_infer_template_from_import_batch`，不要先把完整批次解析结果放入对话。
5. 对解析摘要、模板草稿、标准化检查结果继续做 LLM 分析。

当前批次解析只支持 H3C、Huawei、Hillstone 防火墙。F5、深信服、路由器、交换机、负载均衡只作为配置资产保存，不能声称已完成解析。

## 工作流 A：完整配置梳理

1. 明确厂商、标准分类和设备角色。
2. 调用 `config_audit_parse_config`。
3. 检查 security zones、inter-zone policy、地址对象、服务对象、日志和未识别块。
4. 调用 `config_audit_export_report` 导出 Excel 事实表和 Markdown 报告。
5. 向用户返回设备画像、模块统计、未识别块和附件路径。

## 工作流 B：标准模板反推

1. 用户明确指定“认可样本”。
2. 对每份样本调用 `config_audit_parse_config`。
3. 调用 `config_audit_infer_template` 生成 draft。
4. 用 LLM 解释 draft 模板的来源、适用区域和需要人工确认的内容。
5. 等用户人工确认或修改后，调用 `config_audit_review_template` 保存 approved 模板。

## 工作流 C：事后标准化检查

1. 调用 `config_audit_parse_config`。
2. 读取或让用户指定 approved 标准模板。
3. 调用 `config_audit_compare_config`。
4. 基于 findings 做 LLM 分析，解释风险和整改建议。
5. 调用 `config_audit_export_report` 输出 Excel 和 Markdown。

## 工作流 D：事前配置脚本检查

1. 明确目标厂商、标准分类和设备角色。
2. 调用 `config_audit_parse_snippet`。
3. 调用 `config_audit_check_snippet`。
4. 如果用户提供当前完整配置，将完整配置作为上下文一并检查。
5. 输出缺失内容、依赖问题、命令风险和建议补充项。

## 禁止事项

- 禁止直接手写临时解析脚本绕过 MCP。
- 禁止把 draft 模板当正式模板使用。
- 禁止自动下发配置命令。
- 禁止把 LLM 分析当作唯一证据。
- 禁止在没有 approved 模板时给出“已符合标准”的结论。
