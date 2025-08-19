"""
Policy source resolution.
Looks for a policy definition from environment, repo default file, or fallback.
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def resolve_policy():
    env = os.environ.get("PROFILER_ASSISTANT_POLICY")
    if env:
        try:
            if Path(env).exists():
                logger.info("Loading policy from file: %s", env)
                return json.loads(Path(env).read_text())
            else:
                logger.info("Loading policy from env string")
                return json.loads(env)
        except Exception as e:
            logger.error("Invalid policy from env: %s", e)
            raise

    default_path = Path(__file__).parent / "default-policy.json"
    if default_path.exists():
        logger.info("Loading default policy from %s", default_path)
        return json.loads(default_path.read_text())

    logger.warning("Falling back to minimal inline policy")
    return {"rules": []}
