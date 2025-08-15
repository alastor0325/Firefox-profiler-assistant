"""
Test helper file.

Provides a deterministic in-memory "docs store" with parents and chunks.
Used to simulate get_docs_by_id behavior without a real backend.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def make_fixture_docs(corpus: Optional[List[Dict[str, Any]]] = None):
    data = list(corpus or [])

    parents: Dict[str, Dict[str, Any]] = {}
    chunks: Dict[str, Dict[str, Any]] = {}
    parent_of: Dict[str, str] = {}

    for doc in data:
        doc_id = doc["id"]
        if "parent_id" in doc:
            chunks[doc_id] = doc
            parent_of[doc_id] = doc["parent_id"]
        else:
            parents[doc_id] = doc

    def _parent_id_of(doc_id: str) -> Optional[str]:
        if doc_id in parent_of:
            return parent_of[doc_id]
        if doc_id in parents:
            return doc_id
        return None

    def docs_impl(ids: List[str], return_kind: str) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        if return_kind == "chunk":
            for i in ids:
                if i in chunks:
                    results.append(_normalize(chunks[i]))
                elif i in parents:
                    results.append(_normalize(parents[i]))
            return results

        if return_kind == "parent":
            seen: set[str] = set()
            ordered_parent_ids: List[str] = []
            for i in ids:
                pid = _parent_id_of(i)
                if pid and pid not in seen:
                    seen.add(pid)
                    ordered_parent_ids.append(pid)
            for pid in ordered_parent_ids:
                if pid in parents:
                    # Removed walrus operator for broader Python compatibility
                    results.append(_normalize(parents[pid]))
            return results

        # return_kind == "both"
        seen_ids: set[str] = set()
        for i in ids:
            if i in chunks:
                if i not in seen_ids:
                    seen_ids.add(i)
                    results.append(_normalize(chunks[i]))
                pid = _parent_id_of(i)
                if pid and pid in parents and pid not in seen_ids:
                    seen_ids.add(pid)
                    results.append(_normalize(parents[pid]))
            elif i in parents and i not in seen_ids:
                seen_ids.add(i)
                results.append(_normalize(parents[i]))
        return results

    def _normalize(d: Dict[str, Any]) -> Dict[str, Any]:
        # Ensure shape: id, text, meta
        return {
            "id": d["id"],
            "text": d["text"],
            "meta": dict(d.get("meta", {})),
        }

    return docs_impl
