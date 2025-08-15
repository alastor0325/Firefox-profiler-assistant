"""
Tiny runtime registries for plugging in production RAG implementations.
Provides search and docs fetch registries used by tools and tests.
"""
from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional, Any

# ---- Search impl registry ----

SearchImpl = Callable[[str, int, Optional[Dict[str, str]], int, str], List[Dict[str, Any]]]
_SEARCH_IMPL: Optional[SearchImpl] = None


def register_search_impl(fn: SearchImpl) -> None:
    """Register the active search implementation (call once at app bootstrap or in tests)."""
    global _SEARCH_IMPL
    logging.info("register_search_impl: %s", getattr(fn, "__name__", str(fn)))
    _SEARCH_IMPL = fn


def get_search_impl() -> SearchImpl:
    """Return the active search implementation or raise if unset."""
    if _SEARCH_IMPL is None:
        logging.error("get_search_impl: missing implementation")
        raise RuntimeError("INDEX_NOT_CONFIGURED: no search implementation registered")
    return _SEARCH_IMPL


def clear_search_impl() -> None:
    """Clear the active search implementation (used by tests)."""
    global _SEARCH_IMPL
    logging.info("clear_search_impl")
    _SEARCH_IMPL = None


# ---- Docs impl registry ----

DocsImpl = Callable[[List[str], str], List[Dict[str, Any]]]
_DOCS_IMPL: Optional[DocsImpl] = None


def register_docs_impl(fn: DocsImpl) -> None:
    """Register the active docs implementation (call once at app bootstrap or in tests)."""
    global _DOCS_IMPL
    logging.info("register_docs_impl: %s", getattr(fn, "__name__", str(fn)))
    _DOCS_IMPL = fn


def get_docs_impl() -> DocsImpl:
    """Return the active docs implementation or raise if unset."""
    if _DOCS_IMPL is None:
        logging.error("get_docs_impl: missing implementation")
        raise RuntimeError("DOCS_NOT_CONFIGURED: no docs implementation registered")
    return _DOCS_IMPL


def clear_docs_impl() -> None:
    """Clear the active docs implementation (used by tests)."""
    global _DOCS_IMPL
    logging.info("clear_docs_impl")
    _DOCS_IMPL = None
