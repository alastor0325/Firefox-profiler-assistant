"""
Agent-visible catalog of RAG tools plus a minimal dispatcher.
In PR2, the dispatcher invokes stub implementations with argument validation.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Optional, Type

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

# Contract registry
TOOL_SCHEMAS: Dict[str, Dict[str, Type[Any]]] = {
    "vector_search": {
        "request": VectorSearchRequest,
        "response": VectorSearchResponse,
    },
    "get_docs_by_id": {
        "request": GetDocsByIdRequest,
        "response": GetDocsByIdResponse,
    },
    "context_summarize": {
        "request": ContextSummarizeRequest,
        "response": ContextSummarizeResponse,
    },
}

# Implementation registry (stub functions)
TOOL_REGISTRY = {
    "vector_search": vector_search,
    "get_docs_by_id": get_docs_by_id,
    "context_summarize": context_summarize,
}


def list_tools() -> list[str]:
    """Return the list of tool names exposed by the agent."""
    return sorted(TOOL_SCHEMAS.keys())


def tool_schema(name: str) -> Optional[Dict[str, Any]]:
    """Return a simple description of the request/response types for a tool."""
    entry = TOOL_SCHEMAS.get(name)
    if entry is None:
        return None
    return {
        "name": name,
        "request_type": entry["request"].__name__,
        "response_type": entry["response"].__name__,
    }


def _payload_to_request(name: str, payload: Dict[str, Any]):
    """Convert a dict payload to the proper request dataclass for a tool."""
    schema = TOOL_SCHEMAS.get(name)
    if schema is None:
        raise ValueError(f"UNKNOWN_TOOL: '{name}' is not registered")

    req_cls = schema["request"]

    # Handle reserved-field mapping for GetDocsByIdRequest ('return' -> 'return_')
    if name == "get_docs_by_id" and "return" in payload and "return_" not in payload:
        payload = dict(payload)
        payload["return_"] = payload.pop("return")

    try:
        return req_cls(**payload)  # type: ignore[arg-type]
    except TypeError as e:
        # Dataclass signature mismatch → invalid args
        raise ValueError(f"INVALID_ARG: {e}")


def _response_to_dict(resp_obj: Any) -> Dict[str, Any]:
    """Convert a dataclass response to a plain dict."""
    from dataclasses import is_dataclass
    if is_dataclass(resp_obj) and not isinstance(resp_obj, type):
        return asdict(resp_obj)
    raise ValueError("INVALID_ARG: response object is not a dataclass instance")


def call_tool(name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dispatch to a stub implementation and return its response as a dict.
    Raises ValueError on unknown tool or invalid arguments.
    """
    req_obj = _payload_to_request(name, payload)
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        # Should not happen in PR2, but guard defensively
        raise ValueError(f"UNKNOWN_TOOL: '{name}' has no implementation")
    resp_obj = fn(req_obj)  # type: ignore[misc]
    return _response_to_dict(resp_obj)
