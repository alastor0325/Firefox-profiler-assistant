"""
Verifies the LLM adapter path for context_summarize without calling a real LLM.
- Registers a fake `call_llm` that returns text containing provider-neutral
  citation markers ([[CITE:id]]).
- Confirms the adapter converts markers to (id), computes citation offsets
  correctly, and that the context_summarize tool uses the registered summarizer.
- No external services or SDKs are used; this test is deterministic.
"""

from profiler_assistant.rag.runtime import (
    register_summarizer_impl,
    clear_summarizer_impl,
)
from profiler_assistant.rag.summarizers.llm_adapter import make_llm_summarizer
from profiler_assistant.rag.tools.context_summarize import context_summarize
from profiler_assistant.rag.types import ContextSummarizeRequest, VectorSearchHit


def fake_call_llm(messages, max_tokens):
    # Pretend the model summarized with two citation markers.
    # The adapter should convert these into "(h1)" and "(h2)" with proper offsets.
    return "one [[CITE:h1]] two [[CITE:h2]]"


def test_llm_adapter_path():
    try:
        # Register the LLM-backed summarizer
        register_summarizer_impl(make_llm_summarizer(fake_call_llm))

        hits = [
            VectorSearchHit(id="h1", text="t1", score=1.0, meta={"source": "s"}),
            VectorSearchHit(id="h2", text="t2", score=1.0, meta={"source": "s"}),
        ]
        res = context_summarize(
            ContextSummarizeRequest(hits=hits, style="bullet", token_budget=16)
        )

        # Summary should include citations converted to (id)
        assert "(h1)" in res.summary and "(h2)" in res.summary

        # Each citation offset should slice the exact ID substring
        for c in res.citations:
            start, end = c.offset
            assert res.summary[start:end] == c.id
    finally:
        # Clean up registry for other tests
        clear_summarizer_impl()
