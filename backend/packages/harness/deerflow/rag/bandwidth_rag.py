"""Bandwidth policy RAG implementation.

This module provides RAG capabilities for bandwidth policy queries.
It embeds bandwidth tier information and retrieves relevant policies
based on user queries about current bandwidth and traffic.
"""

import logging
from pathlib import Path
from typing import Optional

from langchain_chroma import Chroma
from langchain.schema import Document

logger = logging.getLogger(__name__)

# Bandwidth tier data extracted from bandwidth.md
# Each tier is stored as a natural language description for better semantic search
BANDWIDTH_TIERS = [
    {
        "current_bw": "2 Mbps",
        "scale_up_threshold": "0.8 Mbps (40%)",
        "scale_up_target": "4 Mbps",
        "scale_down_threshold": "-",
        "scale_down_target": "-",
        "description": "2 Mbps是当前最低配置带宽档位。当P95流量超过0.8 Mbps（即40%利用率）时，需要扩容到4 Mbps。此档位不支持缩容，维持最低配置。",
    },
    {
        "current_bw": "4 Mbps",
        "scale_up_threshold": "1.6 Mbps (40%)",
        "scale_up_target": "6 Mbps",
        "scale_down_threshold": "0.7 Mbps (35% of 2 Mbps)",
        "scale_down_target": "2 Mbps",
        "description": "4 Mbps带宽档位。当P95流量超过1.6 Mbps时扩容到6 Mbps；当流量低于0.7 Mbps时缩容到2 Mbps。",
    },
    {
        "current_bw": "6 Mbps",
        "scale_up_threshold": "2.4 Mbps (40%)",
        "scale_up_target": "8 Mbps",
        "scale_down_threshold": "1.4 Mbps (35% of 4 Mbps)",
        "scale_down_target": "4 Mbps",
        "description": "6 Mbps带宽档位。当P95流量超过2.4 Mbps时扩容到8 Mbps；当流量低于1.4 Mbps时缩容到4 Mbps。",
    },
    {
        "current_bw": "8 Mbps",
        "scale_up_threshold": "3.2 Mbps (40%)",
        "scale_up_target": "10 Mbps",
        "scale_down_threshold": "2.1 Mbps (35% of 6 Mbps)",
        "scale_down_target": "6 Mbps",
        "description": "8 Mbps带宽档位。当P95流量超过3.2 Mbps时扩容到10 Mbps；当流量低于2.1 Mbps时缩容到6 Mbps。",
    },
    {
        "current_bw": "10 Mbps",
        "scale_up_threshold": "4.0 Mbps (40%)",
        "scale_up_target": "20 Mbps",
        "scale_down_threshold": "2.8 Mbps (35% of 8 Mbps)",
        "scale_down_target": "8 Mbps",
        "description": "10 Mbps带宽档位。当P95流量超过4.0 Mbps时扩容到20 Mbps（跳档扩容）；当流量低于2.8 Mbps时缩容到8 Mbps。",
    },
    {
        "current_bw": "20 Mbps",
        "scale_up_threshold": "8.0 Mbps (40%)",
        "scale_up_target": "30 Mbps",
        "scale_down_threshold": "3.5 Mbps (35% of 10 Mbps)",
        "scale_down_target": "10 Mbps",
        "description": "20 Mbps带宽档位。当P95流量超过8.0 Mbps时扩容到30 Mbps；当流量低于3.5 Mbps时缩容到10 Mbps。",
    },
    {
        "current_bw": "30 Mbps",
        "scale_up_threshold": "12.0 Mbps (40%)",
        "scale_up_target": "40 Mbps",
        "scale_down_threshold": "7.0 Mbps (35% of 20 Mbps)",
        "scale_down_target": "20 Mbps",
        "description": "30 Mbps带宽档位。当P95流量超过12.0 Mbps时扩容到40 Mbps；当流量低于7.0 Mbps时缩容到20 Mbps。",
    },
    {
        "current_bw": "40 Mbps",
        "scale_up_threshold": "16.0 Mbps (40%)",
        "scale_up_target": "50 Mbps",
        "scale_down_threshold": "10.5 Mbps (35% of 30 Mbps)",
        "scale_down_target": "30 Mbps",
        "description": "40 Mbps带宽档位。当P95流量超过16.0 Mbps时扩容到50 Mbps；当流量低于10.5 Mbps时缩容到30 Mbps。",
    },
]


