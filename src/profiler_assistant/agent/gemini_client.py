# src/profiler_assistant/agent/gemini_client.py
import os
from dotenv import load_dotenv

# Try to import the SDK, but defer hard failure until first *real* use.
try:
    import google.generativeai as genai
except Exception:
    genai = None  # type: ignore

# Load environment variables, but DO NOT validate at import time.
load_dotenv()

# Use the stable free-tier model
MODEL_NAME = "gemini-1.5-flash"

# Real chat session is initialized lazily and stored here.
_chat_session = None


def _ensure_chat_session():
    """
    Lazily initialize the Gemini client and chat session.
    This avoids import-time failures in CI where GEMINI_API_KEY isn't set.
    """
    global _chat_session

    if _chat_session is not None:
        return

    if genai is None:
        raise RuntimeError(
            "google.generativeai is not installed. Install it to use Gemini."
        )

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        # Validate only when actually needed
        raise RuntimeError(
            "GEMINI_API_KEY not found. Set it to run against Gemini; tests can import without it."
        )

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(MODEL_NAME)
        _chat_session = model.start_chat(history=[])
        # Optional: print once on first init (kept from your original)
        print(f"✅ Using Gemini model: {MODEL_NAME}")
    except Exception as e:
        raise RuntimeError(f"❌ Failed to initialize Gemini model '{MODEL_NAME}': {e}") from e


class _LazyChatSessionProxy:
    """
    Public object exposed as `chat_session` so tests can:
      - assert it's not None at import time
      - monkeypatch its `send_message` method
    On real use, it initializes and forwards to the underlying session.
    """

    def __init__(self):
        # if tests monkeypatch `send_message`, it gets attached to this instance
        pass

    def _real(self):
        _ensure_chat_session()
        return _chat_session

    def send_message(self, *args, **kwargs):
        # Forward to the real session (initializing if needed)
        return self._real().send_message(*args, **kwargs)


# Public attribute expected by tests:
chat_session = _LazyChatSessionProxy()


def call_gemini_chat(prompt: str) -> str:
    """
    Send a prompt to Gemini and return the response text.
    Used for ReAct-style tool reasoning.
    """
    try:
        response = chat_session.send_message(prompt)
        return response.text
    except Exception as e:
        # Preserve a clear error if the key/SDK is missing or the call fails.
        raise RuntimeError(f"Gemini chat call failed: {e}") from e
