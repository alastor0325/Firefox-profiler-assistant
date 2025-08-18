"""
Persist and validate an index manifest alongside vector artifacts so that
query-time embedder/index settings are guaranteed to match the corpus.
"""

from __future__ import annotations
import dataclasses
import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1
MANIFEST_FILENAME = "manifest.json"


class IndexCompatibilityError(RuntimeError):
    """Raised when the current query embedder/index is incompatible with the corpus index."""


@dataclasses.dataclass(frozen=True)
class EmbedderInfo:
    name: str
    dim: int
    normalize: bool


def _sha256_of_file(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_index_manifest(
    index_dir: str,
    *,
    embedder: EmbedderInfo,
    index_impl: str,
    distance: str,
    num_vectors: int,
    vectors_path: str,
    lib_versions: Optional[Dict[str, str]] = None,
    fpa_version: Optional[str] = None,
) -> str:
    """
    Write `.fpa_index/manifest.json` atomically with key settings for fast-fail correctness.
    """
    os.makedirs(index_dir, exist_ok=True)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "embedder_name": embedder.name,
        "embedder_dim": embedder.dim,
        "normalize": embedder.normalize,
        "distance": distance,
        "index_impl": index_impl,
        "num_vectors": num_vectors,
        "vectors_sha256": _sha256_of_file(vectors_path),
        "lib_versions": lib_versions or {},
        "fpa_version": fpa_version,
    }

    tmp = os.path.join(index_dir, f"{MANIFEST_FILENAME}.tmp")
    final = os.path.join(index_dir, MANIFEST_FILENAME)
    log.info("Writing index manifest to %s", final)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    os.replace(tmp, final)
    return final


def _load_manifest(index_dir: str) -> Dict[str, Any]:
    path = os.path.join(index_dir, MANIFEST_FILENAME)
    if not os.path.exists(path):
        raise IndexCompatibilityError(
            "Index manifest is missing. This index likely predates manifest support. "
            "Please rebuild the RAG index (ingest+embed+index) to proceed."
        )
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise IndexCompatibilityError(
                f"Index manifest is corrupted or unreadable: {e}. "
                "Please rebuild the RAG index."
            )
    return data


def assert_index_compatible(
    index_dir: str,
    *,
    current_embedder: EmbedderInfo,
    expected_distance: str,
    expected_index_impl: str,
) -> None:
    """
    Fast-fail if the current query settings don't match the corpus index.
    """
    mf = _load_manifest(index_dir)

    issues = []

    def cmp(key: str, expected: Any) -> None:
        got = mf.get(key)
        if got != expected:
            issues.append((key, got, expected))

    cmp("embedder_name", current_embedder.name)
    cmp("embedder_dim", current_embedder.dim)
    cmp("normalize", current_embedder.normalize)
    cmp("distance", expected_distance)
    cmp("index_impl", expected_index_impl)

    if issues:
        details = "; ".join(f"{k}: index={got!r} ≠ query={exp!r}" for k, got, exp in issues)
        raise IndexCompatibilityError(
            "Incompatible index and query settings detected. "
            f"{details}. Please rebuild the RAG index to align settings."
        )

    log.debug(
        "Index manifest compatibility OK: embedder=%s dim=%d normalize=%s distance=%s index_impl=%s",
        current_embedder.name,
        current_embedder.dim,
        current_embedder.normalize,
        mf.get("distance"),
        mf.get("index_impl"),
    )
