"""
Tests for the run_react_agent wrapper:
- happy path with a mocked policy LLM that emits tool→final
- guard failure path when sources are requested but none provided
"""
import json
from profiler_assistant.agent import react_agent

# Monkeypatch helpers
class _MockLLMHappy:
    def __init__(self):
        self.step = 0
    def __call__(self, messages):
        self.step += 1
        if self.step == 1:
            return json.dumps({"action":"tool","name":"vector_search","args":{"query":"media pipeline","k":1}})
        return json.dumps({"action":"final","answer":"• ok (doc:media-pipeline)","citations":["doc:media-pipeline"]})

class _MockLLMNoCites:
    def __call__(self, messages):
        return json.dumps({"action":"final","answer":"no cites","citations":[]})

def test_react_agent_happy_path(monkeypatch):
    # Patch the policy LLM
    monkeypatch.setattr("profiler_assistant.llm.call_model.call_model", _MockLLMHappy())
    # Avoid touching real filesystem bootstrap
    monkeypatch.setattr("profiler_assistant.agent.react_agent._ensure_bootstrap", lambda: None)
    out = react_agent.run_react_agent({}, "please include sources", [])
    assert "final" in out and "Sources:" in out["final"]

def test_react_agent_guard_failure(monkeypatch):
    monkeypatch.setattr("profiler_assistant.llm.call_model.call_model", _MockLLMNoCites())
    monkeypatch.setattr("profiler_assistant.agent.react_agent._ensure_bootstrap", lambda: None)
    out = react_agent.run_react_agent({}, "give me sources", [])
    assert "error" in out and "GUARD_CITATION_REQUIRED" in out["error"]
