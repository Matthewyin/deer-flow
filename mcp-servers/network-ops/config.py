"""Network Ops MCP Server configuration."""

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


def _resolve_env_vars(value):
    """Recursively resolve $ENV_VAR references in config values."""
    if isinstance(value, str):
        if value.startswith("$"):
            resolved = os.getenv(value[1:])
            if resolved is None:
                raise ValueError(f"Environment variable {value[1:]} not found")
            return resolved
        return value
    elif isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_resolve_env_vars(item) for item in value]
    return value


def _load_llm_from_config_yaml(config_path: str) -> Optional[dict]:
    """Load first model config from deerflow's config.yaml.

    Reads config.yaml, resolves $ENV_VAR references, and returns
    the first model's api_key, base_url, and model name.

    Returns None if config.yaml cannot be read or has no models.
    """
    try:
        import yaml
    except ImportError:
        logger.warning("PyYAML not installed, cannot read config.yaml for LLM config")
        return None

    if not os.path.isfile(config_path):
        logger.warning(f"config.yaml not found at {config_path}")
        return None

    try:
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"Failed to read config.yaml: {e}")
        return None

    models = data.get("models", [])
    if not models:
        logger.warning("No models configured in config.yaml")
        return None

    first_model = models[0]
    try:
        resolved = _resolve_env_vars(first_model)
    except ValueError as e:
        logger.warning(f"Failed to resolve env vars in model config: {e}")
        return None

    api_key = resolved.get("api_key")
    if not api_key:
        logger.warning(
            f"No api_key in first model config ({resolved.get('name', 'unknown')})"
        )
        return None

    return {
        "model": resolved.get("model", resolved.get("name", "gpt-4o-mini")),
        "api_key": api_key,
        "base_url": resolved.get("api_base") or resolved.get("base_url"),
        "name": resolved.get("name", "unknown"),
    }


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
    ollama_model: str = "bge-m3:567m"
    collection_name: str = "bandwidth_policy"
    md_path: str = "docs/bandwidth.md"


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
    # Over-retrieve from vector store, then rerank down to top_k
    retrieval_multiplier: int = 3


@dataclass
class LLMConfig:
    """LLM configuration for NLP-powered tool features.

    Reads from deerflow's config.yaml (first model) and falls back to
    environment variables. This ensures the MCP server uses the same
    LLM provider the user selected in the deerflow UI.
    """

    model: str = ""
    api_key: str = ""
    base_url: Optional[str] = None

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Build LLMConfig: try config.yaml first, then env vars."""
        config_path = os.getenv("CONFIG_YAML_PATH", "/app/config.yaml")
        logger.info(f"Loading LLM config from {config_path}")

        # Priority 1: read from deerflow's config.yaml
        llm = _load_llm_from_config_yaml(config_path)
        if llm:
            logger.info(
                f"LLM config loaded from config.yaml: model={llm['name']} "
                f"(base_url={'set' if llm['base_url'] else 'default'})"
            )
            return cls(
                model=llm["model"],
                api_key=llm["api_key"],
                base_url=llm["base_url"],
            )

        # Priority 2: fall back to explicit env vars
        api_key = os.getenv("LLM_API_KEY", "")
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        base_url = os.getenv("LLM_BASE_URL")
        if api_key:
            logger.info(f"LLM config from env vars: model={model}")
            return cls(model=model, api_key=api_key, base_url=base_url)

        # No LLM available
        logger.warning(
            "No LLM config found — search_by_llm will fall back to keyword search. "
            "Set CONFIG_YAML_PATH or LLM_API_KEY to enable LLM-powered search."
        )
        return cls()


@dataclass
class ServerConfig:
    mysql: MySQLConfig = None
    sqlite: SQLiteConfig = None
    chroma: ChromaConfig = None
    reranker: RerankerConfig = None
    llm: LLMConfig = field(default_factory=LLMConfig)

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
                ollama_model=os.getenv("OLLAMA_EMBED_MODEL", "bge-m3:567m"),
                collection_name=os.getenv("CHROMA_COLLECTION", "bandwidth_policy"),
                md_path=os.getenv("BANDWIDTH_MD_PATH", "docs/bandwidth.md"),
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
        if not isinstance(self.llm, LLMConfig):
            self.llm = LLMConfig()


def get_config() -> ServerConfig:
    cfg = ServerConfig()
    cfg.llm = LLMConfig.from_env()
    return cfg
