"""
Verify that decision tracing produces:
    - a decision span with measurable duration
    - a single chosen-branch annotation
    - optional per-rule logging gated by a flag
"""

import re
import time

from profiler_assistant.agent.tracing.decision_hooks import (
    decision_span,
    log_rule,
    log_branch_choice,
)

class FakeTracer:
    """Very small tracer stub used only for tests."""
    def __init__(self):
        self.stack = []
        self.events = []

    # Span-like APIs supported by decision_hooks (one is enough).
    def start_span(self, name: str):
        self.stack.append((name, time.perf_counter()))
        self.events.append(f"▶ {name}")

    def end_span(self):
        name, ts = self.stack.pop()
        dur_ms = int((time.perf_counter() - ts) * 1000)
        self.events.append(f"✓ {name} ({dur_ms} ms)")

    def annotate(self, text: str):
        self.events.append(text)

def _lines_with(prefix, events):
    return [e for e in events if e.startswith(prefix)]

def test_decision_trace_has_span_and_branch_choice():
    tracer = FakeTracer()
    with decision_span(tracer, title="Decision: evaluate branching rules"):
        log_branch_choice(tracer, "Investigate Video Drops", "drops > 3 within 1s")

    assert any(e.startswith("▶ Decision:") for e in tracer.events)
    assert any(e.startswith("✓ Decision") for e in tracer.events)

    chosen = [e for e in tracer.events if "chosen branch:" in e]
    assert len(chosen) == 1
    assert "↳ chosen branch: Investigate Video Drops (reason: drops > 3 within 1s)" in chosen[0]

def test_decision_trace_times_recorded():
    tracer = FakeTracer()
    with decision_span(tracer, title="Decision"):
        time.sleep(0.005)  # minimal but non-zero

    end_lines = _lines_with("✓ Decision", tracer.events)
    assert end_lines, "No decision end line"
    m = re.search(r"\((\d+) ms\)", end_lines[-1])
    assert m, f"No duration in '{end_lines[-1]}'"
    assert int(m.group(1)) >= 1  # at least 1ms

def test_rule_logging_toggle():
    tracer = FakeTracer()
    with decision_span(tracer, title="Decision"):
        log_rule(tracer, "drops_in_last_second", result=True, reason="4 > 3", enabled=False)
        log_rule(tracer, "drops_in_last_second", result=True, reason="4 > 3", enabled=True)

    rule_lines = [e for e in tracer.events if e.startswith("rule: ")]
    assert len(rule_lines) == 1
    assert "drops_in_last_second" in rule_lines[0]
    assert "True" in rule_lines[0]
    assert "(reason: 4 > 3)" in rule_lines[0]
