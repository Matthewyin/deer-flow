"""Ops Knowledge MCP Server configuration."""

import os
from dataclasses import dataclass


@dataclass
class SQLiteConfig:
    db_path: str = ".deer-flow/db/ops_knowledge.db"


@dataclass
class ChromaConfig:
    persist_dir: str = ".deer-flow/vectors/ops_knowledge"
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "bge-m3:567m"
    collection_name: str = "ops_knowledge"
    raw_dir: str = "docs/ops-knowledge/raw"


@dataclass
class RerankerConfig:
    """Configuration for the cross-encoder reranker model.

    Change `model_name` to swap reranker — no code changes needed.
    Set `enabled = False` to disable reranking (fallback to pure vector search).
    """

    enabled: bool = True
    model_name: str = "BAAI/bge-reranker-v2-m3"
    device: str = "cpu"
    max_length: int = 512
    retrieval_multiplier: int = 3


@dataclass
class ServerConfig:
    sqlite: SQLiteConfig = None
    chroma: ChromaConfig = None
    reranker: RerankerConfig = None

    def __post_init__(self):
        if self.sqlite is None:
            self.sqlite = SQLiteConfig(
                db_path=os.getenv(
                    "OPS_KNOWLEDGE_DB_PATH", ".deer-flow/db/ops_knowledge.db"
                ),
            )
        if self.chroma is None:
            self.chroma = ChromaConfig(
                persist_dir=os.getenv(
                    "CHROMA_PERSIST_DIR", ".deer-flow/vectors/ops_knowledge"
                ),
                ollama_base_url=os.getenv(
                    "OLLAMA_BASE_URL", "http://host.docker.internal:11434"
                ),
                ollama_model=os.getenv("OLLAMA_EMBED_MODEL", "bge-m3:567m"),
                collection_name=os.getenv("CHROMA_COLLECTION", "ops_knowledge"),
                raw_dir=os.getenv("OPS_KNOWLEDGE_RAW_DIR", "docs/ops-knowledge/raw"),
            )
        if self.reranker is None:
            self.reranker = RerankerConfig(
                enabled=os.getenv("RERANKER_ENABLED", "true").lower() == "true",
                model_name=os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"),
                device=os.getenv("RERANKER_DEVICE", "cpu"),
                max_length=int(os.getenv("RERANKER_MAX_LENGTH", "512")),
                retrieval_multiplier=int(
                    os.getenv("RERANKER_RETRIEVAL_MULTIPLIER", "3")
                ),
            )


def get_config() -> ServerConfig:
    return ServerConfig()
