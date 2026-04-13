"""RAG client for ops-knowledge with doc_type-aware chunking."""

import logging
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _resolve_path(path_str: str) -> str:
    p = Path(path_str)
    if p.is_absolute():
        return str(p)
    return str(_PROJECT_ROOT / p)


# bge-m3:567m context 8192 tokens; Chinese ~1.5-2 chars/token
# Conservative: 2000 chars ensures no 400 errors even with mixed CJK/ASCII
MAX_CHUNK_CHARS = 2000


def _split_oversized(chunk: str, max_chars: int = MAX_CHUNK_CHARS) -> List[str]:
    if len(chunk) <= max_chars:
        return [chunk]

    parts = re.split(r"\n{2,}", chunk)
    result: List[str] = []
    buffer = ""
    for part in parts:
        if len(buffer) + len(part) + 2 <= max_chars:
            buffer = (buffer + "\n\n" + part).strip() if buffer else part.strip()
        else:
            if buffer:
                result.append(buffer)
                buffer = ""
            if len(part) > max_chars:
                sentences = re.split(r"(?<=[。！？\n.!?])\s*", part)
                sub_buf = ""
                for sent in sentences:
                    if len(sub_buf) + len(sent) <= max_chars:
                        sub_buf += sent
                    else:
                        if sub_buf:
                            result.append(sub_buf.strip())
                        sub_buf = sent
                        # Hard-split any single sentence still exceeding max_chars
                        while len(sub_buf) > max_chars:
                            result.append(sub_buf[:max_chars])
                            sub_buf = sub_buf[max_chars:]
                if sub_buf.strip():
                    result.append(sub_buf.strip())
            else:
                buffer = part.strip()
    if buffer.strip():
        result.append(buffer.strip())

    # Final safety: hard-split any remaining oversized chunks
    final: List[str] = []
    for r in result if result else [chunk[:max_chars]]:
        while len(r) > max_chars:
            final.append(r[:max_chars])
            r = r[max_chars:]
        final.append(r)
    return final


def _enforce_max_chunks(
    chunks: List[str], max_chars: int = MAX_CHUNK_CHARS
) -> List[str]:
    """Ensure no chunk exceeds max_chars by splitting oversized ones."""
    result: List[str] = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            result.append(chunk)
        else:
            result.extend(_split_oversized(chunk, max_chars))
    return result


def _chunk_by_headings(content: str, min_chunk_size: int = 100) -> List[str]:
    """Split content by markdown headings. Used for SOP docs."""
    parts = re.split(r"(?=^#{1,3}\s)", content, flags=re.MULTILINE)
    chunks: List[str] = []
    buffer = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(buffer) + len(part) < min_chunk_size:
            buffer = (buffer + "\n\n" + part).strip()
        else:
            if buffer:
                chunks.append(buffer)
            buffer = part
    if buffer.strip():
        chunks.append(buffer)
    return _enforce_max_chunks(chunks)


def _chunk_by_paragraphs(content: str, min_chunk_size: int = 100) -> List[str]:
    """Split content by double newlines, merge small chunks.

    Used for fault / event / solution docs.
    """
    raw = re.split(r"\n{2,}", content)
    chunks: List[str] = []
    buffer = ""
    for para in raw:
        para = para.strip()
        if not para:
            continue
        if len(buffer) + len(para) < min_chunk_size:
            buffer = (buffer + "\n\n" + para).strip()
        else:
            if buffer:
                chunks.append(buffer)
            buffer = para
    if buffer.strip():
        chunks.append(buffer)
    return _enforce_max_chunks(chunks)


def _chunk_whole(content: str) -> List[str]:
    """Return content as chunks, splitting if too long. Used for emergency plans."""
    stripped = content.strip()
    if not stripped:
        return []
    return _enforce_max_chunks([stripped])


def chunk_by_doc_type(content: str, doc_type: str) -> List[str]:
    strategies = {
        "fault": _chunk_by_paragraphs,
        "sop": _chunk_by_headings,
        "emergency": _chunk_whole,
        "emergency_system": _chunk_whole,
        "emergency_network": _chunk_whole,
        "emergency_security": _chunk_whole,
        "solution": _chunk_by_paragraphs,
        "event": _chunk_by_paragraphs,
    }
    chunker = strategies.get(doc_type, _chunk_by_paragraphs)
    return chunker(content)


