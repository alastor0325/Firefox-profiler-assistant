"""
Test helper file.

Provides a deterministic in-memory "index" implementation for use in tests.
Used by conftest.py and other tests to simulate vector search behavior without
relying on a real backend index.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _tokenize(s: str) -> list[str]:
    return [t for t in "".join(ch if ch.isalnum() else " " for ch in s.lower()).split() if t]


def make_fixture_search(corpus: Optional[List[Dict[str, Any]]] = None):
    data = list(corpus or [])

    def search_impl(
        query: str,
        k: int,
        filters: Optional[Dict[str, str]],
        section_hard_limit: int,
        reranker: str,  # ignored in fixture
    ) -> List[Dict[str, Any]]:
        q_tokens = _tokenize(query)
        results: List[Dict[str, Any]] = []

        for doc in data:
            # Apply simple filters on meta
            meta = doc.get("meta", {})
            if filters:
                ok = True
                for key, val in filters.items():
                    if meta.get(key) != val:
                        ok = False
                        break
                if not ok:
                    continue

            text = doc["text"]
            t_tokens = _tokenize(text)

            # Exact token matches
            exact = sum(t_tokens.count(qt) for qt in q_tokens)

            # Partial substring matches (query token substring appears in original text)
            partial = 0
            tlower = text.lower()
            for qt in q_tokens:
                if qt and qt not in t_tokens and qt in tlower:
                    partial += 1

            score = exact * 1.0 + partial * 0.1

            # Only keep docs with some relevance; otherwise score 0 means weak/no match
            if score <= 0:
                continue

            # Truncate text if requested
            out_text = text if section_hard_limit <= 0 else text[:section_hard_limit]

            results.append(
                {
                    "id": doc["id"],
                    "text": out_text,
                    "score": float(score),
                    "meta": meta,
                }
            )

        # Sort: score desc, then id asc for determinism
        results.sort(key=lambda r: (-r["score"], r["id"]))

        # Top-k
        return results[: max(0, k)]

    return search_impl
