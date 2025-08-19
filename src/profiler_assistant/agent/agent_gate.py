"""
A lightweight gate in front of profile analysis. It always runs base checks,
optionally scores branch candidates via pluggable, config-driven detectors, and
enforces a per-analysis branch budget. It logs trace events for auditability.

Notes:
- No hardcoded branch names: detectors read rules from options.analysis_rules.
- Emits: base_checks_ran, branch_candidates, branch_selected, branch_budget,
  branch_budget_exceeded (when applicable).
- Designed to be imported and called once per analysis session to select a branch.
"""

from __future__ import annotations
import json
import logging
import math
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------- Errors ----------

class BranchBudgetExceeded(RuntimeError):
    pass


class BaseCheckError(ValueError):
    pass


# ---------- Utilities ----------

def _log(tracer: Any, event: str, **payload: Any) -> None:
    """Send a structured trace event, with safe fallbacks to stdlib logging."""
    fn = getattr(tracer, "log", None)
    if callable(fn):
        try:
            fn(event, **payload)
            return
        except Exception:
            logger.exception("tracer.log failed for event=%s", event)
    fn = getattr(tracer, "record", None)
    if callable(fn):
        try:
            fn(event, payload=dict(payload))
            return
        except Exception:
            logger.exception("tracer.record failed for event=%s", event)
    try:
        logger.info("trace %s %s", event, payload)
    except Exception:
        pass


def _getopt(options: Any, key: str, default: Any = None) -> Any:
    """Support options as dict or object with attributes."""
    if options is None:
        return default
    if isinstance(options, dict):
        return options.get(key, default)
    return getattr(options, key, default)


def _getctx(tracer: Any) -> Dict[str, Any]:
    """Get or create a mutable context dict on the tracer for counters/state."""
    ctx = getattr(tracer, "context", None)
    if isinstance(ctx, dict):
        return ctx
    ctx = {}
    try:
        setattr(tracer, "context", ctx)
    except Exception:
        _GLOBAL_TRACER_STATE.setdefault(id(tracer), {})
        return _GLOBAL_TRACER_STATE[id(tracer)]
    return ctx


_GLOBAL_TRACER_STATE: Dict[int, Dict[str, Any]] = {}


@dataclass
class BaseCheckResult:
    ok: bool
    process_count: int
    start_time: float
    end_time: float
    duration_ms: float
    profile_size_bytes: int


# ---------- Base checks (always run) ----------

def _run_base_checks(profile_path: str) -> BaseCheckResult:
    """Lightweight sanity checks: file exists, parseable, processes/time ok."""
    if not profile_path or not os.path.exists(profile_path):
        raise BaseCheckError(f"Profile file not found: {profile_path}")

    try:
        with open(profile_path, "rb") as f:
            raw = f.read()
        profile = json.loads(raw)
        size = len(raw)
    except Exception as e:
        raise BaseCheckError(f"Failed to read/parse profile: {e!r}")

    processes = profile.get("processes") or profile.get("profile", {}).get("processes")
    if not isinstance(processes, list) or len(processes) == 0:
        raise BaseCheckError("No processes found in profile JSON.")

    meta = profile.get("meta") or {}
    start = meta.get("startTime") or profile.get("startTime") or 0.0
    end = meta.get("endTime") or profile.get("endTime") or 0.0
    if (not start or not end) and isinstance(processes, list):
        for proc in processes:
            rng = proc.get("timeRange") or {}
            s = rng.get("start") or 0.0
            e = rng.get("end") or 0.0
            if e > s > 0.0:
                start, end = s, e
                break

    duration_ms = float(end - start)
    if duration_ms <= 0.0:
        raise BaseCheckError("Invalid time range in profile (duration <= 0).")

    return BaseCheckResult(
        ok=True,
        process_count=len(processes),
        start_time=float(start),
        end_time=float(end),
        duration_ms=duration_ms,
        profile_size_bytes=size,
    )


# ---------- Generic feature helpers (tiny; detectors use them) ----------