class BandwidthRAG:
    """RAG system for bandwidth policy queries."""

    def __init__(
        self,
        persist_dir: str = ".deer-flow/vectors/bandwidth_policy",
        ollama_base_url: str = "http://host.docker.internal:11434",
    ):
        self.persist_dir = Path(persist_dir)
        self.ollama_base_url = ollama_base_url
        self._vectorstore: Optional[Chroma] = None

    def _get_embeddings(self):
        """Get Ollama embeddings for bge-m3."""
        try:
            from langchain_ollama import OllamaEmbeddings

            return OllamaEmbeddings(
                model="bge-m3",
                base_url=self.ollama_base_url,
            )
        except ImportError:
            logger.error("langchain-ollama not installed. Run: uv add langchain-ollama")
            raise

    def initialize(self, force_rebuild: bool = False) -> "BandwidthRAG":
        """Initialize the vector store with bandwidth policy documents.

        Args:
            force_rebuild: If True, rebuild the vector store even if it exists.

        Returns:
            Self for chaining.
        """
        if self._vectorstore is not None and not force_rebuild:
            return self

        # Check if vector store already exists
        if self.persist_dir.exists() and not force_rebuild:
            logger.info(f"Loading existing bandwidth policy vector store from {self.persist_dir}")
            self._vectorstore = Chroma(
                collection_name="bandwidth_policy",
                embedding_function=self._get_embeddings(),
                persist_directory=str(self.persist_dir),
            )
            return self

        # Build documents from bandwidth tiers
        logger.info("Building bandwidth policy vector store...")
        documents = []

        for tier in BANDWIDTH_TIERS:
            # Create rich text description for embedding
            page_content = tier["description"]

            # Create metadata for filtering and display
            metadata = {
                "current_bw": tier["current_bw"],
                "scale_up_threshold": tier["scale_up_threshold"],
                "scale_up_target": tier["scale_up_target"],
                "scale_down_threshold": tier["scale_down_threshold"],
                "scale_down_target": tier["scale_down_target"],
                "bw_numeric": self._parse_bw_value(tier["current_bw"]),
            }

            doc = Document(page_content=page_content, metadata=metadata)
            documents.append(doc)

        # Create vector store
        self.persist_dir.parent.mkdir(parents=True, exist_ok=True)
        self._vectorstore = Chroma.from_documents(
            documents=documents,
            embedding=self._get_embeddings(),
            collection_name="bandwidth_policy",
            persist_directory=str(self.persist_dir),
        )

        logger.info(f"Bandwidth policy vector store created at {self.persist_dir}")
        return self

    @staticmethod
    def _parse_bw_value(bw_str: str) -> int:
        """Parse bandwidth string like '10 Mbps' to numeric value 10."""
        return int(bw_str.split()[0])

    def query(
        self,
        current_bw: Optional[str] = None,
        current_traffic: Optional[float] = None,
        query_text: Optional[str] = None,
        k: int = 3,
    ) -> list[dict]:
        """Query bandwidth policies.

        Args:
            current_bw: Current bandwidth tier, e.g., "10 Mbps"
            current_traffic: Current traffic in Mbps
            query_text: Natural language query (alternative to structured params)
            k: Number of results to return

        Returns:
            List of matching policy documents with scores
        """
        if self._vectorstore is None:
            self.initialize()

        # Build query text
        if query_text:
            search_query = query_text
        else:
            search_parts = []
            if current_bw:
                search_parts.append(f"当前带宽{current_bw}")
            if current_traffic is not None:
                search_parts.append(f"当前流量{current_traffic} Mbps")
            search_query = "，".join(search_parts) or "带宽策略"

        # Search vector store
        results = self._vectorstore.similarity_search_with_score(search_query, k=k)

        # Format results
        formatted = []
        for doc, score in results:
            formatted.append({
                "current_bw": doc.metadata["current_bw"],
                "scale_up_threshold": doc.metadata["scale_up_threshold"],
                "scale_up_target": doc.metadata["scale_up_target"],
                "scale_down_threshold": doc.metadata["scale_down_threshold"],
                "scale_down_target": doc.metadata["scale_down_target"],
                "description": doc.page_content,
                "relevance_score": round(1 - score, 4),  # Convert distance to similarity
            })

        return formatted

    def get_recommendation(
        self,
        current_bw: str,
        current_traffic: float,
    ) -> dict:
        """Get bandwidth recommendation based on current state.

        Args:
            current_bw: Current bandwidth tier, e.g., "10 Mbps"
            current_traffic: Current traffic in Mbps

        Returns:
            Recommendation including action, target bandwidth, and reasoning
        """
        # First, find the exact tier for current bandwidth
        current_tier = None
        for tier in BANDWIDTH_TIERS:
            if tier["current_bw"] == current_bw:
                current_tier = tier
                break

        if not current_tier:
            # Fallback to RAG search
            results = self.query(current_bw=current_bw, current_traffic=current_traffic, k=1)
            if not results:
                return {
                    "action": "unknown",
                    "reasoning": f"未找到带宽档位 {current_bw} 的配置信息",
                }
            best_match = results[0]
        else:
            best_match = {
                "current_bw": current_tier["current_bw"],
                "scale_up_threshold": current_tier["scale_up_threshold"],
                "scale_up_target": current_tier["scale_up_target"],
                "scale_down_threshold": current_tier["scale_down_threshold"],
                "scale_down_target": current_tier["scale_down_target"],
            }

        # Parse thresholds
        scale_up_threshold = self._extract_threshold(best_match["scale_up_threshold"])
        scale_down_threshold = self._extract_threshold(best_match["scale_down_threshold"])

        # Determine action
        if scale_up_threshold and current_traffic > scale_up_threshold:
            return {
                "action": "scale_up",
                "current_bw": current_bw,
                "current_traffic_mbps": current_traffic,
                "threshold_mbps": scale_up_threshold,
                "target_bw": best_match["scale_up_target"],
                "reasoning": f"当前流量 {current_traffic} Mbps 超过扩容阈值 {scale_up_threshold} Mbps，建议扩容到 {best_match['scale_up_target']}",
            }
        elif scale_down_threshold and current_traffic < scale_down_threshold:
            return {
                "action": "scale_down",
                "current_bw": current_bw,
                "current_traffic_mbps": current_traffic,
                "threshold_mbps": scale_down_threshold,
                "target_bw": best_match["scale_down_target"],
                "reasoning": f"当前流量 {current_traffic} Mbps 低于缩容阈值 {scale_down_threshold} Mbps，建议缩容到 {best_match['scale_down_target']}",
            }
        else:
            return {
                "action": "maintain",
                "current_bw": current_bw,
                "current_traffic_mbps": current_traffic,
                "reasoning": f"当前流量 {current_traffic} Mbps 在合理范围内，维持当前带宽 {current_bw} 配置",
            }

    @staticmethod
    def _extract_threshold(threshold_str: str) -> Optional[float]:
        """Extract numeric threshold from string like '1.6 Mbps (40%)'."""
        if not threshold_str or threshold_str == "-":
            return None
        try:
            # Extract first number from string
            parts = threshold_str.split()
            return float(parts[0])
        except (ValueError, IndexError):
            return None


# Global instance for reuse
_bandwidth_rag_instance: Optional[BandwidthRAG] = None


def get_bandwidth_rag() -> BandwidthRAG:
    """Get singleton BandwidthRAG instance."""
    global _bandwidth_rag_instance
    if _bandwidth_rag_instance is None:
        _bandwidth_rag_instance = BandwidthRAG().initialize()
    return _bandwidth_rag_instance
