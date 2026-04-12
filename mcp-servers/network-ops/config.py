"""Network Ops MCP Server configuration."""

import os
from dataclasses import dataclass


@dataclass
class MySQLConfig:
    host: str = "host.docker.internal"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "iteams_db"


@dataclass
class SQLiteConfig:
    db_path: str = ".deer-flow/db/network_ops.db"


@dataclass
class ChromaConfig:
    persist_dir: str = ".deer-flow/vectors/bandwidth_policy"
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "qwen3-embedding:0.6b"
    collection_name: str = "bandwidth_policy"
    md_path: str = "docs/bandwidth.md"


@dataclass
class RerankerConfig:
    """Configuration for the cross-encoder reranker model.

    Change `model_name` to swap reranker — no code changes needed.
    Set `enabled = False` to disable reranking (fallback to pure vector search).
    """

    enabled: bool = True
    model_name: str = "Qwen/Qwen3-Reranker-0.6B"
    device: str = "cpu"
    max_length: int = 512
    # Over-retrieve from vector store, then rerank down to top_k
    retrieval_multiplier: int = 3


@dataclass
class ServerConfig:
    mysql: MySQLConfig = None
    sqlite: SQLiteConfig = None
    chroma: ChromaConfig = None
    reranker: RerankerConfig = None

    def __post_init__(self):
        if self.mysql is None:
            self.mysql = MySQLConfig(
                host=os.getenv("MYSQL_HOST", "host.docker.internal"),
                port=int(os.getenv("MYSQL_PORT", "3306")),
                user=os.getenv("MYSQL_USER", "root"),
                password=os.getenv("MYSQL_PASSWORD", ""),
                database=os.getenv("MYSQL_DATABASE", "iteams_db"),
            )
        if self.sqlite is None:
            self.sqlite = SQLiteConfig(
                db_path=os.getenv("SQLITE_DB_PATH", ".deer-flow/db/network_ops.db"),
            )
        if self.chroma is None:
            self.chroma = ChromaConfig(
                persist_dir=os.getenv(
                    "CHROMA_PERSIST_DIR", ".deer-flow/vectors/bandwidth_policy"
                ),
                ollama_base_url=os.getenv(
                    "OLLAMA_BASE_URL", "http://host.docker.internal:11434"
                ),
                ollama_model=os.getenv("OLLAMA_EMBED_MODEL", "qwen3-embedding:0.6b"),
                collection_name=os.getenv("CHROMA_COLLECTION", "bandwidth_policy"),
                md_path=os.getenv("BANDWIDTH_MD_PATH", "docs/bandwidth.md"),
            )
        if self.reranker is None:
            self.reranker = RerankerConfig(
                enabled=os.getenv("RERANKER_ENABLED", "true").lower() == "true",
                model_name=os.getenv("RERANKER_MODEL", "Qwen/Qwen3-Reranker-0.6B"),
                device=os.getenv("RERANKER_DEVICE", "cpu"),
                max_length=int(os.getenv("RERANKER_MAX_LENGTH", "512")),
                retrieval_multiplier=int(
                    os.getenv("RERANKER_RETRIEVAL_MULTIPLIER", "3")
                ),
            )


def get_config() -> ServerConfig:
    return ServerConfig()
