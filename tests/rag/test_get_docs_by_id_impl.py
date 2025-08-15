"""
Behavior tests for get_docs_by_id thin impl using the in-memory docs store.
Covers parent fetch, both-mode ordering, metadata presence, and invalid args.
"""
from profiler_assistant.rag.tools.get_docs_by_id import get_docs_by_id
from profiler_assistant.rag.types import GetDocsByIdRequest


def test_parent_fetch_from_chunk_id():
    req = GetDocsByIdRequest(ids=["doc:media#0-10"], return_="parent")
    resp = get_docs_by_id(req)
    assert len(resp.docs) == 1
    assert resp.docs[0].id == "doc:media"
    assert resp.docs[0].meta.get("title") == "Media"


def test_both_mode_orders_chunk_then_parent_and_dedups():
    req = GetDocsByIdRequest(ids=["doc:media#0-10"], return_="both")
    resp = get_docs_by_id(req)
    ids = [d.id for d in resp.docs]
    assert ids == ["doc:media#0-10", "doc:media"]


def test_chunk_mode_accepts_parent_ids():
    req = GetDocsByIdRequest(ids=["doc:render-thread"], return_="chunk")
    resp = get_docs_by_id(req)
    assert len(resp.docs) == 1
    assert resp.docs[0].id == "doc:render-thread"


def test_invalid_args():
    # Empty list
    try:
        get_docs_by_id(GetDocsByIdRequest(ids=[], return_="chunk"))
    except ValueError as e:
        assert "INVALID_ARG" in str(e)
    else:
        raise AssertionError("Expected ValueError for empty ids")

    # Blank id
    try:
        get_docs_by_id(GetDocsByIdRequest(ids=[""], return_="chunk"))
    except ValueError as e:
        assert "INVALID_ARG" in str(e)
    else:
        raise AssertionError("Expected ValueError for blank id")
