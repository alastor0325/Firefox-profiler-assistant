"""
Contract tests updated for vector_search/get_docs_by_id and context_summarize.
Checks basic shape and citation offsets without relying on any external LLM.
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
    top_ids = [h.id for h in resp.hits[:2]]
    assert top_ids == ["doc:media-pipeline", "doc:media"]  # tie-breaker by ID


def test_vector_search_invalid_args():
    try:
        vector_search(VectorSearchRequest(query=""))
    except ValueError as e:
        assert "INVALID_ARG" in str(e)
    else:
        raise AssertionError("Expected ValueError for empty query")

    try:
        vector_search(VectorSearchRequest(query="ok", k=0))
    except ValueError as e:
        assert "INVALID_ARG" in str(e)
    else:
        raise AssertionError("Expected ValueError for k <= 0")

    try:
        vector_search(VectorSearchRequest(query="ok", section_hard_limit=-1))
    except ValueError as e:
        assert "INVALID_ARG" in str(e)
    else:
        raise AssertionError("Expected ValueError for negative section_hard_limit")


def test_get_docs_by_id_success_and_shape():
    resp = get_docs_by_id(GetDocsByIdRequest(ids=["doc:media#0-10"], return_="parent"))
    assert isinstance(resp.docs, list)
    assert len(resp.docs) == 1
    assert resp.docs[0].id == "doc:media"
    assert resp.docs[0].meta.get("title") == "Media"


def test_get_docs_by_id_invalid_args():
    try:
        get_docs_by_id(GetDocsByIdRequest(ids=[]))
    except ValueError as e:
        assert "INVALID_ARG" in str(e)
    else:
        raise AssertionError("Expected ValueError for empty ids")

    try:
        get_docs_by_id(GetDocsByIdRequest(ids=["", "doc:2"]))
    except ValueError as e:
        assert "INVALID_ARG" in str(e)
    else:
        raise AssertionError("Expected ValueError for blank id")


def test_context_summarize_success_and_offsets():
    hit_meta: Metadata = {"source": "s"}
    hits = [VectorSearchHit(id="h1", text="some fact", score=1.0, meta=hit_meta)]
    res = context_summarize(ContextSummarizeRequest(hits=hits, style="bullet", token_budget=24))
    assert isinstance(res.summary, str) and len(res.summary) > 0
    assert len(res.citations) >= 1
    for c in res.citations:
        assert res.summary[c.offset[0]:c.offset[1]] == c.id


def test_context_summarize_invalid_args():
    hit_meta: Metadata = {"source": "s"}
    hits = [VectorSearchHit(id="h1", text="t", score=1.0, meta=hit_meta)]
    try:
        context_summarize(ContextSummarizeRequest(hits=hits, token_budget=-5))
    except ValueError as e:
        assert "INVALID_ARG" in str(e)
    else:
        raise AssertionError("Expected ValueError for negative token_budget")
