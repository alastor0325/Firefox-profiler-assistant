"""
Stub implementation of the vector_search tool.
Validates inputs and returns an empty result set (no backend retrieval yet).
"""
from __future__ import annotations

from profiler_assistant.rag.types import VectorSearchRequest, VectorSearchResponse


def vector_search(req: VectorSearchRequest) -> VectorSearchResponse:
    # Basic validation (raise ValueError on invalid args)
    if not isinstance(req.query, str) or not req.query.strip():
        raise ValueError("INVALID_ARG: 'query' must be a non-empty string")
    if not isinstance(req.k, int) or req.k <= 0:
        raise ValueError("INVALID_ARG: 'k' must be a positive integer")
    if not isinstance(req.section_hard_limit, int) or req.section_hard_limit < 0:
        raise ValueError("INVALID_ARG: 'section_hard_limit' must be >= 0")

    # Deterministic empty response for PR2
    return VectorSearchResponse(hits=[])
