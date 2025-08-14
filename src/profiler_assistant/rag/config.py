"""
Configuration utilities for RAG knowledge discovery (TOML-only).

We load a single TOML file that declares:
- knowledge_roots: list[str]  # directories to scan
- include: list[str]          # glob patterns to include (relative to each root)
- exclude: list[str]          # glob patterns to exclude (relative to each root)

Behavior:
- If the config file is missing, we raise FileNotFoundError (and print a hint).
- If required keys are missing/invalid, we raise ValueError (and print a hint).
- Only TOML is supported (use Python 3.11+ for stdlib 'tomllib'), see config/rag.toml.

"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional
import fnmatch

# --- TOML loader: use stdlib 'tomllib' on 3.11+, fall back to 'tomli' on older ---
try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # < 3.11
    try:
        import tomli as tomllib  # type: ignore[assignment]
    except ModuleNotFoundError as e:
        # We get here only if tomli isn't installed on <3.11
        raise ImportError(
            "TOML config requires Python 3.11+ (tomllib) or the 'tomli' package on older Pythons.\n"
            "Install with: pip install tomli"
        ) from e


@dataclass
class RagConfig:
    knowledge_roots: List[str]
    include: List[str]
    exclude: List[str]


def _resolve_config_path(path: Optional[str | Path]) -> Path:
    """
    Resolve a TOML config path. If not provided, defaults to 'config/rag.toml'.
    Raise FileNotFoundError if it doesn't exist.
    """
    if path:
        p = Path(path)
        if not p.exists():
            print(f"[RAG] Config error: file not found -> {p}")
            raise FileNotFoundError(f"RAG config not found: {p}")
        return p

    cfg = Path("config") / "rag.toml"
    if cfg.exists():
        return cfg

    print("[RAG] Config error: expected file at config/rag.toml")
    raise FileNotFoundError("RAG config not found. Expected file at: config/rag.toml")


def load_rag_config(path: Optional[str | Path] = None) -> RagConfig:
    """
    Load config from TOML. Raises FileNotFoundError if missing.
    Raises ValueError if required keys are missing or invalid.
    """
    cfg_path = _resolve_config_path(path)
    with open(cfg_path, "rb") as f:
        data = tomllib.load(f)

    try:
        roots = [str(x) for x in data["knowledge_roots"]]
        include = [str(x) for x in data["include"]]
        exclude = [str(x) for x in data.get("exclude", [])]
        if not roots or not include:
            print("[RAG] Config error: 'knowledge_roots' and 'include' must be non-empty lists.")
            raise ValueError("Both 'knowledge_roots' and 'include' must be non-empty lists.")
    except KeyError as e:
        print(f"[RAG] Config error: missing key {e} in {cfg_path}")
        raise ValueError(f"Missing required key in {cfg_path}: {e}") from e
    except Exception as e:
        print(f"[RAG] Config error: invalid structure in {cfg_path}: {e}")
        raise ValueError(f"Invalid RAG config structure in {cfg_path}: {e}") from e

    print(f"[RAG] Config loaded: {cfg_path}")
    print(f"[RAG]  roots={roots}")
    print(f"[RAG]  include={include}")
    print(f"[RAG]  exclude={exclude}")
    return RagConfig(knowledge_roots=roots, include=include, exclude=exclude)


def iter_candidate_files(cfg: RagConfig) -> Iterator[Path]:
    """
    Yield files under each root that match include patterns and do not match
    exclude patterns. Paths are yielded once (deduped). Prints a per-root
    summary of candidates and kept counts.

    Fix Windows/relative path issues by resolving roots to absolute paths
    and make '**/file' also exclude a root-level 'file'.
    """
    seen: set[Path] = set()

    for root_str in cfg.knowledge_roots:
        root = Path(root_str)
        root_abs = root if root.is_absolute() else (Path.cwd() / root).resolve()

        if not root_abs.exists():
            print(f"[RAG] Knowledge root missing: {root_abs}")
            continue

        # Collect potential matches from includes; ensure '**/x' also checks 'x' at root
        included: list[Path] = []
        for pattern in cfg.include:
            patterns = [pattern]
            if pattern.startswith("**/"):
                patterns.append(pattern[3:])  # also match at root level
            for pat in patterns:
                for p in root_abs.glob(pat):
                    if p.is_file():
                        included.append(p.resolve())

        kept: list[Path] = []

        def _is_excluded(rel_posix: str) -> bool:
            import fnmatch as _fn
            name = rel_posix.split("/")[-1]
            for ex in cfg.exclude:
                # direct relpath match
                if _fn.fnmatch(rel_posix, ex):
                    return True
                # '**/file' should also match 'file' at root
                if ex.startswith("**/") and _fn.fnmatch(name, ex[3:]):
                    return True
                # bare filename (no slash) applies anywhere
                if "/" not in ex and _fn.fnmatch(name, ex):
                    return True
            return False

        for p in included:
            try:
                rel_posix = p.relative_to(root_abs).as_posix()
            except ValueError:
                rel_posix = p.name  # safety fallback; shouldn't occur with root_abs normalization

            if _is_excluded(rel_posix):
                # Uncomment for verbose:
                # print(f"[RAG] Excluding {rel_posix} (matched exclude)")
                continue

            if p not in seen:
                seen.add(p)
                kept.append(p)

        print(f"[RAG] Scan root={root_abs} candidates={len(included)} kept={len(kept)}")
        for k in kept:
            yield k
