# tests/test_agent/test_gemini_client.py
# CI-friendly tests: never require a real GEMINI_API_KEY or network.

import types
import pytest

from profiler_assistant.agent import gemini_client


class _DummySessionOK:
    def __init__(self, text="Hello"):
        self._text = text

    def send_message(self, prompt):
        # Mimic a google.generativeai response object with a `.text` attribute
        return types.SimpleNamespace(text=self._text)


class _DummySessionFail:
    def send_message(self, prompt):
        raise RuntimeError("boom")


def test_call_gemini_chat_basic(monkeypatch):
    # If gemini_client.chat_session doesn't exist, allow creation (raising=False)
    monkeypatch.setattr(
        gemini_client, "chat_session", _DummySessionOK("Hello"), raising=False
    )
    out = gemini_client.call_gemini_chat("ping")
    assert out == "Hello"


def test_call_gemini_chat_failure(monkeypatch):
    monkeypatch.setattr(
        gemini_client, "chat_session", _DummySessionFail(), raising=False
    )
    with pytest.raises(RuntimeError) as exc:
        gemini_client.call_gemini_chat("ping")
    # Ensure our wrapper surfaces a clear error
    assert "Gemini chat call failed" in str(exc.value)
