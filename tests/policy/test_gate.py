"""
Unit tests for the policy gating logic (decisions, injection, and source resolution).
Notes:
- Keeps assertions small and direct to ease debugging.
- Uses environment-based policy resolution to avoid file I/O.
"""

import json
import logging
import os

import pytest

from profiler_assistant.policy import gate


logger = logging.getLogger(__name__)


def test_has_policy_true_false(caplog):
    logger.info("Start test_has_policy_true_false")
    with caplog.at_level(logging.DEBUG):
        assert gate.has_policy({"policy": {}}) is True
        assert gate.has_policy({"nope": 1}) is False


@pytest.mark.parametrize(
    "flag, present, expected_action",
    [
        ("once", False, "inject"),
        ("always", False, "inject"),
        ("none", False, "bypass"),
        ("once", True, "skip"),
        ("always", True, "replace"),
        ("none", True, "bypass"),
    ],
)
def test_decide_policy_action_matrix(flag, present, expected_action, caplog):
    logger.info("Start test_decide_policy_action_matrix flag=%s present=%s", flag, present)
    with caplog.at_level(logging.INFO):
        profile = {"policy": {"k": 1}} if present else {}
        decision = gate.decide_policy_action(profile, flag)
        assert decision["action"] == expected_action


def test_inject_policy_preserves_fields(caplog):
    logger.info("Start test_inject_policy_preserves_fields")
    with caplog.at_level(logging.INFO):
        base = {"a": 1, "b": 2}
        policy = {"rules": [{"allow": "all"}]}
        out = gate.inject_policy(base, policy)
        assert out is not base  # immutability (copied)
        assert out["a"] == 1 and out["b"] == 2
        assert out["policy"] == policy


def test_load_default_policy_env_string(monkeypatch, caplog):
    logger.info("Start test_load_default_policy_env_string")
    with caplog.at_level(logging.INFO):
        payload = {"rules": [{"deny": "nothing"}]}
        monkeypatch.setenv("PROFILER_ASSISTANT_POLICY", json.dumps(payload))
        loaded = gate.load_default_policy()
        assert loaded == payload
