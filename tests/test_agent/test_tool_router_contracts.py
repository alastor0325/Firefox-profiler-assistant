"""
Asserts that the agent tool registry exposes the declared tools and that
dispatch is not implemented in PR1 (raises NotImplementedError).
"""
from profiler_assistant.agent.tool_router import list_tools, tool_schema, call_tool


def test_list_tools_contains_declared():
    names = list_tools()
    assert set(names) == {"context_summarize", "get_docs_by_id", "vector_search"}


def test_tool_schema_shapes():
    vs = tool_schema("vector_search")
    assert vs and vs["request_type"] == "VectorSearchRequest" and vs["response_type"] == "VectorSearchResponse"

    gd = tool_schema("get_docs_by_id")
    assert gd and gd["request_type"] == "GetDocsByIdRequest" and gd["response_type"] == "GetDocsByIdResponse"

    cs = tool_schema("context_summarize")
    assert cs and cs["request_type"] == "ContextSummarizeRequest" and cs["response_type"] == "ContextSummarizeResponse"

    assert tool_schema("unknown") is None


def test_call_tool_not_implemented():
    try:
        call_tool("vector_search", {"query": "x"})
    except NotImplementedError as e:
        assert "not implemented in PR1" in str(e)
    else:
        raise AssertionError("Expected NotImplementedError")
