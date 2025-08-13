"""
test_rag_embeddings.py
----------------------
Purpose: Verify embedding backends are deterministic, shaped correctly, and CI-safe.
- Uses DummyBackend by default (no network/deps).
- Confirms per-text variation and unit-norm outputs.
"""

import numpy as np
from profiler_assistant.rag.embeddings import get_backend, DummyBackend

def test_dummy_backend_deterministic(monkeypatch):
    monkeypatch.setenv("FPA_EMBEDDINGS", "dummy")
    be = get_backend()
    v1 = be.encode(["hello world", "goodbye"])
    v2 = be.encode(["hello world", "goodbye"])
    assert v1.shape == (2, 64)
    assert np.allclose(v1, v2)

def test_dummy_backend_varies_by_text():
    be = DummyBackend(dim=32, seed=123)
    a = be.encode(["alpha"])[0]
    b = be.encode(["beta"])[0]
    assert a.shape == (32,)
    # Different texts → not identical vectors
    assert not np.allclose(a, b)
    # Unit norm
    assert np.isclose(np.linalg.norm(a), 1.0, atol=1e-5)
