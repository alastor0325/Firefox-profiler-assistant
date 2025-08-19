"""
Base checks always executed and validated.
"""

import json
import os
import pytest

from profiler_assistant.agent.agent_gate import ensure_general_analysis, BaseCheckError


class FakeTracer:
    def __init__(self):
        self.events = []
        self.context = {}

    def log(self, event, **payload):
        self.events.append((event, dict(payload)))


def _write_profile(tmpdir, profile_dict):
    path = os.path.join(tmpdir, "profile.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile_dict, f)
    return path


def test_base_checks_emit_event_and_pass_for_valid_profile(tmp_path):
    profile = {
        "meta": {"startTime": 0.0, "endTime": 1000.0},
        "processes": [{"pid": 1, "timeRange": {"start": 0.0, "end": 1000.0}, "markers": {"markers": []}}],
    }
    path = _write_profile(tmp_path, profile)
    tracer = FakeTracer()

    branch, reason = ensure_general_analysis(path, tracer, options={})

    assert any(e[0] == "base_checks_ran" for e in tracer.events)
    assert isinstance(branch, str) and branch != ""
    assert isinstance(reason, str)


def test_base_checks_fail_on_invalid_profile_missing_processes(tmp_path):
    profile = {"meta": {"startTime": 0.0, "endTime": 1000.0}, "processes": []}
    path = _write_profile(tmp_path, profile)
    tracer = FakeTracer()

    with pytest.raises(BaseCheckError):
        ensure_general_analysis(path, tracer, options={})


def test_base_checks_fail_on_invalid_duration(tmp_path):
    profile = {"meta": {"startTime": 10.0, "endTime": 10.0}, "processes": [{"pid": 1}]}
    path = _write_profile(tmp_path, profile)
    tracer = FakeTracer()

    with pytest.raises(BaseCheckError):
        ensure_general_analysis(path, tracer, options={})
