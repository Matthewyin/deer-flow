#!/usr/bin/env python3
"""Rebuild bandwidth policy vectorstore from docs/bandwidth.md.

Usage:
  python docs/rebuild_bandwidth_vectors.py
"""

import shutil
import sys
import time
from pathlib import Path

# Add mcp-servers to path (same pattern as batch_ingest_ops_knowledge.py)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
MCP_SERVERS = PROJECT_ROOT / "mcp-servers" / "network-ops"
sys.path.insert(0, str(MCP_SERVERS))

from config import get_config
from rag.bandwidth_rag import BandwidthRAG


def main():
    cfg = get_config()
    persist_dir = cfg.chroma.persist_dir
    md_path = cfg.chroma.md_path

    print(f"MD path: {md_path}")
    print(f"Persist dir: {persist_dir}")

    # Resolve relative paths
    if not Path(md_path).is_absolute():
        md_path = str(PROJECT_ROOT / md_path)
    if not Path(persist_dir).is_absolute():
        persist_dir = str(PROJECT_ROOT / persist_dir)

    # Check source file
    if not Path(md_path).exists():
        print(f"ERROR: Source file not found: {md_path}")
        sys.exit(1)

    # Delete existing vectorstore
    if Path(persist_dir).exists():
        print(f"Deleting existing vectorstore at {persist_dir}")
        shutil.rmtree(persist_dir)

    # Build vectorstore
    print("Building vectorstore...")
    start = time.time()
    rag = BandwidthRAG(
        persist_dir=persist_dir,
        ollama_base_url=cfg.chroma.ollama_base_url,
        ollama_model=cfg.chroma.ollama_model,
        collection_name=cfg.chroma.collection_name,
        md_path=md_path,
    )
    rag.initialize()
    elapsed = int(time.time() - start)

    count = rag._vectorstore._collection.count()
    print(f"Done: {count} chunks in {elapsed}s")
    sys.exit(0)


if __name__ == "__main__":
    main()