"""
Provider-neutral LLM adapter for context summarization.
Accepts any client via a simple call_llm(messages,max_tokens) callable.
Parses [[CITE:ID]] markers into '(ID)' and computes offsets safely.
"""
from __future__ import annotations

from typing import Callable, Dict, List

from profiler_assistant.rag.prompting.summarize_prompt import build_summarize_prompt
from profiler_assistant.rag.summarizers.base import char_budget, extract_citations


def make_llm_summarizer(call_llm: Callable[[List[Dict], int], str]):
    def summarizer(hits: List[Dict], style: str, token_budget: int):
        messages = build_summarize_prompt(style, hits, token_budget)
        raw = call_llm(messages, token_budget) or ""

        # Replace provider-neutral markers [[CITE:ID]] -> (ID)
        out = []
        i = 0
        while i < len(raw):
            j = raw.find("[[CITE:", i)
            if j == -1:
                out.append(raw[i:])
                break
            out.append(raw[i:j])
            k = raw.find("]]", j)
            if k == -1:
                # Malformed; stop replacing
                out.append(raw[j:])
                break
            cid = raw[j + 7 : k]  # after [[CITE:
            out.append(f"({cid})")
            i = k + 2

        summary = "".join(out)

        # Enforce char budget (simple hard cap)
        limit = char_budget(token_budget)
        if limit and len(summary) > limit:
            summary = summary[:limit]

        # Extract citation offsets on (ID)
        citations = extract_citations(summary)
        return summary, citations

    return summarizer
