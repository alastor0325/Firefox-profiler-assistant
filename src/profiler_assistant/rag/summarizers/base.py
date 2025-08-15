"""
Shared helpers for summarizers (fallback and LLM adapter).
Includes budget handling, safe concatenation, and citation extraction.
"""
from __future__ import annotations

from typing import Dict, List, Tuple


def char_budget(token_budget: int) -> int:
    # Simple proxy: ~4 chars per token (tunable)
    if token_budget <= 0:
        return 0
    return token_budget * 4


def safe_append_line(buf: str, line: str, limit: int) -> Tuple[str, bool]:
    """
    Append `line` (with a preceding newline if buf not empty) without exceeding limit.
    We do not append partial lines to avoid breaking citation offsets.
    Returns (new_buf, appended_flag).
    """
    if limit == 0:
        return buf, False
    sep = "" if not buf else "\n"
    if len(buf) + len(sep) + len(line) <= limit:
        return buf + sep + line, True
    return buf, False


def extract_citations(summary: str) -> List[Dict]:
    """
    Scan for '(ID)' citations and return [{"id": ID, "offset": (start,end)}],
    where offset indexes the ID substring (not including parentheses).
    """
    out: List[Dict] = []
    i = 0
    n = len(summary)
    while i < n:
        if summary[i] == "(":
            j = summary.find(")", i + 1)
            if j != -1 and j > i + 1:
                inner = summary[i + 1 : j]
                # Basic sanity: avoid spaces-only IDs
                if inner and inner.strip() == inner:
                    out.append({"id": inner, "offset": (i + 1, j)})
                i = j + 1
                continue
        i += 1
    return out
