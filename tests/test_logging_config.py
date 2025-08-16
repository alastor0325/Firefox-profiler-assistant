
"""
Validate the logging configuration helper.
"""

import logging
import importlib

import profiler_assistant.logging_config as logging_config


def _reset_root_logging():
    """Utility for tests to reset logging to a known state."""
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(logging.NOTSET)


def test_configure_logging_sets_warning_by_default(capsys):
    _reset_root_logging()
    logging_config.configure_logging("WARNING")
    assert logging.getLogger().getEffectiveLevel() == logging.WARNING
    out, err = capsys.readouterr()
    assert "Logging configured to WARNING" in (out + err)


def test_configure_logging_sets_debug(capsys):
    _reset_root_logging()
    logging_config.configure_logging("DEBUG")
    assert logging.getLogger().getEffectiveLevel() == logging.DEBUG
    out, err = capsys.readouterr()
    assert "Logging configured to DEBUG" in (out + err)


def test_configure_logging_invalid_level_defaults_to_warning(capsys):
    _reset_root_logging()
    logging_config.configure_logging("NOTALEVEL")
    assert logging.getLogger().getEffectiveLevel() == logging.WARNING
    out, err = capsys.readouterr()
    assert "Logging configured to WARNING" in (out + err)
