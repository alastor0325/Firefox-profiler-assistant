"""
Provider-neutral model wrapper for the ReAct agent.

This module reads provider credentials **only** from the nearest `.env` file
(upwards from CWD). We do not read or set process environment variables to
avoid environment pollution.

Exports:
- call_model(messages) -> str
    Policy LLM call (expects one JSON action per step as a raw string).
- find_dotenv_path() -> Optional[Path]
- read_dotenv_vars() -> dict[str, str]
- has_policy_llm_config() -> bool

Built-in provider path:
- Gemini via google-generativeai, when `GEMINI_API_KEY` is present in `.env`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional


# -----------------------------
# .env discovery and parsing
# -----------------------------
def find_dotenv_path() -> Optional[Path]:
    """
    Return the nearest .env path from CWD up to repo root (best-effort),
    or None if not found.
    """
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        p = parent / ".env"
        if p.exists():
            return p
    return None


def _parse_env_line(line: str) -> Optional[tuple[str, str]]:
    s = line.strip()
    if not s or s.startswith("#") or "=" not in s:
        return None
    key, val = s.split("=", 1)
    key = key.strip()
    val = val.strip().strip('"').strip("'")
    if not key:
        return None
    return key, val


def read_dotenv_vars() -> Dict[str, str]:
    """
    Parse the nearest .env into a dict WITHOUT touching os.environ.
    Returns {} if no .env is present or on parse errors.
    """
    path = find_dotenv_path()
    if not path:
        return {}
    out: Dict[str, str] = {}
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                kv = _parse_env_line(line)
                if kv:
                    k, v = kv
                    out[k] = v
    except Exception:
        # best-effort; empty dict on failure
        return {}
    return out


def has_policy_llm_config() -> bool:
    """
    Returns True if a supported provider API key is configured in `.env`.
    """
    vars_ = read_dotenv_vars()
    # TODO : add other providers as needed
    return bool(
        vars_.get("GEMINI_API_KEY")
    )


# -----------------------------
# Provider calls
# -----------------------------
def _call_gemini(messages: List[Dict[str, str]], api_key: str, model_name: str) -> str:
    """
    Call Gemini using the provided api_key and model_name.
    Returns raw text; expected to be a single JSON object string.
    """
    try:
        import google.generativeai as genai  # type: ignore
    except Exception as e:
        raise RuntimeError("Gemini SDK not installed (google-generativeai)") from e

    # Configure with the key passed from `.env` (no env vars)
    genai.configure(api_key=api_key)

    # Flatten messages into one prompt (role tags included)
    parts = [f"{m.get('role','user')}: {m.get('content','')}" for m in messages]
    prompt_text = "\n".join(parts)

    try:
        model = genai.GenerativeModel(model_name or "gemini-1.5-flash")
        resp = model.generate_content(
            prompt_text,
            generation_config={"response_mime_type": "application/json"},
        )
        text = getattr(resp, "text", None)
        if not text:
            # Fallback path used by some SDK versions
            try:
                cand = resp.candidates[0]
                text = cand.content.parts[0].text  # type: ignore[attr-defined]
            except Exception as e:
                raise RuntimeError("Gemini returned empty response") from e
        return str(text)
    except Exception as e:
        raise RuntimeError(f"Gemini call failed: {e}") from e


def call_model(messages: List[Dict[str, str]]) -> str:
    """
    Provider-neutral policy LLM entry point used by the ReAct agent.

    Strategy:
    - Read `.env` only (no os.environ)
    - If GEMINI_API_KEY exists, call Gemini
    - Otherwise raise clear "not configured" error
    """
    vars_ = read_dotenv_vars()

    gem_key = vars_.get("GEMINI_API_KEY")
    if gem_key:
        model_name = vars_.get("RAG_POLICY_MODEL", "gemini-1.5-flash")
        return _call_gemini(messages, gem_key, model_name)

    raise RuntimeError(
        "LLM not configured: set GEMINI_API_KEY in your .env (no OS env is read)."
    )
