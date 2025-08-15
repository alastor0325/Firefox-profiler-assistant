"""
Holds per-process runtime context for tools (e.g., the currently loaded profile).
Kept deliberately tiny; the CLI sets this before each ReAct run.
"""
from __future__ import annotations
from typing import Any, Dict, Optional

_CURRENT_PROFILE: Optional[Dict[str, Any]] = None

def set_current_profile(profile: Dict[str, Any]) -> None:
    global _CURRENT_PROFILE
    _CURRENT_PROFILE = profile

def get_current_profile() -> Optional[Dict[str, Any]]:
    return _CURRENT_PROFILE
