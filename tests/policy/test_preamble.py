import os
from pathlib import Path

import pytest

from profiler_assistant.policy.preamble import (
    PolicyPreambleLoader,
    PolicyPreambleInjector,
    PolicyStateStore,
)


SAMPLE_MD = """# General Flow

- Top bullet A
- Top bullet B with a [link](https://example.com)

## Section One
- Bullet 1
- Bullet 2 with `inline code`
- Bullet 3

### Subsection
- Sub bullet 1
- Sub bullet 2

#### Too deep should be ignored
- Deep bullet

```
# In code block (ignored)
- pretend bullet
```

## Section Two
- Another bullet
- Second bullet

"""


def write_temp_md(tmp_path: Path, name: str = "general-flow.md") -> Path:
    p = tmp_path / name
    p.write_text(SAMPLE_MD, encoding="utf-8")
    return p


def test_loader_compress_basic(tmp_path: Path):
    md_path = write_temp_md(tmp_path)
    loader = PolicyPreambleLoader(md_path=md_path)
    card = loader.get_policy_card()

    # Header present
    assert card.startswith("[Policy Card: General Flow]")

    # Headings retained up to ###, but not deeper
    assert "General Flow" in card
    assert "Section One" in card
    assert "Subsection" in card
    assert "Too deep" not in card  # #### heading is ignored

    # Bullets cleaned (links/code stripped)
    assert "Top bullet A" in card
    assert "Top bullet B with a link" in card or "Top bullet B with a" in card
    assert "Bullet 2 with inline code" in card


def test_loader_caps(tmp_path: Path):
    md_path = write_temp_md(tmp_path)
    loader = PolicyPreambleLoader(md_path=md_path)

    raw = loader.load_raw_markdown()
    short = loader.compress_to_policy_card(raw, max_headings=1, max_bullets_per_heading=1, max_chars=80)

    # Only top-level heading and one bullet should remain, and under char limit
    assert short.count("\n") <= 3
    assert len(short) <= 80


def test_state_store_roundtrip():
    store = PolicyStateStore()
    pid = "profile-123"
    assert store.get_applied(pid) is False
    store.set_applied(pid, True)
    assert store.get_applied(pid) is True


def test_inject_once_only(tmp_path: Path):
    md_path = write_temp_md(tmp_path)
    loader = PolicyPreambleLoader(md_path=md_path)
    store = PolicyStateStore()
    injector = PolicyPreambleInjector(loader, state_store=store)

    pid = "abc"
    base_messages = [{"role": "system", "content": "baseline system"}, {"role": "user", "content": "hi"}]

    # First injection should prepend a system policy message
    m1 = injector.inject(pid, base_messages)
    assert m1[0]["role"] == "system"
    assert "Policy Card:" in m1[0]["content"]
    assert len(m1) == len(base_messages) + 1

    # Second injection for same profile should be a no-op
    m2 = injector.inject(pid, base_messages)
    assert m2 == base_messages


def test_missing_file_graceful(tmp_path: Path):
    # Point to non-existent file
    missing = tmp_path / "nope.md"
    loader = PolicyPreambleLoader(md_path=missing)
    injector = PolicyPreambleInjector(loader)

    pid = "pid"
    msgs = [{"role": "user", "content": "hello"}]
    out = injector.inject(pid, msgs)
    # Should not inject anything and not crash
    assert out == msgs
