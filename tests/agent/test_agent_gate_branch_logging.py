"""
Branch chosen is logged with branch + reason (config-driven).
"""

import json
import os

from profiler_assistant.agent.agent_gate import ensure_general_analysis


class FakeTracer:
    def __init__(self):
        self.events = []
        self.context = {}

    def log(self, event, **payload):
        self.events.append((event, dict(payload)))

    def get(self, event):
        return [p for e, p in self.events if e == event]


def _write_profile(tmpdir, profile_dict):
    path = os.path.join(tmpdir, "profile.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile_dict, f)
    return path


def test_branch_selected_event_contains_branch_and_reason(tmp_path):
    profile = {
        "meta": {"startTime": 0.0, "endTime": 1000.0},
        "processes": [
            {
                "pid": 1,
                "timeRange": {"start": 0.0, "end": 1000.0},
                "markers": {"markers": [{"name": "VideoSink"}, {"name": "VideoSink"}, {"name": "MediaDecoderStateMachine"}]},
            }
        ],
    }
    path = _write_profile(tmp_path, profile)
    tracer = FakeTracer()

    options = {
        "analysis_rules": {
            "branches": [
                {
                    "name": "media",
                    "score": 1.0,
                    "reason": "media markers present: {count}",
                    "markers": {"any": ["VideoSink", "MediaDecoderStateMachine"]},
                    "min_count": 2,
                }
            ]
        }
    }

    branch, reason = ensure_general_analysis(path, tracer, options=options)

    selected = tracer.get("branch_selected")
    assert selected, "branch_selected event not emitted"
    assert selected[0]["branch"] == "media"
    assert "media" in selected[0]["reason"]
    assert branch == "media"
    assert "media" in reason
