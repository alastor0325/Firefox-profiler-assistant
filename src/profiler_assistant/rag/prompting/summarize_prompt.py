"""
Provider-neutral prompt builder for context summarization.
Models are asked to emit explicit citation markers like [[CITE:doc_id]].
"""
from __future__ import annotations

from typing import Dict, List


def build_summarize_prompt(style: str, hits: List[Dict], token_budget: int) -> List[Dict]:
    """Return chat-style messages (system+user) for any LLM client."""
    # Compact, model-neutral instructions
    system = (
        "You are a careful assistant. Summarize ONLY from the provided context.\n"
        "Keep it concise. Do not invent facts. Respect the user's requested style.\n"
        "For every fact, append a citation marker in the form [[CITE:ID]] where ID is the source id.\n"
        f"Stay within approximately {token_budget} tokens."
    )

    # Build a small, deterministic context payload
    lines = []
    for h in hits:
        # Trim each hit text to keep prompt short; LLM adapters should set max_tokens too.
        txt = " ".join(str(h.get('text','')).split())
        if len(txt) > 300:
            txt = txt[:300] + "…"
        lines.append(f"[{h.get('id','')}] {txt}")

    style_note = {
        "bullet": "Write 3-6 short bullet points.",
        "abstract": "Write a tight paragraph.",
        "qa": "Write a short direct answer.",
    }.get(style, "Write a concise summary.")

    user = (
        f"Style: {style}\n"
        f"Guidance: {style_note}\n\n"
        "Context:\n" + "\n".join(lines) + "\n\n"
        "Output rules:\n"
        "- Use only the context above.\n"
        "- Append [[CITE:ID]] after each fact or sentence.\n"
        "- Be concise."
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
