"""knowledge_list tool: browse and filter ops-knowledge documents."""

import logging
from typing import Optional

from config import get_config
from db.metadata_client import MetadataClient

logger = logging.getLogger(__name__)

_db: Optional[MetadataClient] = None


def _get_db() -> MetadataClient:
    global _db
    if _db is None:
        cfg = get_config()
        _db = MetadataClient(db_path=cfg.sqlite.db_path)
    return _db


def register(mcp):
    @mcp.tool()
    def knowledge_list(
        doc_type: Optional[str] = None,
        device_vendor: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        """
        浏览知识库中的文档列表。支持按类型和厂商过滤，分页查询。

        Args:
            doc_type: 按文档类型过滤（可选）: fault, sop, emergency, solution, event
            device_vendor: 按设备厂商过滤（可选）: huawei, h3c, hillstone, f5 等
            limit: 每页数量（默认20）
            offset: 偏移量（默认0）

        Returns:
            dict: 包含 documents 列表和 total 总数
        """
        db = _get_db()
        documents = db.list_documents(
            doc_type=doc_type,
            device_vendor=device_vendor,
            limit=limit,
            offset=offset,
        )
        total = db.count_documents(doc_type=doc_type)
        return {
            "documents": documents,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
