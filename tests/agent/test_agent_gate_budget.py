"""
Enforce branch budget (limit 3), log increments, raise on 4th.
"""

import json
import os
import pytest

from profiler_assistant.agent.agent_gate import ensure_general_analysis, BranchBudgetExceeded


class FakeTracer:
    def __init__(self):
        self.events = []
        self.context = {}

    def log(self, event, **payload):
        self.events.append((event, dict(payload)))

    def counts(self, event):
        return [p["count"] for e, p in self.events if e == event and "count" in p]


def _write_profile(tmpdir, profile_dict):
    path = os.path.join(tmpdir, "profile.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile_dict, f)
    return path


def _valid_profile():
    return {
        "meta": {"startTime": 0.0, "endTime": 1000.0},
        "processes": [{"pid": 1, "timeRange": {"start": 0.0, "end": 1000.0}, "markers": {"markers": []}}],
    }


def test_budget_increments_and_exceeds_on_fourth_call(tmp_path):
    path = _write_profile(tmp_path, _valid_profile())
    tracer = FakeTracer()

    opts = {"branch_budget_limit": 3}

    for _ in range(3):
        ensure_general_analysis(path, tracer, options=opts)

    counts = tracer.counts("branch_budget")
    assert counts == [1, 2, 3]

    with pytest.raises(BranchBudgetExceeded):
        ensure_general_analysis(path, tracer, options=opts)
