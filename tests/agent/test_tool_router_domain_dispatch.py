# Purpose:
# - Ensure domain-tool dispatch uses the registry's callable under "function"
#   and never tries to call the entry dict itself (which would raise
#   "'dict' object is not callable").
#
# - Keep this test lightweight by monkeypatching the registry with a fake tool.

from profiler_assistant.agent import tool_router


def test_domain_dispatch_calls_function(monkeypatch):
    calls = []

    def fake_tool(profile, *, foo=None):
        # record that we were called with profile and kwargs
        calls.append(("ok", bool(profile), foo))
        return {"status": "ok", "foo": foo}

    # Monkeypatch a dummy domain tool entry
    monkeypatch.setitem(
        tool_router._DOMAIN_TOOL_REGISTRY,
        "dummy_domain_tool",
        {"function": fake_tool, "args": ["foo"], "description": "dummy"},
    )

    # Call through the dispatcher with a minimal payload and a dummy profile
    result = tool_router.call_tool("dummy_domain_tool", {"profile": object(), "foo": 123, "ignore": 1})

    assert result == {"status": "ok", "foo": 123}
    assert calls and calls[0] == ("ok", True, 123)
