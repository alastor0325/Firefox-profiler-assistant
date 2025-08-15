"""
Validates router integration with stub implementations:
- tools are listed and schema is reported
- call_tool dispatches successfully and returns dict responses
- invalid/unknown tool cases are surfaced as ValueError
"""
from profiler_assistant.agent.tool_router import (
    list_tools,
    tool_schema,
    call_tool,
)


def test_list_tools_and_schema():
    names = list_tools()
    assert set(names) == {"context_summarize", "get_docs_by_id", "vector_search"}

    vs = tool_schema("vector_search")
    assert vs and vs["request_type"] == "VectorSearchRequest" and vs["response_type"] == "VectorSearchResponse"


def test_call_tool_success_paths():
    # vector_search
    resp = call_tool("vector_search", {"query": "media pipeline", "k": 2})
    assert "hits" in resp and isinstance(resp["hits"], list) and len(resp["hits"]) == 0

    # get_docs_by_id (allow 'return' alias)
    resp2 = call_tool("get_docs_by_id", {"ids": ["doc:1"], "return": "chunk"})
    assert "docs" in resp2 and isinstance(resp2["docs"], list) and len(resp2["docs"]) == 0

    # context_summarize
    resp3 = call_tool(
        "context_summarize",
        {
            "hits": [
                {
                    "id": "h1",
                    "text": "t",
                    "score": 1.0,
                    "meta": {"source": "s"},
                }
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
