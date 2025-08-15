"""
A tiny, model-agnostic ReAct loop that coordinates tool calls via the router.
Each step expects the LLM to emit a single JSON object describing a tool call
or a final answer. Includes guardrails for source/citation requirements.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from profiler_assistant.agent.tool_router import call_tool
from profiler_assistant.agent.prompting.agent_prompt import seed_messages
from profiler_assistant.agent.guards import validate_final


def _strip_fences(txt: str) -> str:
    if not txt:
        return txt
    s = txt.strip()
    if s.startswith("```"):
        # Remove leading triple backtick block (optionally with language)
        first_nl = s.find("\n")
        if first_nl != -1:
            s = s[first_nl + 1 :]
        if s.endswith("```"):
            s = s[: -3]
    return s.strip()


def _parse_action(raw: str) -> Dict[str, Any]:
    s = _strip_fences(raw)
    try:
        obj = json.loads(s)
    except Exception as e:
        raise ValueError(f"PARSE_ERROR: expected a JSON object, got: {raw!r}") from e
    if not isinstance(obj, dict):
        raise ValueError("PARSE_ERROR: JSON must be an object")
    return obj


def _collect_seen_ids(result: Dict[str, Any], accum: set[str]) -> None:
    # Record ids from tool results for guard checks
    if "hits" in result and isinstance(result["hits"], list):
        for h in result["hits"]:
            hid = h.get("id")
            if isinstance(hid, str):
                accum.add(hid)
    if "docs" in result and isinstance(result["docs"], list):
        for d in result["docs"]:
            did = d.get("id")
            if isinstance(did, str):
                accum.add(did)
    # context_summarize returns only summary+citations (offsets). We don't add their ids
    # here; the ids should already have been seen from retrieval.


def run_react(
    question: str,
    call_model: Any,
    max_steps: int = 6,
) -> Dict[str, Any]:
    """
    Runs a minimal ReAct loop until a final action is produced or max_steps hit.

    Args:
        question: user question text
        call_model: callable(messages: list[dict]) -> str
        max_steps: max number of tool/think iterations

    Returns:
        dict with keys: answer (str), citations (list[str]), steps (list[dict])
    """
    messages: List[Dict[str, str]] = seed_messages(question)
    steps: List[Dict[str, Any]] = []
    last_result: Dict[str, Any] | None = None
    seen_ids: set[str] = set()

    for _ in range(max_steps):
        raw = call_model(messages)
        action = _parse_action(raw)

        kind = action.get("action")
        steps.append({"action": action})

        if kind == "tool":
            name = action.get("name")
            if not isinstance(name, str) or not name:
                raise ValueError("TOOL_ACTION_ERROR: 'name' must be a non-empty string")
            args = action.get("args") or {}
            # Convenience for tests: allow "$last_hits" placeholder
            if "hits" in args and args["hits"] == "$last_hits":
                if last_result and "hits" in last_result:
                    args = dict(args)
                    args["hits"] = last_result["hits"]
                else:
                    args = dict(args)
                    args["hits"] = []

            result = call_tool(name, args)
            _collect_seen_ids(result, seen_ids)
            steps[-1]["observation"] = result

            # Append observation into conversation for model context
            messages.append({"role": "assistant", "content": json.dumps({"tool_result": result})})
            last_result = result
            continue

        if kind == "final":
            answer = action.get("answer") or ""
            citations = list(action.get("citations") or [])
            # Guardrails
            validate_final(question, answer, citations, seen_ids)
            return {"answer": answer, "citations": citations, "steps": steps}

        raise ValueError(f"INVALID_ACTION: {kind!r} not supported")

    raise ValueError("MAX_STEPS_EXCEEDED")
