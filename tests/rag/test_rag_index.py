"""
test_rag_index.py
-----------------
Purpose: Validate vector index behavior and backend parity.
- Round-trip: add vectors + search → top-1 is the exact item.
- Unified hit schema across backends.
- Optional FAISS parity test runs only if FAISS is available.
"""

import importlib.util
import pytest
import numpy as np
from profiler_assistant.rag.index import NumpyIndex

# Check if faiss module is available
_HAS_FAISS = importlib.util.find_spec("faiss") is not None
if _HAS_FAISS:
    from profiler_assistant.rag.index import FaissIndex


def _toy_data():
    rng = np.random.RandomState(0)
    base = rng.normal(size=(5, 16)).astype(np.float32)
    base /= np.linalg.norm(base, axis=1, keepdims=True) + 1e-12
    metas = [{
        "doc_id": f"d{i}", "chunk_id": i, "section_path": "A/B", "heading": f"H{i}"
    } for i in range(5)]
    return base, metas


def _assert_hit_schema(hit):
    for k in ("doc_id", "chunk_id", "score", "section_path", "heading"):
        assert k in hit


def test_numpy_index_roundtrip_top1():
    vecs, metas = _toy_data()
    idx = NumpyIndex(dim=16)
    idx.add(vecs, metas)
    q = vecs[2]  # exact item in the set → should be rank 1
    hits = idx.search(q, k=3)
    assert hits[0]["doc_id"] == metas[2]["doc_id"]
    for h in hits:
        _assert_hit_schema(h)
    assert -1.01 <= hits[0]["score"] <= 1.01  # cosine range guard


def test_backends_identical_results_when_same_vectors():
    if not _HAS_FAISS:
        pytest.skip("faiss not installed")

    vecs, metas = _toy_data()
    numpy_idx = NumpyIndex(dim=16)
    numpy_idx.add(vecs, metas)
    q = vecs[1]
    numpy_hits = numpy_idx.search(q, k=3)

    faiss_idx = FaissIndex(dim=16)
    faiss_idx.add(vecs, metas)
    faiss_hits = faiss_idx.search(q, k=3)
    assert [h["doc_id"] for h in faiss_hits] == [h["doc_id"] for h in numpy_hits]
