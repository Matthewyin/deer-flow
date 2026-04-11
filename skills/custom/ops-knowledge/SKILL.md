---
name: ops-knowledge
description: 运维知识库技能。当用户查询运维相关知识（故障案例、SOP流程、应急预案、解决方案、事件记录）时加载此技能。触发词：故障、SOP、预案、应急、巡检、知识库、运维文档、解决方案。也适用于用户需要上传或管理运维文档的场景。
---

# 运维知识库技能

## 概述

此技能指导你完成运维知识库的完整交互流程：从理解用户需求，到检索知识、上传文档、浏览库内容。

知识库存储在独立的 ChromaDB 向量数据库中，通过 MCP Server 提供服务。支持 fault（故障案例）、sop（标准操作流程）、emergency（应急预案）、solution（解决方案）、event（事件记录）五种文档类型。

## 触发条件

当用户输入包含以下任何一种情况时，立即加载此技能：
- 提到"故障"、"故障案例"、"排障"、"troubleshooting"
- 提到"SOP"、"标准操作"、"操作流程"、"操作规范"
- 提到"预案"、"应急"、"应急预案"、"应急响应"
- 提到"解决方案"、"知识库"、"运维文档"
- 提到"事件记录"、"事件报告"
- 需要查找历史运维经验或文档
- 需要上传新的运维文档

## 可用工具

| 工具 | 用途 | 数据源 |
|------|------|--------|
| `knowledge_search` | 语义检索知识库 | ChromaDB (ops_knowledge collection) |
| `knowledge_upload` | 文档入库（支持pdf/docx/xlsx/txt/md/csv） | ChromaDB + SQLite |
| `knowledge_list` | 浏览知识库文档列表 | SQLite (metadata.db) |

## 工作流程

### 流程 A：知识检索

示例输入：`"华为交换机OSPF邻居关系断开的排查方法"`

**步骤：**

1. **理解用户意图**：识别为知识检索需求
   - 关键词：OSPF、邻居断开、华为交换机
   - 隐含过滤：device_vendor=huawei, device_type=switch

2. **调用知识检索**：
   ```
   knowledge_search(query="华为交换机OSPF邻居关系断开排查", device_vendor="huawei", top_k=5)
   ```

3. **整合回复**：将检索结果按相关性整理后回复用户

### 流程 B：文档入库

示例输入：`"把这个SOP文档加到知识库里"`

**步骤：**

1. **确认文档信息**：
   - 文件路径（用户指定或从上下文获取）
   - 文档类型：sop / fault / emergency / solution / event
   - 标题
   - 可选：设备厂商、设备类型

2. **调用入库工具**：
   ```
   knowledge_upload(
       file_path="docs/ops-knowledge/raw/SOP/02网络SOP/OSPF配置规范.docx",
       doc_type="sop",
       title="OSPF配置规范",
       device_vendor="huawei"
   )
   ```

3. **确认结果**：告知用户入库状态和chunk数量

### 流程 C：浏览知识库

示例输入：`"知识库里有哪些故障案例？"`

**步骤：**

1. **调用浏览工具**：
   ```
   knowledge_list(doc_type="fault", limit=20)
   ```

2. **展示结果**：列出文档标题、类型、上传日期

### 流程 D：混合查询

用户可能在检索后要求上传新文档，或在浏览后进行检索。按需组合上述流程。

## 语义理解要点

- "怎么处理XX故障" → knowledge_search(query="XX故障处理")
- "有没有XX的SOP" → knowledge_search(query="XX操作流程", doc_type="sop")
- "应急预案在哪" → knowledge_search(query="应急预案", doc_type="emergency")
- "把这个文件加进去" → knowledge_upload(...)
- "库里有什么" → knowledge_list()
- "华为相关的故障" → knowledge_search(query="故障", device_vendor="huawei")

## 注意事项

- 文档入库时自动去重：同hash跳过，同标题覆盖更新
- 支持6种文件格式：pdf、docx、xlsx、txt、md、csv
- 检索支持元数据过滤：doc_type、device_vendor、device_type
- 知识库与带宽管理系统相互隔离，使用独立的ChromaDB collection和SQLite数据库
