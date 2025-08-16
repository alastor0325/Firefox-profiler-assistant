# Purpose:
# - Ensure domain-tool dispatch normalizes a pandas.DataFrame return to a dict.
# - Guards against "'dict' object is not callable" and "INVALID_RETURN" errors.

import pandas as pd
from profiler_assistant.agent import tool_router


def test_domain_tool_dataframe_is_normalized(monkeypatch):
    calls = []

    def fake_df_tool(profile):
        calls.append(bool(profile))
        # Same columns your real tool uses when empty:
        return pd.DataFrame(columns=["markerName", "threadName", "processName", "time"])

    # Inject a fake domain tool entry directly into the registry
    monkeypatch.setitem(
        tool_router._DOMAIN_TOOL_REGISTRY,
        "dummy_df_tool",
        {"function": fake_df_tool, "args": [], "description": "dummy df tool"},
    )

    # Call through the dispatcher with a minimal payload and dummy profile
    out = tool_router.call_tool("dummy_df_tool", {"profile": object()})

    # Expect normalized dict
    assert isinstance(out, dict)
    assert "data" in out
    assert isinstance(out["data"], list)  # records
    assert out["data"] == []  # empty dataframe -> empty records
    # Optional metadata
    assert "columns" in out and set(out["columns"]) == {"markerName", "threadName", "processName", "time"}
    assert "shape" in out and out["shape"][0] == 0

    # Underlying tool was actually called
    assert calls and calls[0] is True
