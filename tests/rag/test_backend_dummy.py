"""
Verify DummyBackend returns deterministic, dependency-free embeddings
for use in tests/CI. Ensures shape, order, and stability across calls.
"""

import os
import numpy as np
from importlib import reload
from profiler_assistant.rag import embeddings

def test_dummy_backend_shape_and_determinism(monkeypatch, caplog):
    monkeypatch.setenv("FPA_EMBED_BACKEND", "dummy")
    reload(embeddings)

    caplog.clear()
    backend = embeddings.get_backend()
    texts = ["x", "y", "x"]
