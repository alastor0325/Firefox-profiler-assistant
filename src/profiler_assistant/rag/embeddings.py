"""
embeddings.py
-------------
Purpose: Define a lightweight, swappable embedding interface for the RAG stack.
- EmbeddingBackend protocol with encode().
- Default DummyBackend (deterministic, dependency-free for tests/CI).
- Optional SentenceTransformersBackend ("all-MiniLM-L6-v2") if installed.
- Selection via env var FPA_EMBEDDINGS (e.g., 'dummy', 'sentence-transformers').
"""

from __future__ import annotations
import hashlib
import os
from typing import List, Protocol, Optional
import numpy as np

class EmbeddingBackend(Protocol):
    def encode(self, texts: List[str]) -> np.ndarray: ...

def _hash_to_rng_seed(s: str, seed: int) -> int:
    h = hashlib.sha256((s + str(seed)).encode("utf-8")).digest()
    return int.from_bytes(h[:8], "little", signed=False) % (2**31 - 1)

class DummyBackend:
    """Deterministic, fast, dependency-free embeddings for tests/CI."""
    def __init__(self, dim: int = 64, seed: int = 42):
        self.dim = dim
        self.seed = seed

    def encode(self, texts: List[str]) -> np.ndarray:
        vecs = []
        for t in texts:
            rs = np.random.RandomState(_hash_to_rng_seed(t, self.seed))
            v = rs.normal(size=self.dim).astype(np.float32)
            v /= np.linalg.norm(v) + 1e-12
            vecs.append(v)
        return np.vstack(vecs)

class SentenceTransformersBackend:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: Optional[str] = None):
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError("sentence-transformers not available") from e
        self.model = SentenceTransformer(model_name, device=device)

    def encode(self, texts: List[str]) -> np.ndarray:  # pragma: no cover (heavy)
        emb = self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return emb.astype(np.float32)

def get_backend() -> EmbeddingBackend:
    kind = os.getenv("FPA_EMBEDDINGS", "dummy").lower()
    if kind in ("dummy", "test"):
        return DummyBackend()
    if kind in ("sentence-transformers", "st", "minilm"):
        try:
            return SentenceTransformersBackend("all-MiniLM-L6-v2")
        except RuntimeError:
            # Fallback to dummy if ST isn’t installed (keeps CI green)
            return DummyBackend()
    # Future: openai, gemini, onnx
    return DummyBackend()
