"""
Defines a minimal, provider-neutral prompt for a ReAct-style loop.
The LLM must emit a single JSON object each step describing either a tool call
or a final answer. Guardrails: if the user asks for sources, include ≥1 citation.
"""
from __future__ import annotations

from typing import List, Dict

def build_agent_system_prompt() -> str:
    return (
        "You are a helpful assistant that MUST use tools to answer about the LOADED PROFILE.\n"
        "At each step, output ONE JSON object ONLY:\n"
        '  {\"action\":\"tool\",\"name\":\"<tool_name>\",\"args\":{...}}\n'
        "or\n"
        '  {\"action\":\"final\",\"answer\":\"...\",\"citations\":[\"id1\",\"id2\"]}\n'
        "- Available tools:\n"
        "  • vector_search: {\"query\":\"string\",\"k\":3}\n"
        "  • get_docs_by_id: {\"ids\":[\"doc:…\"],\"return\":\"chunk|parent|both\"}\n"
        "  • context_summarize: {\"hits\":\"$last_hits\",\"style\":\"bullet\",\"token_budget\":128}\n"
        "  • find_video_sink_dropped_frames: {}\n"
        "  • extract_process: {\"query\":\"MediaDecoder\"}  or  {\"pid\":1234}\n"
        "- If the question is about the profile (stuttering/jank/dropped frames/markers/threads/perf),\n"
        "  you MUST call a diagnostic tool before finalizing.\n"
        "- If the user asks for sources/citations, include at least one citation in the final.\n"
        "- Keep JSON strict; no text outside the JSON.\n"
    )

def seed_messages(user_question: str) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": build_agent_system_prompt()},
        {"role": "user", "content": user_question},
    ]
