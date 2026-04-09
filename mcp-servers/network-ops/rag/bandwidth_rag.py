import re
import os
import logging
from pathlib import Path
from typing import List, Dict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _resolve_path(path_str: str) -> str:
    p = Path(path_str)
    if p.is_absolute():
        return str(p)
    return str(_PROJECT_ROOT / p)


def _chunk_md(content: str) -> List[Dict[str, str]]:
    """
    Split markdown by section headers (digits or template names).
    """
    # Regex to split by headers:
    # 1. Start of line with digits (e.g., "1. 概述")
    # 2. Start of line with "模板" (e.g., "模板一：...")
    pattern = r"(?=^\d+\.\s|(?=^模板[一二三四]))"
    chunks = re.split(pattern, content, flags=re.MULTILINE)

    processed_chunks = []
    for chunk in chunks:
        chunk = chunk.strip()
        if len(chunk) < 20:
            continue

        # Extract section title (first line)
        lines = chunk.split("\n")
        section_title = lines[0].strip()
        # Clean title of numbering if possible
        section_title = re.sub(r"^\d+\.\s*", "", section_title)

        processed_chunks.append({"content": chunk, "section_title": section_title})

    if not processed_chunks:
        return [{"content": content, "section_title": "Full Document"}]

    return processed_chunks


class BandwidthRAG:
    def __init__(
        self, persist_dir: str, ollama_base_url: str, md_path: str = "docs/bandwidth.md"
    ):
        self.persist_dir = _resolve_path(persist_dir)
        self.ollama_base_url = ollama_base_url
        self.md_path = _resolve_path(md_path)
        self._vectorstore = None
        self._is_initialized = False

    def initialize(self, force_rebuild: bool = False) -> "BandwidthRAG":
        from langchain_ollama import OllamaEmbeddings
        from langchain_chroma import Chroma
        from langchain_core.documents import Document

        if self._is_initialized and not force_rebuild:
            return self

        embeddings = OllamaEmbeddings(
            model="bge-m3:567m", base_url=self.ollama_base_url
        )

        if os.path.exists(self.persist_dir) and not force_rebuild:
            logger.info(f"Loading existing vectorstore from {self.persist_dir}")
            self._vectorstore = Chroma(
                persist_directory=self.persist_dir,
                embedding_function=embeddings,
                collection_name="bandwidth_policy",
            )
            self._is_initialized = True
            return self

        logger.info(f"Building vectorstore from {self.md_path}")
        if not os.path.exists(self.md_path):
            logger.error(f"File not found: {self.md_path}")
            raise FileNotFoundError(f"Markdown file not found: {self.md_path}")

        with open(self.md_path, "r", encoding="utf-8") as f:
            content = f.read()

        chunks = _chunk_md(content)
        documents = [
            Document(
                page_content=chunk["content"],
                metadata={"source": self.md_path, "section": chunk["section_title"]},
            )
            for chunk in chunks
        ]

        self._vectorstore = Chroma.from_documents(
            documents=documents,
            embedding=embeddings,
            persist_directory=self.persist_dir,
            collection_name="bandwidth_policy",
        )

        self._is_initialized = True
        logger.info("Vectorstore initialized successfully")
        return self

    def query(self, query_text: str, k: int = 3) -> List[Dict]:
        if not self._is_initialized:
            self.initialize()

        results = self._vectorstore.similarity_search_with_score(query_text, k=k)

        formatted_results = []
        for doc, score in results:
            formatted_results.append(
                {
                    "section": doc.metadata.get("section", "Unknown"),
                    "content": doc.page_content,
                    "score": round(1 - score, 4),
                }
            )

        return formatted_results
