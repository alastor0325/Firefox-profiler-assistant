"""
index.py
--------
Purpose: Provide a backend-agnostic vector index interface for retrieval.
- VectorIndex protocol with add() and search().
- Default NumpyIndex using cosine similarity (no extra deps).
- Optional FaissIndex if 'faiss' is available (same hit schema).
- Returns hits with {doc_id, chunk_id, score, section_path, heading}.
"""

from __future__ import annotations
from typing import List, Protocol, Dict, Any, Optional
import numpy as np

class VectorIndex(Protocol):
    def add(self, vectors: np.ndarray, metas: List[Dict[str, Any]]) -> None: ...
    def search(self, query_vec: np.ndarray, k: int) -> List[Dict[str, Any]]: ...

def _normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True) + 1e-12
    return mat / norms

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
        return hits

class FaissIndex:
    def __init__(self, dim: int):
        try:
            import faiss  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError("faiss not available") from e
        self.faiss = faiss
        self.dim = dim
        self.index = faiss.IndexFlatIP(dim)
        self._metas: List[Dict[str, Any]] = []

    def add(self, vectors: np.ndarray, metas: List[Dict[str, Any]]) -> None:
        if vectors.ndim != 2:
            raise ValueError("vectors must be 2D [n, d]")
        if len(metas) != vectors.shape[0]:
            raise ValueError("metas length must match vectors")
        vecs = vectors.astype("float32")
        vecs = _normalize(vecs)
        self.index.add(vecs)
        self._metas.extend(metas)

    def search(self, query_vec: np.ndarray, k: int) -> List[Dict[str, Any]]:
        if len(self._metas) == 0:
            return []
        q = _normalize(query_vec.astype("float32").reshape(1, -1))
        D, I = self.index.search(q, k)
        sims = D[0]
        idxs = I[0]
        hits = []
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
        return hits

def get_default_index(dim: int) -> VectorIndex:
    # Prefer pure NumPy default (simple, no extra deps)
    return NumpyIndex(dim)
