"""
Validates dataclass/TypedDict contracts for RAG tools:
round-trips via asdict and checks required field presence.
"""
from dataclasses import asdict

from profiler_assistant.rag.types import (
    Metadata,
    VectorSearchRequest,
    VectorSearchHit,
    VectorSearchResponse,
    GetDocsByIdRequest,
    GetDocsByIdResponse,
    Doc,
    ContextSummarizeRequest,
    ContextSummarizeResponse,
    Citation,
)


def test_vector_search_types_roundtrip():
    meta: Metadata = {
        "source": "docs/guide.md",
        "title": "Guide",
        "url": "https://example.com/guide",
        "created_at": "2025-08-14T00:00:00Z",
        "rights": "public",
        "hash": "abc123",
    }
    req = VectorSearchRequest(query="hello", k=5, section_hard_limit=1024)
    hit = VectorSearchHit(id="doc:1#0-200", text="chunk text", score=0.42, meta=meta)
    resp = VectorSearchResponse(hits=[hit])

    assert asdict(req)["query"] == "hello"
    assert asdict(resp)["hits"][0]["id"] == "doc:1#0-200"
    assert asdict(resp)["hits"][0]["meta"]["title"] == "Guide"


def test_get_docs_by_id_types_roundtrip():
    req = GetDocsByIdRequest(ids=["doc:1", "doc:2"], return_="parent")
    doc = Doc(id="doc:1#0-200", text="full text", meta={"source": "x"})
    resp = GetDocsByIdResponse(docs=[doc])

    assert asdict(req)["return_"] == "parent"
    assert asdict(resp)["docs"][0]["id"].startswith("doc:1")


def test_context_summarize_types_roundtrip():
    hit_meta: Metadata = {"source": "s"}
    hit = VectorSearchHit(id="h1", text="t", score=1.0, meta=hit_meta)
    req = ContextSummarizeRequest(hits=[hit], style="qa", token_budget=900)

    cit = Citation(id="h1", offset=(0, 5))
    resp = ContextSummarizeResponse(summary="hello", citations=[cit])

    assert asdict(req)["style"] == "qa"
    assert asdict(resp)["citations"][0]["offset"] == (0, 5)
