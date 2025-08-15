"""
Defines the public data contracts (request/response/error/metadata types)
for RAG tools: vector_search, get_docs_by_id, and context_summarize.
No implementations here; these shapes are used by tools and the agent.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict, Literal, Optional, List, Dict, Tuple


# ---- Shared / metadata ----

class Metadata(TypedDict, total=False):
    """Common metadata attached to retrieved chunks or documents."""
    source: str           # e.g., file path or logical source id
    title: str            # human-friendly title
    url: str              # original URL if any
    created_at: str       # ISO8601 timestamp string
    rights: str           # e.g., "public", "internal_only"
    hash: str             # stable content hash for chunk


@dataclass(frozen=True)
class ToolError:
    """Typed error returned by tools when a recoverable issue is encountered."""
    code: Literal["NOT_FOUND", "TIMEOUT", "RATE_LIMIT", "INVALID_ARG"]
    message: str


# ---- vector_search ----

@dataclass(frozen=True)
class VectorSearchRequest:
    """Input schema for semantic (and optionally hybrid) retrieval."""
    query: str
    k: int = 8
    filters: Optional[Dict[str, str]] = None
    reranker: Literal["none", "cross_encoder", "LLM"] = "none"
    section_hard_limit: int = 2048


@dataclass(frozen=True)
class VectorSearchHit:
    """A single retrieved chunk with score and metadata."""
    id: str
    text: str
    score: float
    meta: Metadata


@dataclass(frozen=True)
class VectorSearchResponse:
    """Top‑k retrieval results."""
    hits: List[VectorSearchHit]


# ---- get_docs_by_id ----

@dataclass(frozen=True)
class GetDocsByIdRequest:
    """Fetches chunks and/or parent documents by their IDs."""
    ids: List[str]
    # 'return' is a keyword in Python; use 'return_' as the field name.
    return_: Literal["chunk", "parent", "both"] = "chunk"


@dataclass(frozen=True)
class Doc:
    """A chunk or parent document with associated metadata."""
    id: str
    text: str
    meta: Metadata


@dataclass(frozen=True)
class GetDocsByIdResponse:
    """Resolved documents corresponding to requested IDs."""
    docs: List[Doc]


# ---- context_summarize ----

@dataclass(frozen=True)
class Citation:
    """Inline citation span mapping back to a retrieved source ID."""
    id: str
    # Character offsets into the summary string. Inclusive start, exclusive end.
    offset: Tuple[int, int]


@dataclass(frozen=True)
class ContextSummarizeRequest:
    """Specifies inputs and constraints for summarizing retrieved context."""
    hits: List[VectorSearchHit]
    style: Literal["bullet", "abstract", "qa"] = "bullet"
    token_budget: int = 1200


@dataclass(frozen=True)
class ContextSummarizeResponse:
    """Summarized context plus inline citations."""
    summary: str
    citations: List[Citation]
