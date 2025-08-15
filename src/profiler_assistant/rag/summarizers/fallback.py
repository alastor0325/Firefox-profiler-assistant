"""
Deterministic, dependency-free summarizer used when no LLM is registered.
Builds a short summary from hits and includes '(id)' citations with safe offsets.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from profiler_assistant.rag.summarizers.base import char_budget, safe_append_line, extract_citations


def _clean_snippet(text: str, max_len: int) -> str:
    s = " ".join(text.split())
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def fallback_summarize(hits: List[Dict], style: str, token_budget: int) -> (str, List[Dict]):  # type: ignore[type-arg]
    limit = char_budget(token_budget)
    if limit <= 0 or not hits:
        return "", []

    # Per-line snippet allowance (rough heuristic so multiple items can fit)
    per_line = max(24, min(140, limit // 4))

    if style == "abstract":
        # Join 1-3 compact sentences with citations
        buf = ""
        count = 0
        for h in hits:
            if count >= 3:
                break
            snippet = _clean_snippet(str(h.get("text", "")), per_line)
            line = f"{snippet} ({h.get('id','')})."
            new_buf, ok = safe_append_line(buf, line, limit)
            if not ok:
                break
            buf = new_buf
            count += 1
        return buf, extract_citations(buf)

    if style == "qa":
        # Short "Answer: ..." followed by one or two cited facts
        buf = ""
        header, ok = safe_append_line(buf, "Answer:", limit)
        if ok:
            buf = header
        count = 0
        for h in hits:
            if count >= 2:
                break
            snippet = _clean_snippet(str(h.get("text", "")), per_line)
            line = f"{snippet} ({h.get('id','')})"
            new_buf, ok = safe_append_line(buf, line, limit)
            if not ok:
                break
            buf = new_buf
            count += 1
        return buf, extract_citations(buf)

    # Default: bullet style
    buf = ""
    for h in hits:
        snippet = _clean_snippet(str(h.get("text", "")), per_line)
        line = f"• {snippet} ({h.get('id','')})"
        new_buf, ok = safe_append_line(buf, line, limit)
        if not ok:
            break
        buf = new_buf

    return buf, extract_citations(buf)
