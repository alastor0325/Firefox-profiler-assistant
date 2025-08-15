"""
Defines a minimal, provider-neutral prompt for a ReAct-style loop.
The LLM must emit a single JSON object each step describing either a tool call
or a final answer. Guardrails: if the user asks for sources, include ≥1 citation.
"""
from __future__ import annotations

from typing import List, Dict


def build_agent_system_prompt() -> str:
    return (
        "You are a helpful assistant that can use tools.\n"
        "At each step, output ONE JSON object with this shape:\n"
        '  {"action":"tool","name":"<tool_name>","args":{...}}\n'
        "or\n"
        '  {"action":"final","answer":"...","citations":["id1","id2"]}\n'
        "- Tool names: vector_search, get_docs_by_id, context_summarize\n"
        "- If the user requests sources/citations, include at least one citation in the final answer.\n"
        "- Keep JSON strict; no comments or extra text outside the JSON.\n"
    )


def seed_messages(user_question: str) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": build_agent_system_prompt()},
        {"role": "user", "content": user_question},
    ]
