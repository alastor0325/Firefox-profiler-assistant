"""
Provide a backend-agnostic vector index interface for retrieval.
- VectorIndex protocol with add() and search().
- Default NumpyIndex using cosine similarity (no extra deps).
- Optional FaissIndex if 'faiss' is available (same hit schema).
- Returns hits with {doc_id, chunk_id, score, section_path, heading}.
"""

from __future__ import annotations
from typing import List, Protocol, Dict, Any, Optional
import numpy as np
import logging

_log = logging.getLogger(__name__)

class VectorIndex(Protocol):
    def add(self, vectors: np.ndarray, metas: List[Dict[str, Any]]) -> None: ...
    def search(self, query_vec: np.ndarray, k: int) -> List[Dict[str, Any]]: ...

def _normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True) + 1e-12
    return mat / norms

def get_index_contract() -> Dict[str, Any]:
    """
    Purpose:
    Expose the retrieval contract for safety/manifest checks.
    """
    # Both NumpyIndex and FaissIndex below normalize then use inner product,
    # which equals cosine similarity when inputs are L2-normalized.
    return {
        "index_impl": "numpy",   # default impl used by get_default_index()
        "distance": "cosine",
    }

class NumpyIndex:
    def __init__(self, dim: Optional[int] = None):
        self.dim = dim
        self._vecs: Optional[np.ndarray] = None
        self._metas: List[Dict[str, Any]] = []

    def add(self, vectors: np.ndarray, metas: List[Dict[str, Any]]) -> None:
        if vectors.ndim != 2:
            raise ValueError("vectors must be 2D [n, d]")
        if len(metas) != vectors.shape[0]:
            raise ValueError("metas length must match vectors")
        if self._vecs is None:
            self.dim = vectors.shape[1]
            self._vecs = _normalize(vectors.astype(np.float32))
        else:
            if vectors.shape[1] != self._vecs.shape[1]:
                raise ValueError("all vectors must have same dimension")
            self._vecs = np.vstack([self._vecs, _normalize(vectors.astype(np.float32))])
        self._metas.extend(metas)
        _log.debug("NumpyIndex.add: total=%d dim=%s", len(self._metas), self.dim)

    def search(self, query_vec: np.ndarray, k: int) -> List[Dict[str, Any]]:
        if self._vecs is None or len(self._metas) == 0:
            return []
        q = query_vec.astype(np.float32).reshape(1, -1)
        q = _normalize(q)
        sims = (self._vecs @ q.T).ravel()  # cosine since both are normalized
        idx = np.argsort(-sims)[:k]
        hits = []
        for i in idx:
            m = self._metas[i]
            hits.append({
                "doc_id": m.get("doc_id"),
                "chunk_id": m.get("chunk_id"),
                "score": float(sims[i]),
                "section_path": m.get("section_path"),
                "heading": m.get("heading"),
            })
        _log.debug("NumpyIndex.search: k=%d -> %d hits", k, len(hits))
        return hits

class FaissIndex:
    def __init__(self, dim: int):
        """
        Purpose:
        Cosine-similarity retrieval on top of FAISS (IndexFlatIP) with
        explicit L2-normalization to make IP == cosine.
        """
        try:
            import faiss  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError("faiss not available") from e
        from typing import Any
        self.faiss = faiss
        self.dim = dim
        # Treat FAISS index as Any to avoid SWIG stub signature noise in Pylance.
        self.index: Any = faiss.IndexFlatIP(dim)
        self._metas: List[Dict[str, Any]] = []
        _log.debug("FaissIndex.__init__: dim=%d", dim)

    def add(self, vectors: np.ndarray, metas: List[Dict[str, Any]]) -> None:
        """
        Add a batch of vectors and matching metas. Vectors are L2-normalized
        to align with cosine similarity (matching NumpyIndex behavior).
        """
        if vectors.ndim != 2:
            raise ValueError("vectors must be 2D [n, d]")
        if len(metas) != vectors.shape[0]:
            raise ValueError("metas length must match vectors")
        if vectors.shape[1] != self.dim:
            raise ValueError(f"vector dim {vectors.shape[1]} != index dim {self.dim}")

        # Normalize and ensure C-contiguous float32 for FAISS.
        vecs = vectors.astype("float32", copy=False)
        vecs = vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12)
        vecs = np.ascontiguousarray(vecs, dtype="float32")

        self.index.add(vecs)  # type: ignore[attr-defined]
        self._metas.extend(metas)
        _log.debug("FaissIndex.add: added=%d total=%d", len(metas), len(self._metas))

    def search(self, query_vec: np.ndarray, k: int) -> List[Dict[str, Any]]:
        """
        Search top-k by cosine similarity (via IP on normalized vectors).
        Returns [{doc_id, chunk_id, score, section_path, heading}].
        """
        if len(self._metas) == 0:
            return []
        q = query_vec.astype("float32", copy=False).reshape(1, -1)
        q = q / (np.linalg.norm(q, axis=1, keepdims=True) + 1e-12)
        q = np.ascontiguousarray(q, dtype="float32")

        D, I = self.index.search(q, k)  # type: ignore[attr-defined]
        sims = D[0]
        idxs = I[0]
        hits: List[Dict[str, Any]] = []
        for i, sim in zip(idxs, sims):
            if i < 0:
                continue
            m = self._metas[i]
            hits.append({
                "doc_id": m.get("doc_id"),
                "chunk_id": m.get("chunk_id"),
                "score": float(sim),
                "section_path": m.get("section_path"),
                "heading": m.get("heading"),
            })
        _log.debug("FaissIndex.search: k=%d -> %d hits", k, len(hits))
        return hits
