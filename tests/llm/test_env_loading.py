"""
Ensures GEMINI_API_KEY is picked up from env or .env.

If neither an environment variable nor a .env file is present, this test
returns early (no-op) so CI without secrets won't fail.
"""

from profiler_assistant.llm.call_model import has_policy_llm_config, read_dotenv_vars

def test_policy_key_detected_from_dotenv_only():
    vars_ = read_dotenv_vars()
    # No .env or no key → do nothing (pass), avoids CI dependency on secrets.
    if "GEMINI_API_KEY" not in vars_:
        return
    # If key exists in .env, our config detector must be True.
    assert has_policy_llm_config() is True
