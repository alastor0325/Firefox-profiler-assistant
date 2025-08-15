"""
Bootstrap RAG backends for the runtime (search/docs) and, when configured via `.env`,
register an LLM-based summarizer for `context_summarize`.

What this does:
- Loads small on-disk artifacts for RAG (chunks and optional parents).
- Registers a minimal keyword-based search impl (placeholder until a file-backed
  vector index is wired).
- Registers a deterministic chunk/parent docs impl.
- If a provider API key is present in `.env` (e.g., GEMINI_API_KEY), registers
  an LLM summarizer via the provider-neutral adapter. Otherwise the deterministic
  fallback summarizer remains in effect.

NOTE: The ReAct "policy LLM" (deciding actions per step) is separate and is invoked
via `profiler_assistant.llm.call_model.call_model`. This module only registers the
summarizer if creds are present.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from profiler_assistant.rag.runtime import (
    register_search_impl,
    register_docs_impl,
    register_summarizer_impl,
)
from profiler_assistant.rag.summarizers.llm_adapter import make_llm_summarizer
import profiler_assistant.llm.call_model as _policy_llm  # .env-only config


# -----------------------------
# Helpers: load artifacts
# -----------------------------
def _load_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                logging.warning("bootstrap: skip bad jsonl line in %s", path)


def _tokenize(s: str) -> List[str]:
    return [t for t in "".join(ch if ch.isalnum() else " " for ch in s.lower()).split() if t]


# -----------------------------
# Search impl (keyword placeholder)
# -----------------------------
def _make_search_impl_from_chunks(chunks: List[Dict[str, Any]]):
    """
    Minimal keyword-based search over chunk texts.
    Scoring: +1.0 per exact token match (word boundary), +0.1 per substring;
    tie-break by id asc. Respects simple filters (meta equality).
    Truncates text to section_hard_limit if provided.
    """
    corpus = [
        {
            "id": str(d.get("id", "")),
            "text": str(d.get("text", "")),
            "meta": dict(d.get("meta", {})),
        }
        for d in chunks
        if d.get("id") and d.get("text") is not None
    ]

    def _score(query: str, item: Dict[str, Any]) -> float:
        q_tokens = _tokenize(query)
        hay = item["text"].lower()
        score = 0.0
        for qt in q_tokens:
            if f" {qt} " in f" {hay} ":
                score += 1.0
            elif qt in hay:
                score += 0.1
        return score

    def _passes_filters(meta: Dict[str, Any], filters: Optional[Dict[str, str]]) -> bool:
        if not filters:
            return True
        for k, v in filters.items():
            if str(meta.get(k)) != str(v):
                return False
        return True

    def search_impl(
        query: str,
        k: int,
        filters: Optional[Dict[str, str]],
        section_hard_limit: int,
        reranker: str,
    ) -> List[Dict[str, Any]]:
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for item in corpus:
            if not _passes_filters(item["meta"], filters):
                continue
            s = _score(query, item)
            if s > 0.0:
                scored.append((s, item))
        # score desc, id asc
        scored.sort(key=lambda p: (-p[0], p[1]["id"]))
        out: List[Dict[str, Any]] = []
        for score, item in scored[: max(1, k)]:
            text = item["text"]
            if section_hard_limit and section_hard_limit > 0:
                text = text[:section_hard_limit]
            out.append(
                {
                    "id": item["id"],
                    "text": text,
                    "score": float(score),
                    "meta": dict(item["meta"]),
                }
            )
        return out

    return search_impl


# -----------------------------
# Docs impl (chunk/parent/both)
# -----------------------------
def _make_docs_impl(chunks: List[Dict[str, Any]], parents: List[Dict[str, Any]]):
    """
    Deterministic chunk/parent store:
    - If parents not provided, synthesize parent docs by grouping chunks by prefix before '#'.
    - return_kind 'both' returns [chunk, parent] per input chunk; dedups while preserving order.
    """
    parent_map: Dict[str, Dict[str, Any]] = {}
    chunk_map: Dict[str, Dict[str, Any]] = {}
    parent_of: Dict[str, str] = {}

    for p in parents:
        pid = str(p.get("id", ""))
        if pid:
            parent_map[pid] = {"id": pid, "text": str(p.get("text", "")), "meta": dict(p.get("meta", {}))}

    if not parent_map:
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for c in chunks:
            cid = str(c.get("id", ""))
            if not cid:
                continue
            pid = cid.split("#", 1)[0]
            groups.setdefault(pid, []).append(c)
        for pid, group in groups.items():
            text = " ".join(str(x.get("text", ""))[:128] for x in group)[:512]
            meta = dict(group[0].get("meta", {})) if group else {}
            parent_map[pid] = {"id": pid, "text": text, "meta": meta}

    for c in chunks:
        cid = str(c.get("id", ""))
        if not cid:
            continue
        pid = c.get("parent_id") or cid.split("#", 1)[0]
        parent_of[cid] = str(pid)
        chunk_map[cid] = {"id": cid, "text": str(c.get("text", "")), "meta": dict(c.get("meta", {}))}

    def impl(ids: List[str], return_kind: str) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        if return_kind == "chunk":
            for i in ids:
                if i in chunk_map:
                    results.append(dict(chunk_map[i]))
                elif i in parent_map:
                    results.append(dict(parent_map[i]))
            return results

        if return_kind == "parent":
            seen: set[str] = set()
            order: List[str] = []
            for i in ids:
                pid = parent_of.get(i, i if i in parent_map else None)
                if pid and pid not in seen:
                    seen.add(pid)
                    order.append(pid)
            for pid in order:
                if pid in parent_map:
                    results.append(dict(parent_map[pid]))
            return results

        # both
        seen_ids: set[str] = set()
        for i in ids:
            if i in chunk_map:
                if i not in seen_ids:
                    seen_ids.add(i)
                    results.append(dict(chunk_map[i]))
                pid = parent_of.get(i)
                if pid and pid in parent_map and pid not in seen_ids:
                    seen_ids.add(pid)
                    results.append(dict(parent_map[pid]))
            elif i in parent_map and i not in seen_ids:
                seen_ids.add(i)
                results.append(dict(parent_map[i]))
        return results

    return impl


# -----------------------------
# Optional: register LLM summarizer (from `.env` only)
# -----------------------------
def _maybe_register_summarizer() -> None:
    """
    Register an LLM-backed summarizer when a provider key is present in `.env`.
    Uses the policy `call_model(messages)` for transport (provider-neutral).
    """
    try:
        if _policy_llm.has_policy_llm_config():
            register_summarizer_impl(
                make_llm_summarizer(lambda messages, max_tokens: _policy_llm.call_model(messages))
            )
            logging.info("bootstrap: registered LLM summarizer via adapter (.env detected)")
        else:
            logging.info("bootstrap: no LLM key in .env; using fallback summarizer")
    except Exception as e:
        logging.warning("bootstrap: failed to register LLM summarizer; fallback will be used: %s", e)


# -----------------------------
# Public: init all RAG pieces
# -----------------------------
def init_rag_from_config(config_path: Optional[str] = None) -> None:
    """
    Load minimal artifacts and register search/docs implementations.
    If an LLM is configured in `.env`, also register the LLM-based summarizer.

    Looks for:
      data/rag/chunks.jsonl   (required for search/docs usefulness)
      data/rag/parents.jsonl  (optional)
    """
    root = Path.cwd()
    data_dir = root / "data" / "rag"
    chunks_path = data_dir / "chunks.jsonl"
    parents_path = data_dir / "parents.jsonl"

    chunks = list(_load_jsonl(chunks_path))
    parents = list(_load_jsonl(parents_path))

    if not chunks:
        logging.warning("bootstrap: no chunks found at %s; RAG search/docs may be empty", chunks_path)

    register_search_impl(_make_search_impl_from_chunks(chunks))
    register_docs_impl(_make_docs_impl(chunks, parents))
    logging.info(
        "bootstrap: registered search/docs from %s (chunks=%d, parents=%d)",
        data_dir,
        len(chunks),
        len(parents),
    )

    # Register LLM summarizer if available; otherwise fallback summarizer remains active
    _maybe_register_summarizer()
