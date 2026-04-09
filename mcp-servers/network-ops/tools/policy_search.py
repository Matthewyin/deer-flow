import logging
from fastmcp import FastMCP
from rag.bandwidth_rag import BandwidthRAG
from config import get_config

# Initialize logger
logger = logging.getLogger(__name__)

# Singleton for BandwidthRAG
_rag = None


def _get_rag():
    """Lazily initializes and returns the BandwidthRAG instance."""
    global _rag
    if _rag is None:
        config = get_config()
        _rag = BandwidthRAG(
            persist_dir=config.chroma.persist_dir,
            ollama_base_url=config.chroma.ollama_base_url,
            ollama_model=config.chroma.ollama_model,
            collection_name=config.chroma.collection_name,
            md_path=config.chroma.md_path,
        )
        _rag.initialize()
    return _rag


def register(mcp: FastMCP):
    """Registers the policy_search tool with the FastMCP instance."""

    @mcp.tool()
    def policy_search(query: str, k: int = 3) -> list[dict]:
        """
        搜索带宽策略文档（docs/bandwidth.md）。按语义相似度返回匹配的章节。
        用于查找：操作流程、阈值规则、角色职责、邮件模板格式等。
        当需要了解具体策略细节时调用此工具，而不是硬编码规则。

        Args:
            query: 搜索查询，如 "扩容操作流程"、"带宽阈值标准"、"缩容邮件模板"、"应急扩容条件"
            k: 返回结果数量（默认3）

        Returns:
            list[dict]: 匹配的文档章节列表，每条包含 section (标题), content (内容), score (相关度)
        """
        rag = _get_rag()
        return rag.query(query, k=k)
