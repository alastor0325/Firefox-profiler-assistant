# Purpose:
# - A thin, centralized registry that exposes LLM-callable tools implemented in
#   `analysis_tools.py`. It auto-discovers public functions and surfaces their
#   name, description (from docstrings), and argument list.
# Why this file exists:
# - Decouples agent/router wiring from analysis implementation details.
# - Provides a single source of truth for what the LLM can call.
# - Improves observability via lightweight logging at registration time.
#
# Notes:
# - All business logic and detailed logging live in `analysis_tools.py`.
# - This file only discovers and registers public functions (names not starting with "_").

from __future__ import annotations

import inspect
import logging
from typing import Any, Dict, List

from profiler_assistant import analysis_tools as _analysis_tools

logger = logging.getLogger(__name__)


def _tool_args(func) -> List[str]:
    """
    Collect explicit parameter names for a tool, excluding the common `profile` param.
    """
    try:
        params = inspect.signature(func).parameters
        args: List[str] = []
        for name, p in params.items():
            if name == "profile":
                continue
            if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY):
                args.append(name)
        return args
    except Exception as e:
        logger.exception(
            "Failed to inspect function signature for %s: %r",
            getattr(func, "__name__", func),
            e,
        )
        return []


def _discover_tools_from_module(module) -> Dict[str, Dict[str, Any]]:
    """
    Discover and register all public top-level functions defined in a module.
    A "public" function is one whose name does not start with '_' and whose
    __module__ matches the provided module (to skip re-exports).
    """
    registry: Dict[str, Dict[str, Any]] = {}
    for name, obj in inspect.getmembers(module, inspect.isfunction):
        if name.startswith("_"):
            continue
        if obj.__module__ != module.__name__:
            continue  # skip re-exports
        description = (obj.__doc__ or "").strip() or f"{name} (no description)"
        entry = {
            "function": obj,
            "description": description,
            "args": _tool_args(obj),  # args beyond the required `profile`
        }
        registry[name] = entry

    logger.info(
        "Discovered %d tools from %s: %s",
        len(registry),
        module.__name__,
        sorted(registry.keys()),
    )
    return registry


# Public registry consumed by the LLM/router.
TOOLS: Dict[str, Dict[str, Any]] = _discover_tools_from_module(_analysis_tools)

__all__ = ["TOOLS"]
