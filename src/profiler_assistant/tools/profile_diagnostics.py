"""
Router-callable wrappers around profile diagnostic utilities.

Purpose:
- Make selected domain analysis functions callable by the ReAct agent
  through the shared tool router.
- Each wrapper reads the *currently loaded profile* from the runtime
  context and returns a JSON-serializable dict.

Handles pandas DataFrame results gracefully by extracting totals and a
small preview, so the agent always gets a stable JSON shape.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from profiler_assistant.runtime.context import get_current_profile

# Import from the defining modules
from profiler_assistant.analysis_tools import (  # type: ignore
    find_video_sink_dropped_frames as _core_find_dropped,
)
from profiler_assistant.tools.base import (  # type: ignore
    extract_process as _core_extract_process,
)

log = logging.getLogger(__name__)


def _coerce_dropped_result(res: Any) -> Dict[str, Any]:
    """
    Normalize arbitrary return shapes into:
      {"dropped_frames": <int>, "preview": [ ... ]? , "details": {...}?}
    - If a DataFrame is returned, try to sum a likely column ('dropped' / 'dropped_frames'),
      else sum all numeric columns; include a small preview of the first rows.
    - If a number is returned, use it as the total.
    - If a dict is returned and contains 'dropped_frames', use it and keep details.
    - Otherwise return a conservative 0 and include details for debugging.
    """
    # pandas DataFrame path (checked without importing unconditionally)
    try:
        # Heuristic: object has .to_dict/.columns/.shape -> treat as DataFrame
        if hasattr(res, "to_dict") and hasattr(res, "columns") and hasattr(res, "shape"):
            df = res  # type: ignore
            # Pick a likely column name first
            columns = [str(c) for c in getattr(df, "columns", [])]
            pick: Optional[str] = None
            for c in columns:
                cl = c.lower()
                if cl in ("dropped", "dropped_frames", "frames_dropped", "droppedframes"):
                    pick = c
                    break
            if pick is not None:
                total = int(df[pick].fillna(0).astype("int64").sum())
            else:
                # Fallback: sum all numeric columns
                num = df.select_dtypes(include="number")
                # Newer pandas requires numeric_only keyword in sum; handle both
                try:
                    total = int(num.fillna(0).sum(numeric_only=True).sum())
                except TypeError:
                    total = int(num.fillna(0).sum().sum())
            # Include a tiny preview for transparency
            try:
                preview: List[Dict[str, Any]] = df.head(5).to_dict(orient="records")
            except Exception:
                preview = []
            out: Dict[str, Any] = {"dropped_frames": total}
            if preview:
                out["preview"] = preview
            return out
    except Exception:
        # If anything goes wrong, fall through to generic cases
        pass

    # Primitive numbers
    if isinstance(res, (int, float)) and not isinstance(res, bool):
        return {"dropped_frames": int(res)}

    # Dict with explicit key
    if isinstance(res, dict):
        if "dropped_frames" in res and isinstance(res["dropped_frames"], (int, float)):
            return {"dropped_frames": int(res["dropped_frames"]), "details": res}
        return {"dropped_frames": 0, "details": res}

    # Fallback
    return {"dropped_frames": 0}


def find_video_sink_dropped_frames(_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    No-arg tool. Reads current profile and returns a normalized summary:
      {"dropped_frames": int, "preview": [...]}  (preview only when DF returned)
    Raises ValueError if no profile is set.
    """
    profile = get_current_profile()
    if profile is None:
        raise ValueError("NO_PROFILE: profile not initialized in runtime context")
    try:
        res = _core_find_dropped(profile)
        log.info("[tool] find_video_sink_dropped_frames -> %s", type(res).__name__)
        return _coerce_dropped_result(res)
    except Exception as e:
        log.exception("find_video_sink_dropped_frames failed")
        raise ValueError(f"DIAG_TOOL_ERROR: {e}")

