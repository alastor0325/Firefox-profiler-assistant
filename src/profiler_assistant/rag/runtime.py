"""
Tiny runtime registry for plugging in the production search implementation.
Tests use this to register a deterministic in-memory search.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Any

# Signature the search implementation must follow.
SearchImpl = Callable[[str, int, Optional[Dict[str, str]], int, str], List[Dict[str, Any]]]

_SEARCH_IMPL: Optional[SearchImpl] = None


def register_search_impl(fn: SearchImpl) -> None:
    """Register the active search implementation (call once at app bootstrap or in tests)."""
    global _SEARCH_IMPL
    _SEARCH_IMPL = fn


def get_search_impl() -> SearchImpl:
    """Return the active search implementation or raise if unset."""
    if _SEARCH_IMPL is None:
        raise RuntimeError("INDEX_NOT_CONFIGURED: no search implementation registered")
    return _SEARCH_IMPL


def clear_search_impl() -> None:
    """Clear the active search implementation (used by tests)."""
    global _SEARCH_IMPL
    _SEARCH_IMPL = None
