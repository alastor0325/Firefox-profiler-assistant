"""
Declares the agent-visible catalog of RAG tools and exposes lightweight
introspection helpers. Implementations are intentionally absent in PR1.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Type

from ..rag.types import (
    VectorSearchRequest,
    VectorSearchResponse,
    GetDocsByIdRequest,
    GetDocsByIdResponse,
    ContextSummarizeRequest,
    ContextSummarizeResponse,
)

# Contract-only registry (no implementations in PR1).
# Each entry advertises the request/response dataclass types.
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


def call_tool(name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Placeholder dispatcher. PR1 provides no implementations and always raises.
    Implementations are introduced in PR2.
    """
    raise NotImplementedError(
        f"Tool '{name}' is declared but not implemented in PR1 "
        "(see PR2 for stub implementations)."
    )
