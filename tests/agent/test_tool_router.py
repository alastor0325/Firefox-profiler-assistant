"""
Router integration test using fixture search and docs stores.
Ensures non-empty results and stable ordering through call_tool.
"""
from profiler_assistant.agent.tool_router import list_tools, tool_schema, call_tool


def test_list_tools_and_schema():
    names = list_tools()
    assert set(names) == {"context_summarize", "get_docs_by_id", "vector_search"}

    vs = tool_schema("vector_search")
    assert vs and vs["request_type"] == "VectorSearchRequest" and vs["response_type"] == "VectorSearchResponse"


def test_call_tool_success_paths():
    # vector_search
    resp = call_tool("vector_search", {"query": "media pipeline", "k": 2})
    ids = [h["id"] for h in resp["hits"]]
    # Tie-breaker is lexicographic ID on equal scores; 'doc:media' < 'doc:render-thread'
    assert ids == ["doc:media-pipeline", "doc:media"]

    # get_docs_by_id (use 'return' alias; fetch parent from a chunk id)
    resp2 = call_tool("get_docs_by_id", {"ids": ["doc:media#0-10"], "return": "parent"})
    assert "docs" in resp2 and isinstance(resp2["docs"], list) and len(resp2["docs"]) == 1
    assert resp2["docs"][0]["id"] == "doc:media"
    assert resp2["docs"][0]["meta"].get("title") == "Media"

    # context_summarize
    resp3 = call_tool(
        "context_summarize",
        {
            "hits": [
                {"id": "h1", "text": "t", "score": 1.0, "meta": {"source": "s"}},
            ],
            "style": "bullet",
            "token_budget": 10,
        },
    )
    assert resp3.get("summary") == "No context provided yet."
    assert isinstance(resp3.get("citations"), list)


def test_call_tool_invalid_args_and_unknown_tool():
    # Unknown tool
    try:
        call_tool("nope", {})
    except ValueError as e:
        assert "UNKNOWN_TOOL" in str(e)
    else:
        raise AssertionError("Expected ValueError for unknown tool")

    # Invalid args: vector_search requires non-empty query
    try:
        call_tool("vector_search", {"query": ""})
    except ValueError as e:
        assert "INVALID_ARG" in str(e)
    else:
        raise AssertionError("Expected ValueError for invalid query")
