"""
Agent guardrails:
- Detect when the user asked for sources
- Extract inline '(ID)' citations from text
- Validate the final answer has ≥1 citation when required and that cited IDs
  were seen by the agent via tool outputs.
"""
from __future__ import annotations

import re
from typing import List, Set

from profiler_assistant.rag.summarizers.base import extract_citations


_SOURCES_RE = re.compile(r"\b(source|sources|cite|citation|citations|reference|references)\b", re.I)


def needs_citations(user_text: str) -> bool:
    return bool(_SOURCES_RE.search(user_text or ""))


def inline_citation_ids(text: str) -> List[str]:
    # Reuse P4 extractor (returns dicts with {"id","offset"}); we just need the ids.
    return [c["id"] for c in extract_citations(text or "")]


def validate_final(
    user_text: str,
    final_answer: str,
    explicit_ids: List[str] | None,
    seen_ids: Set[str],
) -> None:
    """
    Raises ValueError with codes:
      - GUARD_CITATION_REQUIRED
      - GUARD_CITATION_UNKNOWN_ID
    """
    require = needs_citations(user_text)
    provided = list(explicit_ids or [])
    if not provided:
        # Try inline (ID) in the answer
        provided = inline_citation_ids(final_answer)

    if require and len(provided) == 0:
        raise ValueError("GUARD_CITATION_REQUIRED: user requested sources but none were provided")

    # If citations exist, ensure each is something we saw from tools
    for cid in provided:
        if cid not in seen_ids:
            raise ValueError(f"GUARD_CITATION_UNKNOWN_ID: cited id '{cid}' was not observed in tool outputs")
