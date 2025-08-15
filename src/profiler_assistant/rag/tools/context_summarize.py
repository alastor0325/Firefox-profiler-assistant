"""
context_summarize tool:
- Validates inputs
- Uses a pluggable summarizer impl if registered; otherwise deterministic fallback
- Enforces a character budget derived from token_budget
- Returns summary plus inline citation offsets over the ID substring
"""
from __future__ import annotations

from typing import Any, Dict, List, Union

from profiler_assistant.rag.types import (
    ContextSummarizeRequest,
    ContextSummarizeResponse,
    Citation,
    VectorSearchHit,
)
from profiler_assistant.rag.runtime import get_summarizer_impl
from profiler_assistant.rag.summarizers.fallback import fallback_summarize
from profiler_assistant.rag.summarizers.base import char_budget


def _hit_to_dict(h: Union[VectorSearchHit, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Normalize a hit to a plain dict. Accepts either a VectorSearchHit dataclass
    or the dict shape that may arrive via router payloads.
    """
    if isinstance(h, dict):
        return {
            "id": str(h.get("id", "")),
            "text": str(h.get("text", "")),
            "score": float(h.get("score", 0.0)),
            "meta": dict(h.get("meta", {})),
        }
    # Assume dataclass form
    return {"id": h.id, "text": h.text, "score": h.score, "meta": dict(h.meta)}


def context_summarize(req: ContextSummarizeRequest) -> ContextSummarizeResponse:
    # Validate
    if not isinstance(req.hits, list):
        raise ValueError("INVALID_ARG: 'hits' must be a list")
    if req.style not in ("bullet", "abstract", "qa"):
        raise ValueError("INVALID_ARG: 'style' must be one of {'bullet','abstract','qa'}")
    if not isinstance(req.token_budget, int) or req.token_budget < 0:
        raise ValueError("INVALID_ARG: 'token_budget' must be >= 0")

    # Convert hits to plain dicts (supports dataclasses or dict payloads)
    plain_hits: List[Dict[str, Any]] = [_hit_to_dict(h) for h in req.hits]

    # Use registered summarizer or fallback
    try:
        impl = get_summarizer_impl()
        summary, cits = impl(plain_hits, req.style, req.token_budget)
    except RuntimeError:
        summary, cits = fallback_summarize(plain_hits, req.style, req.token_budget)

    # Final hard cap (defensive): drop any citation past the cap
    limit = char_budget(req.token_budget)
    if limit and len(summary) > limit:
        summary = summary[:limit]
    citations: List[Citation] = []
    for c in cits:
        start, end = c.get("offset", (0, 0))
        if 0 <= start < end <= len(summary):
            citations.append(Citation(id=c["id"], offset=(start, end)))

    return ContextSummarizeResponse(summary=summary, citations=citations)
