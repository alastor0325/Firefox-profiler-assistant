"""
Verify that the default embedding backend is SentenceTransformersBackend
when no env override is set. Uses a mocked SentenceTransformer to stay offline
and asserts correct shape, order preservation, and logging behavior.
"""

import logging
import types
import sys
import numpy as np
from importlib import reload
from profiler_assistant.rag import embeddings

class _FakeST:
    def __init__(self, model_id):
        assert model_id == embeddings.DEFAULT_ST_MODEL
    def encode(self, texts, **kwargs):
        import numpy as np
        n, d = len(texts), 384
        out = np.zeros((n, d), dtype=np.float32)
        for i in range(n):
            out[i, 0] = i  # make order testable
        return out

def test_default_is_local_with_mock(monkeypatch, caplog):
    # Inject fake module
    fake_mod = types.ModuleType("sentence_transformers")
    setattr(fake_mod, "SentenceTransformer", _FakeST)   # <- no Pylance error
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_mod)
    reload(embeddings)

    caplog.clear()
    caplog.set_level(logging.INFO, logger="profiler_assistant.rag.embeddings")

    backend = embeddings.get_backend()
    xs = ["a", "b", "c", "d", "e"]
    vecs = backend.encode(xs)

    assert vecs.shape == (5, 384)
    # order preserved: first column equals index
    assert np.allclose(vecs[:, 0], np.arange(5, dtype=np.float32))
    assert any("embedding_backend=local" in r.message for r in caplog.records)
