"""
Contract tests updated to expect non-empty results from the fixture index.
Invalid-arg paths remain the same.
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
from profiler_assistant.rag.tools.vector_search import vector_search
from profiler_assistant.rag.tools.get_docs_by_id import get_docs_by_id
from profiler_assistant.rag.tools.context_summarize import context_summarize


def test_vector_search_success_and_shape():
    req = VectorSearchRequest(query="media pipeline", k=3, section_hard_limit=512)
    resp = vector_search(req)
    assert isinstance(resp.hits, list)
    assert len(resp.hits) >= 2
    # Deterministic top-2 IDs based on fixture corpus and score rules
    top_ids = [h.id for h in resp.hits[:2]]
    # Tie-breaker is lexicographic ID on equal scores; 'doc:media' < 'doc:render-thread'
    assert top_ids == ["doc:media-pipeline", "doc:media"]


def test_vector_search_invalid_args():
    # Empty query
    try:
        vector_search(VectorSearchRequest(query=""))
    except ValueError as e:
        assert "INVALID_ARG" in str(e)
    else:
        raise AssertionError("Expected ValueError for empty query")

    # Non-positive k
    try:
        vector_search(VectorSearchRequest(query="ok", k=0))
    except ValueError as e:
        assert "INVALID_ARG" in str(e)
    else:
        raise AssertionError("Expected ValueError for k <= 0")

    # Negative section_hard_limit
    try:
        vector_search(VectorSearchRequest(query="ok", section_hard_limit=-1))
    except ValueError as e:
        assert "INVALID_ARG" in str(e)
    else:
        raise AssertionError("Expected ValueError for negative section_hard_limit")


def test_get_docs_by_id_success_and_shape():
    req = GetDocsByIdRequest(ids=["doc:1"], return_="chunk")
    resp = get_docs_by_id(req)
    assert isinstance(resp.docs, list)
    assert len(resp.docs) == 0


def test_get_docs_by_id_invalid_args():
    # Empty list
    try:
        get_docs_by_id(GetDocsByIdRequest(ids=[]))
    except ValueError as e:
        assert "INVALID_ARG" in str(e)
    else:
        raise AssertionError("Expected ValueError for empty ids")

    # Bad entry
    try:
        get_docs_by_id(GetDocsByIdRequest(ids=["", "doc:2"]))
    except ValueError as e:
        assert "INVALID_ARG" in str(e)
    else:
        raise AssertionError("Expected ValueError for blank id")


def test_context_summarize_success_and_shape():
    hit_meta: Metadata = {"source": "s"}
    hits = [VectorSearchHit(id="h1", text="t", score=1.0, meta=hit_meta)]
    req = ContextSummarizeRequest(hits=hits, style="bullet", token_budget=100)
    resp = context_summarize(req)
    assert isinstance(resp.summary, str)
    assert resp.summary == "No context provided yet."
    assert isinstance(resp.citations, list)
    assert len(resp.citations) == 0


def test_context_summarize_invalid_args():
    # Negative budget
    hit_meta: Metadata = {"source": "s"}
    hits = [VectorSearchHit(id="h1", text="t", score=1.0, meta=hit_meta)]
    try:
        context_summarize(ContextSummarizeRequest(hits=hits, token_budget=-5))
    except ValueError as e:
        assert "INVALID_ARG" in str(e)
    else:
        raise AssertionError("Expected ValueError for negative token_budget")