class OpsKnowledgeRAG:
    """ChromaDB vector store client for ops-knowledge documents."""

    def __init__(
        self,
        persist_dir: str,
        ollama_base_url: str,
        ollama_model: str = "bge-m3:567m",
        collection_name: str = "ops_knowledge",
        reranker_enabled: bool = False,
        reranker_model: str = "",
        reranker_device: str = "cpu",
        reranker_max_length: int = 512,
        reranker_retrieval_multiplier: int = 3,
    ):
        self.persist_dir = _resolve_path(persist_dir)
        self.ollama_base_url = ollama_base_url
        self.ollama_model = ollama_model
        self.collection_name = collection_name
        self._vectorstore = None
        self._is_initialized = False

        self._reranker_enabled = reranker_enabled
        self._reranker_model = reranker_model
        self._reranker_device = reranker_device
        self._reranker_max_length = reranker_max_length
        self._reranker_multiplier = reranker_retrieval_multiplier
        self._reranker = None

    def initialize(self, force_rebuild: bool = False) -> "OpsKnowledgeRAG":
        """Initialize ChromaDB vectorstore (loads existing or creates empty)."""
        from langchain_chroma import Chroma
        from langchain_ollama import OllamaEmbeddings

        if self._is_initialized and not force_rebuild:
            return self

        embeddings = OllamaEmbeddings(
            model=self.ollama_model, base_url=self.ollama_base_url
        )

        if os.path.exists(self.persist_dir) and not force_rebuild:
            logger.info(f"Loading existing vectorstore from {self.persist_dir}")
            self._vectorstore = Chroma(
                persist_directory=self.persist_dir,
                embedding_function=embeddings,
                collection_name=self.collection_name,
            )
            self._is_initialized = True
            return self

        logger.info(f"Creating new vectorstore at {self.persist_dir}")
        from langchain_core.documents import Document

        self._vectorstore = Chroma.from_documents(
            documents=[Document(page_content="__init__", metadata={"type": "init"})],
            embedding=embeddings,
            persist_directory=self.persist_dir,
            collection_name=self.collection_name,
        )
        self._vectorstore._collection.delete(where={"type": "init"})
        # Remove the init placeholder
        self._vectorstore._collection.delete(where={"type": "init"})

        self._is_initialized = True
        logger.info("Vectorstore initialized successfully")
        return self

    def _get_reranker(self):
        if self._reranker is not None:
            return self._reranker
        mcp_servers_path = str(Path(__file__).resolve().parent.parent.parent)
        if mcp_servers_path not in sys.path:
            sys.path.insert(0, mcp_servers_path)
        from common.reranker import Reranker

        self._reranker = Reranker(
            model_name=self._reranker_model,
            device=self._reranker_device,
            max_length=self._reranker_max_length,
        )
        return self._reranker

    def add_chunks(self, chunks: List[Dict]) -> int:
        """Add document chunks to vectorstore.

        Each chunk dict must have: content (str), metadata (dict).
        Returns count of chunks added.
        """
        if not self._is_initialized:
            self.initialize()

        from langchain_core.documents import Document

        documents = [
            Document(page_content=c["content"], metadata=c["metadata"]) for c in chunks
        ]
        self._vectorstore.add_documents(documents)
        logger.info(f"Added {len(documents)} chunks to vectorstore")
        return len(documents)

    def delete_chunks_by_doc_id(self, doc_id: str) -> int:
        """Delete all chunks belonging to a document. Returns count deleted."""
        if not self._is_initialized:
            return 0

        collection = self._vectorstore._collection
        result = collection.get(where={"doc_id": doc_id})
        chunk_ids = result["ids"]
        if chunk_ids:
            collection.delete(ids=chunk_ids)
            logger.info(f"Deleted {len(chunk_ids)} chunks for doc_id={doc_id}")
        return len(chunk_ids)

    def query(
        self,
        query_text: str,
        doc_type: Optional[str] = None,
        device_vendor: Optional[str] = None,
        device_type: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict]:
        """Semantic search with optional metadata filters and reranking."""
        if not self._is_initialized:
            self.initialize()

        where_filter = self._build_filter(doc_type, device_vendor, device_type)

        use_reranker = self._reranker_enabled and self._reranker_model
        retrieve_k = top_k * self._reranker_multiplier if use_reranker else top_k

        kwargs = {"k": retrieve_k}
        if where_filter:
            kwargs["filter"] = where_filter

        results = self._vectorstore.similarity_search_with_score(query_text, **kwargs)

        if use_reranker and len(results) > top_k:
            reranker = self._get_reranker()
            documents = [doc.page_content for doc, _ in results]
            ranked = reranker.rerank(query_text, documents)
            final = []
            for orig_idx, score in ranked[:top_k]:
                doc, _ = results[orig_idx]
                final.append(
                    {
                        "content": doc.page_content,
                        "metadata": doc.metadata,
                        "score": round(score, 4),
                        "reranked": True,
                    }
                )
            return final

        formatted = []
        for doc, score in results:
            formatted.append(
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": round(1 - score, 4),
                }
            )
        return formatted

    def count_chunks(self, doc_type: Optional[str] = None) -> int:
        """Count chunks in vectorstore, optionally filtered by doc_type."""
        if not self._is_initialized:
            return 0

        collection = self._vectorstore._collection
        if doc_type:
            result = collection.get(where={"doc_type": doc_type})
            return len(result["ids"])
        return collection.count()

    @staticmethod
    def _build_filter(
        doc_type: Optional[str],
        device_vendor: Optional[str],
        device_type: Optional[str],
    ) -> Optional[Dict]:
        """Build ChromaDB where filter from non-None params."""
        conditions = {}
        if doc_type:
            conditions["doc_type"] = doc_type
        if device_vendor:
            conditions["device_vendor"] = device_vendor
        if device_type:
            conditions["device_type"] = device_type

        if len(conditions) == 0:
            return None
        if len(conditions) == 1:
            return conditions
        return {"$and": [{k: v} for k, v in conditions.items()]}
