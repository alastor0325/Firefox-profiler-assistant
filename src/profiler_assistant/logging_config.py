"""
Purpose:
    Centralized logging configuration for the Firefox Profiler Assistant CLI and library code.
    Provides a small, testable function to (re)configure logging consistently across the project.
"""

from __future__ import annotations
import logging
from typing import Optional

# Expose a mapping to keep choices in one place for argparse/tests.
LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}

def configure_logging(level_str: str, *, fmt: Optional[str] = None) -> None:
    """
    Configure root logging based on a string level. Safe to call multiple times.
    We proactively clear existing handlers so tests and repeated invocations behave predictably.

    Args:
        level_str: One of "DEBUG", "INFO", "WARNING", "ERROR".
        fmt: Optional logging format override.

    Logging:
        Emits a DEBUG and INFO line after configuration to help confirm runtime state.
    """
    level_str = (level_str or "WARNING").upper()
    level = LEVEL_MAP.get(level_str, logging.WARNING)
    effective_name = logging.getLevelName(level)

    # Reset handlers so reconfig works in tests and nested invocations.
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)

    logging.basicConfig(
        level=level,
        format=fmt or "%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    logger = logging.getLogger(__name__)
    logger.debug("configure_logging called with level_str=%s -> level=%s", level_str, level)
    # Show the resolved/effective level, not the raw input, so tests & users see the truth.
    logger.warning("Logging configured to %s", effective_name)
