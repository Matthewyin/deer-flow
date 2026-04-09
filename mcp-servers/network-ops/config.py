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
    md_path: str = "docs/bandwidth.md"


@dataclass
class ServerConfig:
    mysql: MySQLConfig = None
    sqlite: SQLiteConfig = None
    chroma: ChromaConfig = None

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
                md_path=os.getenv("BANDWIDTH_MD_PATH", "docs/bandwidth.md"),
            )


def get_config() -> ServerConfig:
    return ServerConfig()
