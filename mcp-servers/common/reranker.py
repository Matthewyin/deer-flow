"""Cross-encoder reranker using FlagEmbedding (BAAI/bge-reranker family).

This module provides a config-driven reranker that wraps FlagReranker
from the FlagEmbedding library. Supports all BAAI cross-encoder models:
  - BAAI/bge-reranker-v2-m3  (multilingual, lightweight, recommended)
  - BAAI/bge-reranker-base   (Chinese + English)
  - BAAI/bge-reranker-large  (Chinese + English, better quality)

Change `model_name` in RerankerConfig to swap models without touching code.
Set `enabled = False` in config to disable reranking entirely.
"""

import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


class Reranker:
    """Lazy-loading cross-encoder reranker (BAAI bge-reranker family).

    Uses FlagEmbedding.FlagReranker under the hood, which loads a
    sequence-classification transformer and computes relevance scores
    for (query, document) pairs.
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        device: str = "cpu",
        max_length: int = 512,
    ):
        self._model_name = model_name
        self._device = device
        self._max_length = max_length
        self._reranker = None

    def _ensure_loaded(self):
        """Lazily load the model on first use to avoid startup penalty."""
        if self._reranker is not None:
            return

        logger.info(
            "Loading reranker model: %s (device=%s, max_length=%d)",
            self._model_name,
            self._device,
            self._max_length,
        )

        from FlagEmbedding import FlagReranker

        use_fp16 = self._device != "cpu"
        self._reranker = FlagReranker(
            self._model_name,
            use_fp16=use_fp16,
            device=self._device,
        )

        logger.info("Reranker model loaded successfully")

    def rerank(
        self,
        query: str,
        documents: List[str],
    ) -> List[Tuple[int, float]]:
        """Score (query, doc) pairs and return results sorted by relevance.

        Args:
            query: The search query text.
            documents: List of document texts to score against the query.

        Returns:
            List of (original_index, score) tuples sorted by score descending.
            Score is normalized to [0, 1] via sigmoid (higher = more relevant).
        """
        if not documents:
            return []

        self._ensure_loaded()

        # Build (query, doc) pairs for FlagReranker
        pairs = [[query, doc] for doc in documents]

        # compute_score returns a float (single pair) or list[float] (multiple)
        scores = self._reranker.compute_score(pairs, normalize=True)

        # Normalize single-pair return to list
        if isinstance(scores, (int, float)):
            scores = [float(scores)]

        # Pair with original indices and sort descending by score
        indexed = list(enumerate(scores))
        indexed.sort(key=lambda x: x[1], reverse=True)
        return indexed
