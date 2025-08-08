from profiler_assistant.agent import gemini_client

def test_model_loaded():
    assert gemini_client.chat_session is not None

def test_call_gemini_chat_basic(monkeypatch):
    # Avoid hitting real API
    monkeypatch.setattr(gemini_client.chat_session, "send_message", lambda prompt: type("Obj", (object,), {"text": "Hello"})())
    response = gemini_client.call_gemini_chat("Hi")
    assert response == "Hello"
