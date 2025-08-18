"""
Validate that the index manifest is written and that retrieval fast-fails when
the query embedder/index settings don't match the corpus.
"""

import json
import os
import tempfile
import numpy as np
import pytest

from profiler_assistant.rag.manifest import (
    EmbedderInfo,
    write_index_manifest,
    assert_index_compatible,
    IndexCompatibilityError,
)

def _mk_vectors(n=3, d=8):
    rng = np.random.default_rng(0)
    return rng.standard_normal((n, d)).astype(np.float32)

def test_manifest_written_with_expected_fields(tmp_path):
    idx_dir = tmp_path / ".fpa_index"
    vecs = _mk_vectors()
    vectors_path = idx_dir / "vectors.npy"
    os.makedirs(idx_dir, exist_ok=True)
    np.save(vectors_path, vecs)

    manifest_path = write_index_manifest(
        str(idx_dir),
        embedder=EmbedderInfo(name="dummy", dim=8, normalize=True),
        index_impl="numpy",
        distance="cosine",
        num_vectors=vecs.shape[0],
        vectors_path=str(vectors_path),
        lib_versions={"numpy": np.__version__},
        fpa_version=None,
    )

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Spot-check critical contract fields
    assert data["schema_version"] == 1
    assert data["embedder_name"] == "dummy"
    assert data["embedder_dim"] == 8
    assert data["normalize"] is True
    assert data["distance"] == "cosine"
    assert data["index_impl"] == "numpy"
    assert data["num_vectors"] == vecs.shape[0]
    assert isinstance(data.get("vectors_sha256"), (str, type(None)))

def test_refuse_on_model_name_mismatch(tmp_path):
    idx_dir = tmp_path / ".fpa_index"
    os.makedirs(idx_dir, exist_ok=True)
    np.save(idx_dir / "vectors.npy", _mk_vectors())

    write_index_manifest(
        str(idx_dir),
        embedder=EmbedderInfo(name="dummy", dim=8, normalize=True),
        index_impl="numpy",
        distance="cosine",
        num_vectors=3,
        vectors_path=str(idx_dir / "vectors.npy"),
    )

    with pytest.raises(IndexCompatibilityError) as ei:
        assert_index_compatible(
            str(idx_dir),
            current_embedder=EmbedderInfo(name="sentence-transformers/all-MiniLM-L6-v2", dim=384, normalize=True),
            expected_distance="cosine",
            expected_index_impl="numpy",
        )
    assert "embedder_name" in str(ei.value)

def test_refuse_on_dimension_mismatch(tmp_path):
    idx_dir = tmp_path / ".fpa_index"
    os.makedirs(idx_dir, exist_ok=True)
    np.save(idx_dir / "vectors.npy", _mk_vectors())

    write_index_manifest(
        str(idx_dir),
        embedder=EmbedderInfo(name="dummy", dim=8, normalize=True),
        index_impl="numpy",
        distance="cosine",
        num_vectors=3,
        vectors_path=str(idx_dir / "vectors.npy"),
    )

    with pytest.raises(IndexCompatibilityError) as ei:
        assert_index_compatible(
            str(idx_dir),
            current_embedder=EmbedderInfo(name="dummy", dim=16, normalize=True),
            expected_distance="cosine",
            expected_index_impl="numpy",
        )
    assert "embedder_dim" in str(ei.value)

def test_refuse_on_normalize_flag_mismatch(tmp_path):
    idx_dir = tmp_path / ".fpa_index"
    os.makedirs(idx_dir, exist_ok=True)
    np.save(idx_dir / "vectors.npy", _mk_vectors())

    write_index_manifest(
        str(idx_dir),
        embedder=EmbedderInfo(name="dummy", dim=8, normalize=True),
        index_impl="numpy",
        distance="cosine",
        num_vectors=3,
        vectors_path=str(idx_dir / "vectors.npy"),
    )

    with pytest.raises(IndexCompatibilityError) as ei:
        assert_index_compatible(
            str(idx_dir),
            current_embedder=EmbedderInfo(name="dummy", dim=8, normalize=False),
            expected_distance="cosine",
            expected_index_impl="numpy",
        )
    assert "normalize" in str(ei.value)

def test_missing_manifest_refuses_with_hint(tmp_path):
    idx_dir = tmp_path / ".fpa_index"
    os.makedirs(idx_dir, exist_ok=True)
    np.save(idx_dir / "vectors.npy", _mk_vectors())

    with pytest.raises(IndexCompatibilityError) as ei:
        assert_index_compatible(
            str(idx_dir),
            current_embedder=EmbedderInfo(name="dummy", dim=8, normalize=True),
            expected_distance="cosine",
            expected_index_impl="numpy",
        )
    msg = str(ei.value)
    assert "manifest is missing" in msg or "predates manifest" in msg
