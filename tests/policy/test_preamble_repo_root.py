"""
Ensures _repo_root_from_here finds the repo root by locating
knowledge/analysis/general-flow.md, and falls back correctly when missing.
"""

from pathlib import Path
import os

# Import directly from the module under test
from profiler_assistant.policy.preamble import _repo_root_from_here


def test_repo_root_detects_when_general_flow_is_under_knowledge(tmp_path):
    # Simulate a repo: <repo>/knowledge/analysis/general-flow.md
    repo = tmp_path / "repo"
    (repo / "knowledge" / "analysis").mkdir(parents=True)
    (repo / "knowledge" / "analysis" / "general-flow.md").write_text("# flow\n")

    # Simulate current file location inside the project (e.g., src/profiler_assistant/)
    current = repo / "src" / "profiler_assistant"
    current.mkdir(parents=True)

    root = _repo_root_from_here(current)
    assert root == repo, f"Expected repo root to be {repo}, got {root}"

    # And verify caller logic would work:
    flow = root / "knowledge" / "analysis" / "general-flow.md"
    assert flow.exists()


def test_repo_root_falls_back_when_missing(tmp_path):
    # No knowledge/analysis/general-flow.md present
    repo = tmp_path / "repo"
    (repo / "src" / "profiler_assistant").mkdir(parents=True)
    current = repo / "src" / "profiler_assistant"

    root = _repo_root_from_here(current)
    # Our function falls back to current.parent when not found
    assert root == current.parent
