"""
Stub implementation of the context_summarize tool.
Validates inputs and returns a deterministic placeholder summary with no citations.
"""
from __future__ import annotations

from profiler_assistant.rag.types import ContextSummarizeRequest, ContextSummarizeResponse


def context_summarize(req: ContextSummarizeRequest) -> ContextSummarizeResponse:
    # Validation
    if not isinstance(req.hits, list):
        raise ValueError("INVALID_ARG: 'hits' must be a list")
    if req.style not in ("bullet", "abstract", "qa"):
        # Type system should enforce this, but we guard defensively
        raise ValueError("INVALID_ARG: 'style' must be one of {'bullet','abstract','qa'}")
    if not isinstance(req.token_budget, int) or req.token_budget < 0:
        raise ValueError("INVALID_ARG: 'token_budget' must be >= 0")

    # Deterministic placeholder
    return ContextSummarizeResponse(
        summary="No context provided yet.",
        citations=[],
    )
