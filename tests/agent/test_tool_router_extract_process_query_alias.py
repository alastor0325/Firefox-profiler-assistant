"""
Verify the tool router maps 'query' -> 'name' for the 'extract_process' domain tool,
avoids logging "unexpected args" for 'query', and properly calls the registered function.

Notes:
    - Stays consistent with module-level test style (import tool_router module).
    - Includes basic logging in the fake tool to aid debugging if this ever flakes.
"""

import logging
from profiler_assistant.agent import tool_router


def test_extract_process_accepts_query_alias(monkeypatch, caplog):
    calls = []

    def fake_extract_process(profile, *, name=None, pid=None):
        # helpful logging for debug
        logging.getLogger(__name__).info(
            "fake_extract_process called with profile=%s name=%r pid=%r",
            bool(profile), name, pid
        )
        calls.append((bool(profile), name, pid))
        return {"ok": True, "name": name, "pid": pid}

    # Monkeypatch the registry entry to a controlled fake.
    # Include 'query' in args so allow-list shows it as permitted.
    monkeypatch.setitem(
        tool_router._DOMAIN_TOOL_REGISTRY,
        "extract_process",
        {"function": fake_extract_process, "args": ["name", "pid", "query"], "description": "fake"},
    )

    with caplog.at_level(logging.INFO):
        res = tool_router.call_tool(
            "extract_process",
            {"profile": object(), "query": "Content Process", "ignored_arg": "x"},
        )

    # Result correctness
    assert res["ok"] is True
    assert res["name"] == "Content Process"
    assert res["pid"] is None

    # Ensure our fake was actually called with mapped args
    assert calls and calls[0] == (True, "Content Process", None)

    # Confirm the alias mapping log happened
    assert any(
        "Mapped 'query' -> 'name' for extract_process" in r.getMessage()
        for r in caplog.records
    )

    # Ensure we did NOT warn about 'query' being unexpected
    assert not any(
        "Ignoring unexpected args" in r.getMessage() and "query" in r.getMessage()
        for r in caplog.records
    )
