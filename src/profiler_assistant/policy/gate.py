"""
Policy gating logic for profiler-assistant.
This module decides whether to inject, replace, skip, or bypass policy
before running analysis or agent flows.
"""

import logging
from profiler_assistant.policy import sources

logger = logging.getLogger(__name__)


def has_policy(profile):
    present = "policy" in profile
    logger.debug("has_policy=%s", present)
    return present


def decide_policy_action(profile, flag):
    if flag == "none":
        return {"action": "bypass", "reason": "flag=no-policy"}
    if not has_policy(profile):
        if flag in ("once", "always"):
            return {"action": "inject", "reason": "absent"}
    else:
        if flag == "always":
            return {"action": "replace", "reason": "flag=always"}
        return {"action": "skip", "reason": "already_present"}
    return {"action": "skip", "reason": "default"}


def inject_policy(profile, policy):
    logger.info("Injecting policy")
    new_profile = dict(profile)
    new_profile["policy"] = policy
    return new_profile


def load_default_policy():
    return sources.resolve_policy()
