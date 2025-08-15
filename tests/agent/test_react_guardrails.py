"""
Validates guardrails:
- If user asks for sources but final has none -> GUARD_CITATION_REQUIRED
- If final citations reference unknown ids -> GUARD_CITATION_UNKNOWN_ID
"""
import json
import pytest

from profiler_assistant.agent.react import run_react


class MockLLMNoCites:
    def __call__(self, messages):
        # Immediately return final without citations
        return json.dumps({
            "action": "final",
            "answer": "Here is an answer without cites.",
            "citations": []
        })


class MockLLMBadIds:
    def __init__(self):
        self.step = 0

    def __call__(self, messages):
        self.step += 1
        if self.step == 1:
            return json.dumps({
                "action": "tool",
                "name": "vector_search",
                "args": {"query": "media pipeline", "k": 1}
            })
        # Final cites an unknown id
        return json.dumps({
            "action": "final",
            "answer": "• Something (unknown:id)",
            "citations": ["unknown:id"]
        })


def test_guard_requires_citation_when_asked():
    with pytest.raises(ValueError) as e:
        run_react("Please give me sources for the media pipeline.", MockLLMNoCites())
    assert "GUARD_CITATION_REQUIRED" in str(e.value)


def test_guard_rejects_unknown_citation_ids():
    with pytest.raises(ValueError) as e:
        run_react("Summarize with sources.", MockLLMBadIds())
    assert "GUARD_CITATION_UNKNOWN_ID" in str(e.value)
