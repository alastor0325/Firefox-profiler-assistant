"""
Purpose: Define a lightweight, swappable embedding interface for the RAG stack.
- EmbeddingBackend protocol with encode().
- Default SentenceTransformersBackend ("sentence-transformers/all-MiniLM-L6-v2") if installed.
- Optional DummyBackend (deterministic, dependency-free for tests/CI) via env.
- Selection via env var FPA_EMBEDDINGS (e.g., 'dummy', 'sentence-transformers').
"""

from __future__ import annotations
import hashlib
import os
from typing import List, Protocol, Optional
import numpy as np

# Default Hugging Face SentenceTransformers model for local embeddings
DEFAULT_ST_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

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

    def get_embedder_info(self):
        """
        Purpose:
        Expose a stable identity for safety checks (manifest).
        """
        import logging
        log = logging.getLogger(__name__)
        name = "dummy"
        dim = getattr(self, "dim", 8)  # fallback in case dim is implicit
        normalize = getattr(self, "normalize", True)
        log.debug("DummyBackend.get_embedder_info -> name=%s dim=%d normalize=%s", name, dim, normalize)
        return {"name": name, "dim": dim, "normalize": normalize}

class SentenceTransformersBackend:
    def __init__(self, model_name: str = DEFAULT_ST_MODEL, device: Optional[str] = None):
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError("sentence-transformers not available") from e
        if device is not None:
            self.model = SentenceTransformer(model_name, device=device)
        else:
            self.model = SentenceTransformer(model_name)

    def encode(self, texts: List[str]) -> np.ndarray:  # pragma: no cover (heavy)
        emb = self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return emb.astype(np.float32)

    def get_embedder_info(self):
        """
        Purpose:
        Expose a stable identity for safety checks (manifest).
        """
        import logging
        log = logging.getLogger(__name__)
        model_name = getattr(self, "model_name", "sentence-transformers/all-MiniLM-L6-v2")
        dim = getattr(self, "dim", 384)  # typical for MiniLM-L6-v2
        normalize = getattr(self, "normalize", True)
        log.debug("STBackend.get_embedder_info -> name=%s dim=%d normalize=%s", model_name, dim, normalize)
        return {"name": model_name, "dim": dim, "normalize": normalize}


def get_backend() -> EmbeddingBackend:
    import logging
    logger = logging.getLogger(__name__)

    kind = os.getenv("FPA_EMBEDDINGS", "sentence-transformers").lower()
    if kind in ("dummy", "test"):
        logger.info("embedding_backend=dummy")
        return DummyBackend()
    if kind in ("sentence-transformers", "st", "minilm"):
        try:
            logger.info("embedding_backend=local model=%s", DEFAULT_ST_MODEL)
            return SentenceTransformersBackend(DEFAULT_ST_MODEL)
        except RuntimeError:
            logger.warning("sentence-transformers not available; falling back to dummy")
            return DummyBackend()
    logger.info("embedding_backend=unknown -> fallback dummy")
    return DummyBackend()
