"""
vector_search tool: now calls a pluggable search implementation via runtime.
Still validates arguments; returns real hits if an impl is registered.
"""
from __future__ import annotations

from profiler_assistant.rag.types import (
    VectorSearchRequest,
    VectorSearchResponse,
    VectorSearchHit,
    Metadata,
)
from profiler_assistant.rag.runtime import get_search_impl


def vector_search(req: VectorSearchRequest) -> VectorSearchResponse:
    # Validation
    if not isinstance(req.query, str) or not req.query.strip():
        raise ValueError("INVALID_ARG: 'query' must be a non-empty string")
    if not isinstance(req.k, int) or req.k <= 0:
        raise ValueError("INVALID_ARG: 'k' must be a positive integer")
    if not isinstance(req.section_hard_limit, int) or req.section_hard_limit < 0:
        raise ValueError("INVALID_ARG: 'section_hard_limit' must be >= 0")

    # Delegate to the active search implementation
    impl = get_search_impl()
    raw_hits = impl(req.query, req.k, req.filters, req.section_hard_limit, req.reranker)

    # Normalize output into dataclasses
    hits: list[VectorSearchHit] = []
    for h in raw_hits:
        meta: Metadata = h.get("meta", {})  # TypedDict, total=False
        hits.append(
            VectorSearchHit(
                id=h["id"],
                text=h["text"],
                score=float(h["score"]),
                meta=meta,
            )
        )
    return VectorSearchResponse(hits=hits)
