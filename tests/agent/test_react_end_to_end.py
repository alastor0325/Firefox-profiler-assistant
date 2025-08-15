"""
End-to-end ReAct test with a mocked LLM:
- vector_search -> context_summarize -> final
- Verifies tool call sequence and that final answer includes citations.
"""
import json

from profiler_assistant.agent.react import run_react


class MockLLM:
    def __init__(self):
        self.step = 0

    def __call__(self, messages):
        # Simple finite state machine that returns JSON actions
        self.step += 1
        if self.step == 1:
            return json.dumps({
                "action": "tool",
                "name": "vector_search",
                "args": {"query": "media pipeline", "k": 2}
            })
        if self.step == 2:
            # Ask to summarize the last hits with a small budget
            return json.dumps({
                "action": "tool",
                "name": "context_summarize",
                "args": {"hits": "$last_hits", "style": "bullet", "token_budget": 24}
            })
        # Final: include at least one known id to satisfy guard
        return json.dumps({
            "action": "final",
            "answer": "• Summary (doc:media-pipeline)",
            "citations": ["doc:media-pipeline"]
        })


def test_react_e2e_with_citations():
    mock = MockLLM()
    out = run_react("Summarize media pipeline and include sources.", mock)

    assert isinstance(out["answer"], str) and len(out["answer"]) > 0
    assert "citations" in out and isinstance(out["citations"], list) and len(out["citations"]) >= 1

    # Steps recorded with observations
    steps = out["steps"]
    assert steps[0]["action"]["name"] == "vector_search"
    assert "observation" in steps[0]
    assert steps[1]["action"]["name"] == "context_summarize"
    assert "observation" in steps[1]
