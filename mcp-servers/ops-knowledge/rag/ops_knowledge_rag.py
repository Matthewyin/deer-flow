"""RAG client for ops-knowledge with doc_type-aware chunking."""

import logging
import os
import re
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


# bge-m3:567m context ~8192 tokens; Chinese ~1.5 chars/token; safe upper bound ~6000 chars
MAX_CHUNK_CHARS = 6000


def _split_oversized(chunk: str, max_chars: int = MAX_CHUNK_CHARS) -> List[str]:
    """Split a single chunk that exceeds max_chars by paragraphs or sentences."""
    if len(chunk) <= max_chars:
        return [chunk]

    # Try splitting by double newlines first
    parts = re.split(r"\n{2,}", chunk)
    result: List[str] = []
    buffer = ""
    for part in parts:
        if len(buffer) + len(part) + 2 <= max_chars:
            buffer = (buffer + "\n\n" + part).strip() if buffer else part.strip()
        else:
            if buffer:
                result.append(buffer)
            # If a single part is still too large, split by sentences
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
                if sub_buf.strip():
                    result.append(sub_buf.strip())
            else:
                buffer = part.strip()
    if buffer.strip():
        result.append(buffer.strip())
    return result if result else [chunk[:max_chars]]


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
    """Dispatch to appropriate chunking strategy based on doc_type."""
    strategies = {
        "fault": _chunk_by_paragraphs,
        "sop": _chunk_by_headings,
        "emergency": _chunk_whole,
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
    ):
        self.persist_dir = _resolve_path(persist_dir)
        self.ollama_base_url = ollama_base_url
        self.ollama_model = ollama_model
        self.collection_name = collection_name
        self._vectorstore = None
        self._is_initialized = False

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
        """Semantic search with optional metadata filters."""
        if not self._is_initialized:
            self.initialize()

        where_filter = self._build_filter(doc_type, device_vendor, device_type)
        kwargs = {"k": top_k}
        if where_filter:
            kwargs["filter"] = where_filter

        results = self._vectorstore.similarity_search_with_score(query_text, **kwargs)

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