def _marker_counts(profile: Dict[str, Any], includes: Iterable[str], limit: Optional[int]) -> int:
    """Count markers whose names contain any of the substrings in `includes`."""
    inc = [s.lower() for s in includes if isinstance(s, str) and s]
    if not inc:
        return 0
    count = 0
    processes = profile.get("processes") or profile.get("profile", {}).get("processes") or []
    seen = 0
    for proc in processes:
        tracks = (proc.get("markers") or {}).get("markers") or []
        for m in tracks:
            name = ""
            if isinstance(m, dict):
                name = str(m.get("name") or m.get("data", {}).get("type") or "")
            elif isinstance(m, list) and m:
                name = str(m[0])
            lname = name.lower()
            if any(s in lname for s in inc):
                count += 1
            seen += 1
            if limit and seen >= limit:
                return count
    return count


def _p95(values: List[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = max(0, min(len(s)-1, int(math.ceil(0.95 * len(s)) - 1)))
    return float(s[idx])


# ---------- Detectors (config-driven; no branch names in code) ----------

def _detector_marker_presence(profile: Dict[str, Any], rules: List[Dict[str, Any]], sample_limit: int) -> List[Dict[str, Any]]:
    cands: List[Dict[str, Any]] = []
    for rule in rules:
        markers_any = (rule.get("markers") or {}).get("any", [])
        if not markers_any:
            continue
        min_count = int(rule.get("min_count", 1))
        cnt = _marker_counts(profile, markers_any, limit=sample_limit)
        if cnt >= min_count:
            base = float(rule.get("score", 0.5))
            scale = 1.0 + min(cnt / max(1.0, float(min_count)), 5.0) * 0.05
            reason_tpl = rule.get("reason") or "matched markers count={count}"
            cands.append({
                "branch": rule.get("name", "general"),
                "reason": reason_tpl.format(count=cnt),
                "score": base * scale,
                "features": {"count": cnt},
            })
    return cands


def _collect_candidates(profile: Dict[str, Any], options: Any) -> List[Dict[str, Any]]:
    rules = (_getopt(options, "analysis_rules") or {}).get("branches", [])
    sample_limit = int(_getopt(options, "sample_limit", 20000))
    cands: List[Dict[str, Any]] = []
    try:
        cands.extend(_detector_marker_presence(profile, rules, sample_limit))
    except Exception:
        logger.exception("marker_presence detector failed")
    return cands


def _choose_branch(cands: List[Dict[str, Any]], options: Any) -> Tuple[str, str, float]:
    """Pick highest-score candidate. If none, fall back to 'general'."""
    if not cands:
        return "general", "no candidates; falling back to general", 0.0
    cands_sorted = sorted(cands, key=lambda c: float(c.get("score", 0.0)), reverse=True)
    top = cands_sorted[0]
    return str(top.get("branch", "general")), str(top.get("reason", "")), float(top.get("score", 0.0))


# ---------- Budget ----------

def _enforce_budget(tracer: Any, limit: int) -> int:
    """Increment and enforce a per-session branch budget stored on tracer.context."""
    ctx = _getctx(tracer)
    count = int(ctx.get("branch_count", 0)) + 1
    ctx["branch_count"] = count
    _log(tracer, "branch_budget", count=count, limit=limit)
    if count > limit:
        _log(tracer, "branch_budget_exceeded", count=count, limit=limit)
        raise BranchBudgetExceeded(f"Branch budget exceeded: {count}/{limit}")
    return count


# ---------- Public API ----------

def ensure_general_analysis(profile_path: str, tracer: Any, options: Any) -> Tuple[str, str]:
    """
    Always runs base checks on the given profile, evaluates detectors to pick a
    branch, logs the chosen branch + reason, and enforces a branch budget.

    Returns:
        (branch: str, reason: str)

    Raises:
        BaseCheckError, BranchBudgetExceeded
    """
    result = _run_base_checks(profile_path)
    _log(tracer, "base_checks_ran",
         process_count=result.process_count,
         duration_ms=result.duration_ms,
         profile_size_bytes=result.profile_size_bytes)

    with open(profile_path, "rb") as f:
        profile = json.loads(f.read())

    candidates = _collect_candidates(profile, options)
    preview = [{"branch": c.get("branch"), "score": float(c.get("score", 0.0)), "reason": c.get("reason")}
               for c in sorted(candidates, key=lambda c: float(c.get("score", 0.0)), reverse=True)[:8]]
    _log(tracer, "branch_candidates", candidates=preview)

    branch, reason, score = _choose_branch(candidates, options)
    _log(tracer, "branch_selected", branch=branch, reason=reason, score=score)

    limit = int(_getopt(options, "branch_budget_limit", 3))
    _enforce_budget(tracer, limit=limit)

    return branch, reason
