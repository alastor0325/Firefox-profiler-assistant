"""
Purpose:
    Lightweight utilities to emit *decision* tracing with minimal churn.
    Wraps an arbitrary tracer-like object (if present) to:
      - Open/close a nested "Decision" span with duration
      - Log rule evaluations (optional, to avoid noisy traces)
      - Log the chosen branch and a human-readable reason

Design:
    - Zero hard dependency on a concrete tracer API.
    - If a provided tracer lacks expected methods, we degrade gracefully
      (no-ops) and log debug messages to aid integration.
    - Intended to be called from existing branching/decision code.

Usage (example):
    from profiler_assistant.agent.tracing.decision_hooks import decision_span, log_branch_choice

    with decision_span(tracer, title="Decision: evaluate branching rules"):
        ...
        log_branch_choice(tracer, "Investigate Video Drops", "drops > 3 within 1s")
        ...

Output target (renderer-agnostic, typical formatting):
    ▶ Decision: evaluate branching rules
    ↳ chosen branch: Investigate Video Drops (reason: drops > 3 within 1s)
    ✓ Decision (2 ms)
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Optional

logger = logging.getLogger(__name__)

def _tracer_has(obj: Any, *attrs: str) -> bool:
    return all(hasattr(obj, a) for a in attrs)

def _safe_call(obj: Any, name: str, *args, **kwargs) -> None:
    """Call obj.name(*args, **kwargs) if it exists; otherwise, debug-log."""
    if hasattr(obj, name):
        try:
            getattr(obj, name)(*args, **kwargs)
        except Exception:
            logger.exception("Tracer method %s raised.", name)
    else:
        logger.debug("Tracer has no method '%s'; skipping.", name)

@contextmanager
def decision_span(tracer: Optional[Any], title: str = "Decision"):
    """
    Open a child span named `title`, yield, and close it with timing.
    Works with tracers exposing one of these patterns:
      - start_span(name)/end_span()
      - push(name)/pop()
      - begin(name)/end()
    If unsupported, becomes a no-op, but still measures wall time.
    """
    start = time.perf_counter()
    logger.debug("Opening decision span: %s", title)

    opened = False
    if tracer:
        if _tracer_has(tracer, "start_span", "end_span"):
            _safe_call(tracer, "start_span", title)
            opened = True
        elif _tracer_has(tracer, "push", "pop"):
            _safe_call(tracer, "push", title)
            opened = True
        elif _tracer_has(tracer, "begin", "end"):
            _safe_call(tracer, "begin", title)
            opened = True
        else:
            logger.debug("Tracer doesn't expose known span API; proceeding no-op.")

    try:
        yield
    finally:
        dur_ms = int((time.perf_counter() - start) * 1000)
        logger.debug("Closing decision span: %s (%d ms)", title, dur_ms)
        if tracer:
            if hasattr(tracer, "annotate"):
                _safe_call(tracer, "annotate", f"{title} finished ({dur_ms} ms)")
            if opened:
                if _tracer_has(tracer, "end_span"):
                    _safe_call(tracer, "end_span")
                elif _tracer_has(tracer, "pop"):
                    _safe_call(tracer, "pop")
                elif _tracer_has(tracer, "end"):
                    _safe_call(tracer, "end")

def log_rule(tracer: Optional[Any], rule_name: str, result: Optional[bool] = None,
             reason: Optional[str] = None, *, enabled: bool = False) -> None:
    """
    Optionally log a rule evaluation. Controlled by `enabled` to prevent noise.
    """
    if not enabled:
        logger.debug("Rule logging disabled; rule '%s' skipped.", rule_name)
        return

    msg = f"rule: {rule_name}"
    if result is not None:
        msg += f" => {result}"
    if reason:
        msg += f" (reason: {reason})"
    logger.debug("Logging rule: %s", msg)
    if tracer and hasattr(tracer, "annotate"):
        _safe_call(tracer, "annotate", msg)

def log_branch_choice(tracer: Optional[Any], branch_name: str, reason: str) -> None:
    """
    Emit the single-line chosen-branch annotation expected by the spec.
    """
    line = f"chosen branch: {branch_name} (reason: {reason})"
    logger.info("Decision made -> %s", line)
    if tracer and hasattr(tracer, "annotate"):
        _safe_call(tracer, "annotate", f"↳ {line}")
