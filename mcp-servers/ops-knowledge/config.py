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
class ServerConfig:
    sqlite: SQLiteConfig = None
    chroma: ChromaConfig = None

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


def get_config() -> ServerConfig:
    return ServerConfig()
