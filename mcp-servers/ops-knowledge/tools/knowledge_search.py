"""knowledge_search tool: semantic search across ops-knowledge RAG."""

import logging
from typing import Optional

from config import get_config
from rag.ops_knowledge_rag import OpsKnowledgeRAG

logger = logging.getLogger(__name__)

_rag: Optional[OpsKnowledgeRAG] = None


def _get_rag() -> OpsKnowledgeRAG:
    global _rag
    if _rag is None:
        cfg = get_config()
        _rag = OpsKnowledgeRAG(
            persist_dir=cfg.chroma.persist_dir,
            ollama_base_url=cfg.chroma.ollama_base_url,
            ollama_model=cfg.chroma.ollama_model,
            collection_name=cfg.chroma.collection_name,
        )
        _rag.initialize()
    return _rag


def register(mcp):
    @mcp.tool()
    def knowledge_search(
        query: str,
        doc_type: Optional[str] = None,
        device_vendor: Optional[str] = None,
        device_type: Optional[str] = None,
        top_k: int = 5,
    ) -> list[dict]:
        """
        搜索运维知识库。支持语义搜索和元数据过滤。
        用于查找：故障案例、SOP流程、应急预案、解决方案、事件记录。

        Args:
            query: 搜索查询，自然语言描述
            doc_type: 按文档类型过滤（可选）: fault, sop, emergency, solution, event
            device_vendor: 按设备厂商过滤（可选）: huawei, h3c, hillstone, f5 等
            device_type: 按设备类型过滤（可选）: router, switch, firewall, load_balancer
            top_k: 返回结果数量（默认5）

        Returns:
            list[dict]: 匹配的文档片段列表，每条包含 content, metadata, score
        """
        rag = _get_rag()
        return rag.query(
            query_text=query,
            doc_type=doc_type,
            device_vendor=device_vendor,
            device_type=device_type,
            top_k=top_k,
        )
