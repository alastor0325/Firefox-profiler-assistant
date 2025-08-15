"""
Agent-visible catalog of RAG tools plus a minimal dispatcher.

- RAG tools (vector_search, get_docs_by_id, context_summarize) use dataclass
  request/response contracts and are returned by list_tools() to match tests.
- Domain tools (diagnostics on the loaded profile) are registered separately
  and callable by the agent, but are not included in list_tools() to keep the
  PR1 contract stable.

All functions include light logging to aid debugging.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List

from profiler_assistant.rag.types import (
    VectorSearchRequest,
    VectorSearchResponse,
    GetDocsByIdRequest,
    GetDocsByIdResponse,
    ContextSummarizeRequest,
    ContextSummarizeResponse,
)
from profiler_assistant.rag.tools.vector_search import vector_search
from profiler_assistant.rag.tools.get_docs_by_id import get_docs_by_id
from profiler_assistant.rag.tools.context_summarize import context_summarize

# Domain diagnostic wrappers (accept dict payloads; read profile from runtime context)
from profiler_assistant.tools.profile_diagnostics import (
    find_video_sink_dropped_frames as _tool_find_dropped,
    extract_process as _tool_extract_process,
)

log = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# Schema map for RAG tools (name -> request/response dataclasses)
# ------------------------------------------------------------------------------
TOOL_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "vector_search": {"request": VectorSearchRequest, "response": VectorSearchResponse},
    "get_docs_by_id": {"request": GetDocsByIdRequest, "response": GetDocsByIdResponse},
    "context_summarize": {"request": ContextSummarizeRequest, "response": ContextSummarizeResponse},
}

# ------------------------------------------------------------------------------
# Registries
# ------------------------------------------------------------------------------
# RAG tools registry
_RAG_TOOL_REGISTRY: Dict[str, Any] = {
    "vector_search": vector_search,
    "get_docs_by_id": get_docs_by_id,
    "context_summarize": context_summarize,
}

# Domain tools registry
_DOMAIN_TOOL_REGISTRY: Dict[str, Any] = {
    "find_video_sink_dropped_frames": _tool_find_dropped,
    "extract_process": _tool_extract_process,
}


# ------------------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------------------
def list_tools() -> List[str]:
    """Return ONLY the high-level RAG tools (contract from PR1/PR2)."""
    names = list(_RAG_TOOL_REGISTRY.keys())
    log.debug("list_tools -> %s", names)
    return names


def tool_schema(name: str) -> Dict[str, str] | None:
    """
    Return a small description of the tool's request/response types for display.
    RAG tools reflect dataclass type names. Domain tools use terse text.
    """
    if name in TOOL_SCHEMAS:
        req_cls = TOOL_SCHEMAS[name]["request"]
        resp_cls = TOOL_SCHEMAS[name]["response"]
        return {"request_type": req_cls.__name__, "response_type": resp_cls.__name__}
    if name == "find_video_sink_dropped_frames":
        return {"request_type": "NoArgs", "response_type": "{dropped_frames:int}"}
    if name == "extract_process":
        return {"request_type": '{"query": str} | {"pid": int}', "response_type": "dict"}
    return None


# ------------------------------------------------------------------------------
# Internals
# ------------------------------------------------------------------------------
def _payload_to_request(name: str, payload: Dict[str, Any]) -> Any:
    """Convert a dict payload to the proper dataclass for a RAG tool."""
    schema = TOOL_SCHEMAS.get(name)
    if schema is None:
        raise ValueError(f"UNKNOWN_TOOL: '{name}' is not a RAG tool")

    req_cls = schema["request"]

    # Map reserved field for GetDocsByIdRequest ('return' -> 'return_')
    if name == "get_docs_by_id" and "return" in payload and "return_" not in payload:
        payload = dict(payload)
        payload["return_"] = payload.pop("return")

    try:
        obj = req_cls(**payload)  # type: ignore[arg-type]
        log.debug("_payload_to_request %s payload=%s -> %s", name, payload, obj)
        return obj
    except TypeError as e:
        log.exception("Invalid args for %s: %s", name, payload)
        raise ValueError(f"INVALID_ARG: {e}")


def _response_to_dict(resp_obj: Any) -> Dict[str, Any]:
    """Convert a dataclass response to a plain dict."""
    if is_dataclass(resp_obj) and not isinstance(resp_obj, type):
        d = asdict(resp_obj)
        log.debug("_response_to_dict <- %s", type(resp_obj).__name__)
        return d
    log.error("Response is not a dataclass instance: %r", resp_obj)
    raise ValueError("INVALID_ARG: response object is not a dataclass instance")


def call_tool(name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dispatch to either RAG or Domain registries.
    - RAG tools: dict payload -> request dataclass -> dataclass response -> dict
    - Domain tools: dict payload -> dict response
    """
    fn = _RAG_TOOL_REGISTRY.get(name) or _DOMAIN_TOOL_REGISTRY.get(name)
    if fn is None:
        log.error("call_tool: unknown tool '%s'", name)
        raise ValueError(f"UNKNOWN_TOOL: '{name}' has no implementation")

    if name in _RAG_TOOL_REGISTRY:
        log.info("call_tool RAG: %s payload=%s", name, payload)
        req = _payload_to_request(name, payload)
        resp_obj = fn(req)  # type: ignore[misc]
        return _response_to_dict(resp_obj)

    # Domain tools accept dict payloads directly and return dicts
    log.info("call_tool DOMAIN: %s payload=%s", name, payload)
    result = fn(payload)  # type: ignore[misc]
    if not isinstance(result, dict):
        log.error("Domain tool '%s' returned non-dict: %r", name, result)
        raise ValueError("INVALID_RETURN: domain tool must return dict")
    return result
