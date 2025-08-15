"""
Stub implementation of the get_docs_by_id tool.
Validates inputs and returns an empty document list (no backend retrieval yet).
"""
from __future__ import annotations

from profiler_assistant.rag.types import GetDocsByIdRequest, GetDocsByIdResponse


def get_docs_by_id(req: GetDocsByIdRequest) -> GetDocsByIdResponse:
    # Validation
    if not isinstance(req.ids, list) or len(req.ids) == 0:
        raise ValueError("INVALID_ARG: 'ids' must be a non-empty list of strings")
    if any((not isinstance(i, str) or not i.strip()) for i in req.ids):
        raise ValueError("INVALID_ARG: each id in 'ids' must be a non-empty string")
    if req.return_ not in ("chunk", "parent", "both"):
        # Type system should enforce this, but we guard defensively
        raise ValueError("INVALID_ARG: 'return_' must be one of {'chunk','parent','both'}")

    # Deterministic empty response for PR2
    return GetDocsByIdResponse(docs=[])
