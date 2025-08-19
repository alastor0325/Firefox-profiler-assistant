"""
CLI integration tests exercising:
- default-to-report dispatch
- policy flag behavior (once/always/none)
- acceptance of profile inputs (path/URL/raw JSON) via run module's loader
- gate decision log lines emitted under logger 'profiler_assistant.policy'

These tests monkeypatch run.py internals to avoid I/O and external calls.
"""

import json
import logging

import builtins
import pytest

import profiler_assistant.cli.run as run_mod


LOG = logging.getLogger(__name__)
POLICY_LOG_NAME = "profiler_assistant.policy"


def _fake_load_profile_from_source_factory(sequence):
    """
    Returns a function that, on each call, pops and returns the next (profile, resolved, is_temp).
    Helpful to simulate 'first run has no policy' then 'second run already has policy'.
    """
    seq = list(sequence)

    def _impl(_source):
        if not seq:
            raise AssertionError("Test sequence exhausted; adjust your test setup.")
        return seq.pop(0)

    return _impl


def _stub_run_react_agent(profile, question, history):
    # Minimal predictable result for tests
    return {"final": f"[stubbed-answer] Q={question[:30]}… policy={'yes' if 'policy' in profile else 'no'}"}


def _seed_caplog(caplog):
    caplog.clear()
    caplog.set_level(logging.INFO)
    logging.getLogger(POLICY_LOG_NAME).setLevel(logging.INFO)


def test_default_to_agent_argv_basic():
    LOG.info("Start: test_default_to_agent_argv_basic")
    assert run_mod._default_to_agent_argv(["some_profile.json"]) == ["agent", "some_profile.json"]
    assert run_mod._default_to_agent_argv(["agent", "p.json"]) == ["agent", "p.json"]
    assert run_mod._default_to_agent_argv(["report", "p.json"]) == ["report", "p.json"]


def test_report_default_path_with_raw_json(monkeypatch, caplog):
    LOG.info("Start: test_report_default_path_with_raw_json")
    _seed_caplog(caplog)

    # Arrange: when run as default (no subcommand), the first arg is profile -> 'report'
    raw_profile = {"x": 1}  # no policy initially
    sequence = [
        (raw_profile, "<raw-json>", False),
    ]
    monkeypatch.setattr(run_mod, "_load_profile_from_source", _fake_load_profile_from_source_factory(sequence))
    monkeypatch.setattr(run_mod, "run_react_agent", _stub_run_react_agent)
    monkeypatch.setattr(run_mod, "refresh_rag_knowledge_index", lambda: None)

    # Act
    # We call the inner handler to avoid sys.exit in main; this mirrors dispatch
    exit_code = run_mod._run_report(json.dumps(raw_profile), policy_flag="once")

    # Assert
    assert exit_code == 0
    # Policy should have been injected since it was absent
    assert any("step=decide_policy" in rec.message and "action=inject" in rec.message for rec in caplog.records if rec.name == POLICY_LOG_NAME)


def test_policy_once_then_skip(monkeypatch, caplog):
    LOG.info("Start: test_policy_once_then_skip")
    _seed_caplog(caplog)

    # First invocation: profile without policy -> inject
    seq1 = [({}, "p1", False)]
    monkeypatch.setattr(run_mod, "_load_profile_from_source", _fake_load_profile_from_source_factory(seq1))
    monkeypatch.setattr(run_mod, "run_react_agent", _stub_run_react_agent)
    monkeypatch.setattr(run_mod, "refresh_rag_knowledge_index", lambda: None)
    code1 = run_mod._run_report("any", policy_flag="once")
    assert code1 == 0
    assert any("action=inject" in r.message for r in caplog.records if r.name == POLICY_LOG_NAME)

    caplog.clear()
    _seed_caplog(caplog)

    # Second invocation: profile comes in with policy -> skip
    seq2 = [({"policy": {"rules": []}}, "p2", False)]
    monkeypatch.setattr(run_mod, "_load_profile_from_source", _fake_load_profile_from_source_factory(seq2))
    code2 = run_mod._run_report("any", policy_flag="once")
    assert code2 == 0
    assert any("action=skip" in r.message for r in caplog.records if r.name == POLICY_LOG_NAME)


def test_policy_always_reinject(monkeypatch, caplog):
    LOG.info("Start: test_policy_always_reinject")
    _seed_caplog(caplog)

    seq = [({"policy": {"rules": [{"old": True}]}}, "p", False)]
    monkeypatch.setattr(run_mod, "_load_profile_from_source", _fake_load_profile_from_source_factory(seq))
    monkeypatch.setattr(run_mod, "run_react_agent", _stub_run_react_agent)
    monkeypatch.setattr(run_mod, "refresh_rag_knowledge_index", lambda: None)

    code = run_mod._run_report("any", policy_flag="always")
    assert code == 0
    assert any("action=replace" in r.message for r in caplog.records if r.name == POLICY_LOG_NAME)


def test_no_policy_bypass(monkeypatch, caplog):
    LOG.info("Start: test_no_policy_bypass")
    _seed_caplog(caplog)

    seq = [({}, "p", False)]
    monkeypatch.setattr(run_mod, "_load_profile_from_source", _fake_load_profile_from_source_factory(seq))
    monkeypatch.setattr(run_mod, "run_react_agent", _stub_run_react_agent)
    monkeypatch.setattr(run_mod, "refresh_rag_knowledge_index", lambda: None)

    code = run_mod._run_report("any", policy_flag="none")
    assert code == 0
    assert any("action=bypass" in r.message for r in caplog.records if r.name == POLICY_LOG_NAME)


def test_agent_loop_exits_immediately_on_quit(monkeypatch, caplog):
    LOG.info("Start: test_agent_loop_exits_immediately_on_quit")
    _seed_caplog(caplog)

    # Ensure the agent loop sees 'exit' immediately and returns 0.
    seq = [({"policy": {"rules": []}}, "p", False)]
    monkeypatch.setattr(run_mod, "_load_profile_from_source", _fake_load_profile_from_source_factory(seq))
    monkeypatch.setattr(run_mod, "run_react_agent", _stub_run_react_agent)
    monkeypatch.setattr(run_mod, "refresh_rag_knowledge_index", lambda: None)

    # Simulate user typing 'exit' at first prompt
    it = iter(["exit"])
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(it))

    code = run_mod._run_agent("any", policy_flag="once")
    assert code == 0
