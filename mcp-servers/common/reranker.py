"""Qwen3-style generative reranker wrapper.

Adapted from the official Qwen3-Embedding repo:
  examples/qwen3_reranker_transformers.py

This module is config-driven: change `model_name` in RerankerConfig
to swap models without touching any code.
"""

import logging
from typing import List, Tuple

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

logger = logging.getLogger(__name__)

_YES_TOKEN = "yes"
_NO_TOKEN = "no"
_PREFIX = (
    "<|im_start|>system\n"
    "Judge whether the Document meets the requirements based on the Query "
    'and the Instruct provided. Note that the answer can only be "yes" or '
    '"no".<|im_end|>\n'
    "<|im_start|>user\n"
)
_SUFFIX = "<|im_end|>\n<|im_start|>assistant\n<think:\n\n</think:>\n\n"
_DEFAULT_INSTRUCTION = "Given the user query, retrieval the relevant passages"


class Reranker:
    """Lazy-loading generative reranker (Qwen3-Reranker family)."""

    def __init__(
        self,
        model_name: str,
        device: str = "cpu",
        max_length: int = 512,
        instruction: str = _DEFAULT_INSTRUCTION,
    ):
        self._model_name = model_name
        self._device = device
        self._max_length = max_length
        self._instruction = instruction
        self._lm = None
        self._tokenizer = None
        self._prefix_tokens = None
        self._suffix_tokens = None
        self._token_true_id = None
        self._token_false_id = None

    def _ensure_loaded(self):
        if self._lm is not None:
            return

        logger.info(
            "Loading reranker model: %s (device=%s)", self._model_name, self._device
        )

        self._tokenizer = AutoTokenizer.from_pretrained(
            self._model_name,
            trust_remote_code=True,
            padding_side="left",
        )

        dtype = torch.float16 if self._device != "cpu" else torch.float32
        device_map = self._device if self._device in ("cuda", "mps") else None

        self._lm = AutoModelForCausalLM.from_pretrained(
            self._model_name,
            trust_remote_code=True,
            dtype=dtype,
            device_map=device_map,
        ).eval()

        if device_map is None:
            self._lm = self._lm.to(self._device)

        self._token_true_id = self._tokenizer.convert_tokens_to_ids(_YES_TOKEN)
        self._token_false_id = self._tokenizer.convert_tokens_to_ids(_NO_TOKEN)
        self._prefix_tokens = self._tokenizer.encode(_PREFIX, add_special_tokens=False)
        self._suffix_tokens = self._tokenizer.encode(_SUFFIX, add_special_tokens=False)

        logger.info("Reranker model loaded successfully")

    def _format_pair(self, query: str, doc: str, instruction: str) -> str:
        inst = instruction or self._instruction
        return f"<Instruct>: {inst}\n<Query>: {query}\n<Document>: {doc}"

    def _tokenize_pairs(self, pairs_text: List[str]) -> dict:
        max_content = (
            self._max_length - len(self._prefix_tokens) - len(self._suffix_tokens)
        )
        out = self._tokenizer(
            pairs_text,
            padding=False,
            truncation="longest_first",
            return_attention_mask=False,
            max_length=max_content,
        )
        for i in range(len(out["input_ids"])):
            out["input_ids"][i] = (
                self._prefix_tokens + out["input_ids"][i] + self._suffix_tokens
            )
        out = self._tokenizer.pad(
            out, padding=True, return_tensors="pt", max_length=self._max_length
        )
        return {k: v.to(self._lm.device) for k, v in out.items()}

    @torch.no_grad()
    def _score_batch(self, inputs: dict) -> List[float]:
        logits = self._lm(**inputs).logits[:, -1, :]
        true_v = logits[:, self._token_true_id]
        false_v = logits[:, self._token_false_id]
        stacked = torch.stack([false_v, true_v], dim=1)
        probs = torch.nn.functional.log_softmax(stacked, dim=1)
        return probs[:, 1].exp().tolist()

    def rerank(
        self,
        query: str,
        documents: List[str],
        instruction: str = None,
    ) -> List[Tuple[int, float]]:
        """Score (query, doc) pairs and return [(original_index, score), ...] sorted desc.

        Returns list sorted by score descending (most relevant first).
        """
        self._ensure_loaded()

        pairs_text = [self._format_pair(query, doc, instruction) for doc in documents]

        inputs = self._tokenize_pairs(pairs_text)
        scores = self._score_batch(inputs)

        indexed = list(enumerate(scores))
        indexed.sort(key=lambda x: x[1], reverse=True)
        return indexed