def _suggest_processes(profile: Dict[str, Any], limit: int = 10) -> List[Dict[str, Any]]:
    """
    Best-effort extraction of process names/pids from the parsed profile so
    we can offer suggestions when no match is found. Safe, defensive parsing.
    """
    suggestions: List[Dict[str, Any]] = []
    try:
        procs = None
        # Common layouts
        if isinstance(profile.get("processes"), list):
            procs = profile["processes"]
        elif isinstance(profile.get("profiler", {}).get("processes"), list):
            procs = profile["profiler"]["processes"]

        if isinstance(procs, list):
            seen = set()
            for p in procs:
                if not isinstance(p, dict):
                    continue
                name = p.get("name") or p.get("processName") or p.get("type") or ""
                pid = p.get("pid") or p.get("processId") or p.get("id")
                key = (str(name), int(pid) if isinstance(pid, int) else str(pid))
                if name and key not in seen:
                    seen.add(key)
                    suggestions.append({"name": str(name), "pid": pid})
                    if len(suggestions) >= limit:
                        break
    except Exception:
        pass
    return suggestions


def extract_process(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accepts flexible inputs and forwards to core extract_process:

      Text query keys (any one):
        {"query": "<name/substring>"} | {"name": "..."} | {"needle": "..."} |
        {"pattern": "..."} | {"process": "..."} | {"process_name": "..."}

      Or PID:
        {"pid": <int>}

    On 'no match' it returns a JSON result instead of raising:
      {"error":"NO_MATCH","candidates":[{"name":..., "pid":...}, ...]}
    """
    import inspect

    profile = get_current_profile()
    if profile is None:
        raise ValueError("NO_PROFILE: profile not initialized in runtime context")

    args_in = dict(payload or {})
    text_keys = ("query", "name", "needle", "pattern", "process", "process_name")
    text_val = next((str(args_in[k]) for k in text_keys if k in args_in and args_in[k] is not None), None)

    pid_val = None
    if "pid" in args_in and args_in["pid"] is not None:
        try:
            pid_val = int(args_in["pid"])
        except Exception:
            return {"error": "BAD_ARGS", "message": "'pid' must be an integer"}

    try:
        sig = inspect.signature(_core_extract_process)
        param_names = [p for p in sig.parameters.keys() if p != "profile"]

        # Prefer keyword path
        kwargs: Dict[str, Any] = {}
        if pid_val is not None and "pid" in param_names:
            kwargs["pid"] = pid_val
        if text_val is not None:
            for candidate in ("query", "name", "needle", "pattern", "text", "process", "process_name"):
                if candidate in param_names:
                    kwargs[candidate] = text_val
                    break

        # Try keyword call first
        try:
            res = _core_extract_process(profile, **kwargs)
            log.info("[tool] extract_process kwargs=%s -> %s", kwargs, type(res).__name__)
            return res if isinstance(res, dict) else {"result": res}
        except TypeError:
            pass

        # Positional fallbacks
        if pid_val is not None:
            try:
                res = _core_extract_process(profile, pid_val)
                log.info("[tool] extract_process positional(pid) -> %s", type(res).__name__)
                return res if isinstance(res, dict) else {"result": res}
            except TypeError:
                pass

        if text_val is not None:
            try:
                res = _core_extract_process(profile, text_val)
                log.info("[tool] extract_process positional(text) -> %s", type(res).__name__)
                return res if isinstance(res, dict) else {"result": res}
            except TypeError:
                pass

        # Last resort
        res = _core_extract_process(profile)
        log.info("[tool] extract_process (profile only) -> %s", type(res).__name__)
        return res if isinstance(res, dict) else {"result": res}

    except ValueError as e:
        # Core signals "No matching process found." → return candidates not an exception
        msg = str(e)
        if "No matching process" in msg:
            cands = _suggest_processes(profile, limit=10)
            return {"error": "NO_MATCH", "message": msg, "candidates": cands}
        log.exception("extract_process failed with ValueError")
        return {"error": "TOOL_ERROR", "message": msg}
    except Exception as e:
        log.exception("extract_process failed")
        return {"error": "TOOL_ERROR", "message": str(e)}
