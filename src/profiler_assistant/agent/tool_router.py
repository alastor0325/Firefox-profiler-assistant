"""
Agent-visible catalog of RAG tools plus a minimal dispatcher.

- RAG tools (vector_search, get_docs_by_id, context_summarize) use dataclass
  request/response contracts and are returned by list_tools() to match tests.
- Domain tools (diagnostics on the loaded profile) are registered separately
   and callable by the agent, and we also include their names in list_tools()
   so tests/agent listings can see them.

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
from profiler_assistant.tools.base import TOOLS as _TOOLS_REGISTRY
# NEW: allow resolving Profile from runtime context when not provided in payload
try:  # NEW
    from profiler_assistant.runtime.context import get_current_profile  # type: ignore
except Exception:  # pragma: no cover  # NEW
    get_current_profile = None  # type: ignore  # NEW

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
# Keep the public domain tool names stable; look up implementations via TOOLS.
# Add to this whitelist if you expose more analysis tools to the agent by name.
_DOMAIN_TOOL_NAMES: List[str] = [
    "find_video_sink_dropped_frames",
    "extract_process",
]

# Build a live view of available domain tools from the centralized registry.
# Each entry is: name -> {"function": callable, "args": [...], "description": "..."}
_DOMAIN_TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    name: _TOOLS_REGISTRY[name]
    for name in _DOMAIN_TOOL_NAMES
    if name in _TOOLS_REGISTRY
}


# ------------------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------------------
def list_rag_tools() -> List[str]:
    """Return ONLY the high-level RAG tool names."""
    names = list(_RAG_TOOL_REGISTRY.keys())
    log.debug("list_rag_tools -> %s", names)
    return names


def list_domain_tools() -> List[str]:
    """Return the names of domain (profile analysis) tools available to the agent."""
    names = list(_DOMAIN_TOOL_REGISTRY.keys())
    log.debug("list_domain_tools -> %s", names)
    return names


def list_agent_tools() -> List[str]:
    """Return all tool names the agent can call: RAG + domain."""
    names = list(_RAG_TOOL_REGISTRY.keys()) + list(_DOMAIN_TOOL_REGISTRY.keys())
    log.debug("list_agent_tools -> %s", names)
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
    if name in _DOMAIN_TOOL_REGISTRY:
        if name == "find_video_sink_dropped_frames":
            return {"request_type": "NoArgs or {profile}", "response_type": "dict"}
        if name == "extract_process":
            return {"request_type": '{"profile"?,"name"?,"pid"?}', "response_type": "dict"}
        return {"request_type": "{profile?, ...tool_args}", "response_type": "dict"}
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


def _resolve_profile(payload: Dict[str, Any]) -> Any:
    """
    Resolve a Profile for domain tools:
    - Prefer an explicit 'profile' entry in payload.
    - Fallback to runtime context if available (react_agent sets it).
    """
    profile = payload.get("profile")
    if profile is not None:
        return profile
    if callable(get_current_profile):  # type: ignore
        try:
            ctx_profile = get_current_profile()  # type: ignore
        except Exception:
            ctx_profile = None
        if ctx_profile is not None:
            return ctx_profile
    log.error("No profile provided and no runtime profile set")
    raise ValueError("MISSING_PROFILE: provide 'profile' in payload or set runtime profile")


def _normalize_domain_result(result: Any) -> Dict[str, Any]:
    """
    Normalize common non-dict return types from domain tools to dicts.
    - pandas.DataFrame -> {"data": [...], "columns": [...], "shape": [...]}
    - list/tuple -> {"data": [...]}
    - fallback -> {"data": str(result)}
    """
    # pandas.DataFrame (or anything with a to_dict that supports orient="records")
    if hasattr(result, "to_dict"):
        try:
            records = result.to_dict(orient="records")  # type: ignore[call-arg]
            resp: Dict[str, Any] = {"data": records}
            if hasattr(result, "columns"):
                try:
                    resp["columns"] = list(result.columns)  # type: ignore[attr-defined]
                except Exception:
                    pass
            if hasattr(result, "shape"):
                try:
                    shp = result.shape  # type: ignore[attr-defined]
                    resp["shape"] = list(shp) if not isinstance(shp, list) else shp
                except Exception:
                    pass
            log.info("Normalized domain result via to_dict(orient='records')")
            return resp
        except TypeError:
            # Fallback: plain to_dict() (e.g., pandas.Series)
            try:
                return {"data": result.to_dict()}  # type: ignore[call-arg]
            except Exception:
                pass

    if isinstance(result, list):
        return {"data": result}
    if isinstance(result, tuple):
        return {"data": list(result)}

    log.warning("Normalizing non-dict domain result to string: %s", type(result).__name__)
    return {"data": str(result)}


# ------------------------------------------------------------------------------
# Dispatcher
# ------------------------------------------------------------------------------
def call_tool(name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dispatch to either RAG or Domain registries.
    - RAG tools: dict payload -> request dataclass -> dataclass response -> dict
    - Domain tools: dict payload (plus runtime profile fallback) -> dict response
    """
    # RAG path
    fn = _RAG_TOOL_REGISTRY.get(name)
    if fn is not None:
        log.info("call_tool RAG: %s payload=%s", name, payload)
        req = _payload_to_request(name, payload)
        resp_obj = fn(req)  # type: ignore[misc]
        return _response_to_dict(resp_obj)

    # Domain path (FIXED): extract callable and pass Profile + filtered kwargs
    if name in _DOMAIN_TOOL_REGISTRY:
        entry = _DOMAIN_TOOL_REGISTRY[name]
        func = entry.get("function")
        if not callable(func):
            log.error("Registry entry for '%s' missing callable 'function': %r", name, entry)
            raise ValueError(f"INVALID_REGISTRY: '{name}' has no callable 'function'")

        profile = _resolve_profile(payload)
        allowed_args = set(entry.get("args", []))
        kwargs = {k: v for k, v in payload.items() if k != "profile" and k in allowed_args}
        ignored = sorted([k for k in payload.keys() if k not in kwargs and k != "profile"])
        if ignored:
            log.warning("Ignoring unexpected args for %s: %s (allowed=%s)", name, ignored, sorted(allowed_args))

        log.info("call_tool DOMAIN (via registry): %s args=%s", name, sorted(kwargs.keys()))
        result = func(profile, **kwargs)  # type: ignore[misc]
        if isinstance(result, dict):
            return result
        # NEW: normalize common return types (e.g., pandas DataFrame) to dict
        norm = _normalize_domain_result(result)  # NEW
        return norm  # NEW

    log.error("call_tool: unknown tool '%s'", name)
    raise ValueError(f"UNKNOWN_TOOL: '{name}' has no implementation")
