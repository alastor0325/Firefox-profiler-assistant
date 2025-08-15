"""
get_docs_by_id tool: delegates ID resolution to a pluggable docs implementation.
Validates inputs, fetches chunk/parent/both, and normalizes results.
"""
from __future__ import annotations

import logging

from profiler_assistant.rag.types import (
    GetDocsByIdRequest,
    GetDocsByIdResponse,
    Doc,
    Metadata,
)
from profiler_assistant.rag.runtime import get_docs_impl


def get_docs_by_id(req: GetDocsByIdRequest) -> GetDocsByIdResponse:
    # Validation
    if not isinstance(req.ids, list) or len(req.ids) == 0:
        raise ValueError("INVALID_ARG: 'ids' must be a non-empty list of strings")
    if any((not isinstance(i, str) or not i.strip()) for i in req.ids):
        raise ValueError("INVALID_ARG: each id in 'ids' must be a non-empty string")
    if req.return_ not in ("chunk", "parent", "both"):
        raise ValueError("INVALID_ARG: 'return_' must be one of {'chunk','parent','both'}")

    logging.debug("get_docs_by_id: return_=%s ids=%d", req.return_, len(req.ids))

    impl = get_docs_impl()
    raw_docs = impl(req.ids, req.return_)

    docs: list[Doc] = []
    for d in raw_docs:
        meta: Metadata = d.get("meta", {})
        docs.append(Doc(id=d["id"], text=d["text"], meta=meta))

    logging.debug("get_docs_by_id: returned=%d", len(docs))
    return GetDocsByIdResponse(docs=docs)
