"""
Implement a local Sentence-Transformers embedding backend using a small,
fast default model suitable for running on CPU by default.
"""

from __future__ import annotations

import logging
from profiler_assistant.rag.embeddings import DEFAULT_ST_MODEL
from time import perf_counter
from typing import List

import numpy as np


class LocalSTBackend:
    MODEL_ID = DEFAULT_ST_MODEL
    BATCH = 32
    # all-MiniLM-L6-v2 is 384-d. We'll confirm on first call and log it.
    _KNOWN_DIM = 384

    def __init__(self, logger: logging.Logger | None = None):
        self.log = logger or logging.getLogger(__name__)
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except Exception as e:
            self.log.error(
                "Local embedding backend requires 'sentence-transformers'. "
                "Install it or set FPA_EMBED_BACKEND=dummy. Error: %s",
                e,
            )
            raise
        self.model = SentenceTransformer(self.MODEL_ID)
        self._dim: int | None = None
        self.log.info("embedding_backend=local model=%s", self.MODEL_ID)

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        n = len(texts)
        if n == 0:
            # If dimension unknown yet, return 0xKNOWN_DIM for this model
            dim = self._dim or self._KNOWN_DIM
            return np.empty((0, dim), dtype=np.float32)

        out_batches: list[np.ndarray] = []

        total_batches = (n + self.BATCH - 1) // self.BATCH
        seen = 0
        for b in range(total_batches):
            start = b * self.BATCH
            end = min(start + self.BATCH, n)
            batch_texts = texts[start:end]

            t0 = perf_counter()
            batch = self.model.encode(
                batch_texts,
                batch_size=self.BATCH,
                convert_to_numpy=True,
                normalize_embeddings=False,
                show_progress_bar=False,
            )
            dt = perf_counter() - t0

            if not isinstance(batch, np.ndarray):
                batch = np.asarray(batch)

            if self._dim is None:
                self._dim = int(batch.shape[1])
                self.log.info("embedding_dim=%d batches=%d", self._dim, total_batches)

            self.log.debug("local.batch %d/%d size=%d elapsed=%.3fs", b + 1, total_batches, end - start, dt)
            out_batches.append(batch.astype(np.float32, copy=False))
            seen += (end - start)

        result = np.vstack(out_batches)
        # Defensive: ensure we preserved order and counts
        if result.shape[0] != n:
            self.log.error("Embedding count mismatch: expected=%d got=%d", n, result.shape[0])
        self.log.debug("local.embed_texts done n=%d shape=%s", n, tuple(result.shape))
        return result
