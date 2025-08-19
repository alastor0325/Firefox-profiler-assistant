"""
Provide a small utility to (1) load the repository's general analysis
policy from a Markdown file, (2) compress it into a short, LLM-friendly
"policy card" (headings + key bullets), and (3) inject that policy once per
profile into the highest-priority System message slot for the first model run.

This module is independent from RAG/ingestion and performs deterministic,
non-retrieval prompt augmentation. A simple in-memory state store is used to
remember which profile_ids have already received the preamble.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
import logging
import threading


logger = logging.getLogger(__name__)


# Default caps to keep the policy card compact and predictable
DEFAULT_MAX_HEADINGS = 8
DEFAULT_MAX_BULLETS_PER_HEADING = 4
DEFAULT_MAX_CHARS = 1600


def _repo_root_from_here(current: Path) -> Path:
    """
    Best-effort: walk upward to find the repo root that contains
    `general-flow.md`. Falls back to current.parent if not found.
    """
    for parent in [current, *current.parents]:
        if (parent / "general-flow.md").exists():
            return parent
    # Fallback: project root likely two levels up from this file
    return current.parent


@dataclass
class PolicyStateStore:
    """
    Minimal in-memory store for whether a profile has had the preamble injected.

    NOTE: This is process-local and not thread-safe for high-concurrency use
    across multiple worker processes; for now we offer coarse thread safety with
    a lock. The interface is intentionally tiny so we can swap in a persistent
    store later without touching call sites.
    """
    _applied: Dict[str, bool] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self._applied is None:
            self._applied = {}
        self._lock = threading.Lock()

    def get_applied(self, profile_id: str) -> bool:
        with self._lock:
            applied = self._applied.get(profile_id, False)
        logger.debug("policy_state_store.get_applied", extra={
            "profile_id": profile_id, "applied": applied
        })
        return applied

    def set_applied(self, profile_id: str, value: bool) -> None:
        with self._lock:
            self._applied[profile_id] = value
        logger.info("policy_state_store.set_applied", extra={
            "profile_id": profile_id, "value": value
        })


class PolicyPreambleLoader:
    """
    Load and compress `general-flow.md` into a short policy card.

    Parameters
    ----------
    md_path: Optional[str | Path]
        Path to the markdown file. If None, we attempt to locate it from the
        repository root by looking upward from this file.
    cache_enabled: bool
        If True, cache raw and compressed content in-process for reuse.
    """

    def __init__(self, md_path: Optional[str | Path] = None, *, cache_enabled: bool = True) -> None:
        self._cache_enabled = cache_enabled
        here = Path(__file__).resolve()
        if md_path is None:
            root = _repo_root_from_here(here)
            self._md_path = root / "general-flow.md"
        else:
            self._md_path = Path(md_path)
        self._raw_cache: Optional[str] = None
        self._card_cache: Optional[str] = None
        logger.info("preamble_loader.init", extra={"md_path": str(self._md_path), "cache": cache_enabled})

    # -------------------- public API --------------------
    def load_raw_markdown(self) -> str:
        """
        Read markdown from disk with optional caching.

        Raises FileNotFoundError if missing.
        """
        if self._cache_enabled and self._raw_cache is not None:
            logger.debug("preamble_loader.load_raw_markdown.cache_hit", extra={"bytes": len(self._raw_cache)})
            return self._raw_cache
        if not self._md_path.exists():
            logger.warning("preamble_loader.load_raw_markdown.file_missing", extra={"md_path": str(self._md_path)})
            raise FileNotFoundError(str(self._md_path))
        text = self._md_path.read_text(encoding="utf-8")
        logger.info("preamble_loader.load_raw_markdown", extra={"bytes": len(text)})
        if self._cache_enabled:
            self._raw_cache = text
        return text

    def compress_to_policy_card(
        self,
        md: str,
        *,
        max_headings: int = DEFAULT_MAX_HEADINGS,
        max_bullets_per_heading: int = DEFAULT_MAX_BULLETS_PER_HEADING,
        max_chars: int = DEFAULT_MAX_CHARS,
    ) -> str:
        """
        Extract a concise policy card: headings + first-level bullets only.

        We keep #, ##, ### headings; capture bullets directly under each heading;
        ignore nested bullets and code blocks; enforce caps and a total char
        budget with graceful truncation.
        """
        logger.info("preamble_loader.compress.start", extra={
            "len": len(md),
            "max_headings": max_headings,
            "max_bullets_per_heading": max_bullets_per_heading,
            "max_chars": max_chars,
        })

        lines = md.splitlines()
        in_code_block = False
        sections: List[tuple[str, List[str]]] = []  # (heading, bullets)
        current_heading: Optional[str] = None
        current_bullets: List[str] = []

        def flush_section():
            nonlocal current_heading, current_bullets
            if current_heading is not None:
                sections.append((current_heading.strip(), current_bullets[:]))
            current_heading = None
            current_bullets = []

        for raw in lines:
            line = raw.rstrip()

            # Code block fence toggling
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue

            # Headings: capture #, ##, ### only
            if line.startswith("# ") or line.startswith("## ") or line.startswith("### "):
                flush_section()
                # Strip leading # and whitespace
                heading = line.lstrip("#").strip()
                current_heading = heading
                continue

            # Bullets: only first-level '-' or '*'
            if (line.startswith("- ") or line.startswith("* ")) and current_heading is not None:
                bullet = line[2:].strip()
                # Basic cleanup for markdown links: [text](url) -> text
                # and for inline code `code` -> code
                bullet = _strip_simple_md_markup(bullet)
                if bullet:
                    current_bullets.append(bullet)
                continue

            # Stop collecting bullets when we hit a blank line between sections
            if line == "" and current_heading is not None:
                # keep scanning; bullets end implicitly when next heading appears
                continue

        flush_section()

        # Enforce caps
        sections = sections[:max_headings]
        capped_sections: List[tuple[str, List[str]]] = []
        for heading, bullets in sections:
            capped_sections.append((heading, bullets[:max_bullets_per_heading]))

        # Render
        header = "[Policy Card: General Flow]"
        out_lines: List[str] = [header]
        for heading, bullets in capped_sections:
            out_lines.append(heading)
            for b in bullets:
                out_lines.append(f"- {b}")

        out = "\n".join(out_lines)
        if len(out) > max_chars:
            out = out[: max(0, max_chars - 1)].rstrip() + "…"
        logger.info("preamble_loader.compress.done", extra={
            "sections": len(capped_sections),
            "chars": len(out),
        })
        return out

    def get_policy_card(self) -> str:
        if self._cache_enabled and self._card_cache is not None:
            logger.debug("preamble_loader.get_policy_card.cache_hit", extra={"chars": len(self._card_cache)})
            return self._card_cache
        md = self.load_raw_markdown()
        card = self.compress_to_policy_card(md)
        if self._cache_enabled:
            self._card_cache = card
        logger.debug("preamble_loader.get_policy_card", extra={"chars": len(card)})
        return card


class PolicyPreambleInjector:
    """Inject the policy card as the first System message once per profile."""

    def __init__(self, loader: PolicyPreambleLoader, state_store: Optional[PolicyStateStore] = None) -> None:
        self._loader = loader
        self._state = state_store or PolicyStateStore()

    def inject(self, profile_id: str, messages: List[dict]) -> List[dict]:
        """
        Prepend a System message with the policy card if not yet applied.

        Parameters
        ----------
        profile_id: str
            Unique ID for the profile (share ID or deterministic local hash).
        messages: list[dict]
            Existing chat messages; we always place the policy before all of them
            to ensure highest priority.
        """
        already = self._state.get_applied(profile_id)
        logger.debug("preamble_injector.check", extra={"profile_id": profile_id, "already": already})
        if already:
            return messages
        try:
            card = self._loader.get_policy_card()
        except FileNotFoundError:
            logger.warning("preamble_injector.skip_missing_policy")
            return messages

        policy_msg = {"role": "system", "content": card}
        new_messages = [policy_msg] + list(messages)
        self._state.set_applied(profile_id, True)
        logger.info("preamble_injector.injected", extra={
            "profile_id": profile_id,
            "chars": len(card),
            "messages_before": len(messages),
            "messages_after": len(new_messages),
        })
        return new_messages


# -------------------- helpers --------------------

def _strip_simple_md_markup(text: str) -> str:
    """
    Remove a few common markdown constructs to keep bullets clean.

    - Inline code: `code` → code
    - Links: [label](url) → label
    - Bold/italic: **x**/*x* → x
    The goal is readable plain text; not a full markdown parser.
    """
    import re

    # inline code
    text = re.sub(r"`([^`]*)`", r"\1", text)
    # links [label](url)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    # bold/italic
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    return text.strip()