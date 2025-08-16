"""
React-agent wrapper and tool descriptors for the CLI.

- describe_tools() -> str
  Returns a compact, human-readable list of available tools:
    - RAG tools with their request/response types (from router schemas)
    - Domain tools discovered in profiler_assistant.tools (public callables)

- run_react_agent(profile, question, history) -> {"final": "..."} | {"error": "..."}
  Bridges the existing CLI (run.py) to the ReAct loop. It bootstraps RAG
  backends once, runs the agent, and appends a 'Sources:' line when citations exist.
"""
from __future__ import annotations

import logging
import profiler_assistant.llm.call_model as _call_model_mod
from typing import Any, Dict, List
from profiler_assistant.app.bootstrap import init_rag_from_config
from profiler_assistant.agent.react import run_react
from profiler_assistant.runtime.context import set_current_profile
from profiler_assistant.agent.tool_router import (
    list_rag_tools as _list_rag_tools,
    list_domain_tools as _list_domain_tools,
    tool_schema as _tool_schema,
)

_RAG_BOOTSTRAPPED = False


def _ensure_bootstrap() -> None:
    """Idempotently register search/docs (and LLM summarizer if configured)."""
    global _RAG_BOOTSTRAPPED
    if not _RAG_BOOTSTRAPPED:
        try:
            init_rag_from_config()
            _RAG_BOOTSTRAPPED = True
        except Exception as e:
            # Non-fatal: agent runs, but tools may return empty if no artifacts.
            logging.warning("react_agent: bootstrap failed: %s", e)


def describe_tools() -> str:
    """
    Return a compact string description of available tools.

    RAG tool lines:
      <name>: <RequestType> -> <ResponseType>

    Followed by a "domain tools:" section listing public callables found in
    profiler_assistant.tools and any of its submodules (best-effort).
    """
    rows: List[str] = []

    # RAG tools (from router schemas)
    try:
        for name in sorted(_list_rag_tools()):
            schema = _tool_schema(name) or {}
            req = str(schema.get("request_type", ""))
            resp = str(schema.get("response_type", ""))
            rows.append(f"{name}: {req} -> {resp}")
    except Exception as e:
        rows.append(f"[warn] failed to enumerate RAG tools: {e}")

    # Domain tools (from router; avoids fragile import scanning)
    try:
        domain_names = sorted(_list_domain_tools())
        if domain_names:
            rows.append("")
            rows.append("domain tools:")
            for n in domain_names:
                rows.append(f"- {n}")
    except Exception:
        pass

    return "\n".join(rows)


def run_react_agent(profile: Dict[str, Any], question: str, history: List[Dict[str, str]]) -> Dict[str, str]:
    """
    CLI entry wrapper used by run.py.
    """
    _ensure_bootstrap()

    try:
        # ✅ make the loaded profile visible to domain tools
        set_current_profile(profile)

        result = run_react(question, _call_model_mod.call_model, max_steps=6)
        final_text = result.get("answer", "")
        cits = result.get("citations") or []
        if cits:
            final_text = f"{final_text}\nSources: {', '.join(cits)}"
        return {"final": final_text}
    except ValueError as e:
        msg = str(e)
        if "GUARD_CITATION_REQUIRED" in msg:
            return {"error": "GUARD_CITATION_REQUIRED"}
        return {"error": f"GUARD: {msg}"}
    except RuntimeError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"agent error: {e}"}
