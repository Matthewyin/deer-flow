"""Management endpoints for RAG rebuild operations."""

import logging
import os
import shutil
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/management", tags=["management"])


class RebuildResponse(BaseModel):
    """Response model for RAG rebuild operations."""

    success: bool = Field(description="Whether the rebuild operation succeeded")
    message: str = Field(description="Human-readable status message")
    details: dict = Field(default_factory=dict, description="Additional details about the operation")


def _import_bandwidth_rag():
    """Import BandwidthRAG from the network-ops MCP server.

    Handles directory naming: mcp-servers uses hyphens (network-ops),
    Python needs underscores. We add the rag/ directory directly to sys.path.
    """
    project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    rag_path = str(project_root / "mcp-servers" / "network-ops" / "rag")
    if rag_path not in sys.path:
        sys.path.insert(0, rag_path)
    from bandwidth_rag import BandwidthRAG  # noqa: E402
    return BandwidthRAG


def _get_persist_dir_from_env(default: str) -> str:
    """Get persist_dir from CHROMA_PERSIST_DIR env var or use default."""
    persist_dir = os.getenv("CHROMA_PERSIST_DIR", default)
    if not Path(persist_dir).is_absolute():
        project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        persist_dir = str(project_root / persist_dir)
    return persist_dir


@router.post(
    "/rebuild-bandwidth-vectors",
    response_model=RebuildResponse,
    summary="Rebuild Bandwidth RAG Index",
    description="Force rebuild the bandwidth policy RAG vectorstore from source markdown.",
)
async def rebuild_bandwidth_vectors() -> RebuildResponse:
    """Rebuild the bandwidth policy RAG vectorstore.

    This endpoint:
    1. Deletes the existing vectorstore directory using shutil.rmtree
    2. Imports the BandwidthRAG class from the network-ops MCP server
    3. Calls initialize(force_rebuild=True) to rebuild the vectorstore from docs/bandwidth.md
    4. Returns success/failure status

    Configuration is read from environment variables:
    - CHROMA_PERSIST_DIR: Vector store directory (default: .deer-flow/vectors/bandwidth_policy)
    - OLLAMA_BASE_URL: Ollama API endpoint (default: http://host.docker.internal:11434)
    - OLLAMA_EMBED_MODEL: Embedding model (default: bge-m3:567m)
    - BANDWIDTH_MD_PATH: Source markdown file (default: docs/bandwidth.md)

    Returns:
        RebuildResponse with success status and message.

    Raises:
        HTTPException: 500 if the rebuild operation fails.
    """
    try:
        persist_dir = _get_persist_dir_from_env(".deer-flow/vectors/bandwidth_policy")
        ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        ollama_model = os.getenv("OLLAMA_EMBED_MODEL", "bge-m3:567m")
        collection_name = os.getenv("CHROMA_COLLECTION", "bandwidth_policy")

        project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        md_path = os.getenv("BANDWIDTH_MD_PATH", "docs/bandwidth.md")
        if not Path(md_path).is_absolute():
            md_path = str(project_root / md_path)

        if Path(persist_dir).exists():
            logger.info(f"Removing existing vectorstore at {persist_dir}")
            shutil.rmtree(persist_dir)

        bw_db = project_root / ".deer-flow" / "db" / "network_ops.db"
        if bw_db.exists():
            logger.info(f"Removing bandwidth tiers DB at {bw_db}")
            bw_db.unlink()

        BandwidthRAG = _import_bandwidth_rag()

        rag = BandwidthRAG(
            persist_dir=persist_dir,
            ollama_base_url=ollama_base_url,
            ollama_model=ollama_model,
            collection_name=collection_name,
            md_path=md_path,
        )

        rag.initialize(force_rebuild=True)

        logger.info("Bandwidth RAG vectorstore rebuilt successfully")
        return RebuildResponse(
            success=True,
            message="Bandwidth RAG vectorstore rebuilt successfully",
            details={
                "persist_dir": persist_dir,
                "md_path": md_path,
                "ollama_base_url": ollama_base_url,
                "ollama_model": ollama_model,
            },
        )

    except FileNotFoundError as e:
        logger.error(f"File not found during bandwidth RAG rebuild: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Required file not found: {str(e)}",
        ) from e
    except ImportError as e:
        logger.error(f"Failed to import BandwidthRAG: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to import BandwidthRAG module: {str(e)}",
        ) from e
    except Exception as e:
        logger.exception("Failed to rebuild bandwidth RAG vectorstore")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to rebuild bandwidth RAG: {str(e)}",
        ) from e


@router.post(
    "/rebuild-ops-knowledge-vectors",
    response_model=RebuildResponse,
    summary="Rebuild Ops Knowledge RAG Index",
    description="Force rebuild the ops-knowledge RAG vectorstore (clears existing index).",
)
async def rebuild_ops_knowledge_vectors() -> RebuildResponse:
    try:
        project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        persist_dir = _get_persist_dir_from_env(".deer-flow/vectors/ops_knowledge")

        if Path(persist_dir).exists():
            logger.info(f"Removing existing vectorstore at {persist_dir}")
            shutil.rmtree(persist_dir)

        ops_db = project_root / ".deer-flow" / "db" / "ops_knowledge.db"
        if ops_db.exists():
            logger.info(f"Removing metadata DB at {ops_db}")
            ops_db.unlink()
        ingest_script = str(project_root / "docs" / "batch_ingest_ops_knowledge.py")

        import subprocess

        venv_python = str(project_root / "backend" / ".venv" / "bin" / "python")
        python_bin = venv_python if Path(venv_python).exists() else shutil.which("python") or "python"

        result = subprocess.run(
            [python_bin, ingest_script],
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(project_root),
        )

        if result.returncode != 0:
            stderr_tail = result.stderr[-500:] if result.stderr else ""
            raise RuntimeError(f"Ingest script failed (rc={result.returncode}): {stderr_tail}")

        stdout_tail = result.stdout[-300:] if result.stdout else ""
        logger.info(f"Ops knowledge rebuild complete: {stdout_tail}")

        return RebuildResponse(
            success=True,
            message="Ops knowledge RAG vectorstore rebuilt and documents re-ingested",
            details={"persist_dir": persist_dir, "ingest_output": stdout_tail},
        )

    except ImportError as e:
        logger.error(f"Failed to import OpsKnowledgeRAG: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to import OpsKnowledgeRAG module: {str(e)}",
        ) from e
    except Exception as e:
        logger.exception("Failed to rebuild ops-knowledge RAG vectorstore")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to rebuild ops-knowledge RAG: {str(e)}",
        ) from e
