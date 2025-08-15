"""
Behavior tests for context_summarize via the fallback summarizer:
- budget truncation never exceeded
- citation offsets slice exact IDs
- styles produce non-empty output when hits exist
"""
from profiler_assistant.rag.types import (
    VectorSearchHit,
    ContextSummarizeRequest,
)
from profiler_assistant.rag.tools.context_summarize import context_summarize
from profiler_assistant.rag.summarizers.base import char_budget


def _hit(i: str, text: str, score: float = 1.0):
    return VectorSearchHit(id=i, text=text, score=score, meta={"source": "t"})


def test_truncation_and_offsets_bullet():
    hits = [
        _hit("h1", "First fact about media playback and pipelines."),
        _hit("h2", "Second fact related to rendering pipeline and frames."),
        _hit("h3", "Third detail for completeness."),
    ]
    req = ContextSummarizeRequest(hits=hits, style="bullet", token_budget=20)
    res = context_summarize(req)
    assert isinstance(res.summary, str)
    assert len(res.summary) <= char_budget(20)
    assert len(res.citations) >= 1
    for c in res.citations:
        assert res.summary[c.offset[0] : c.offset[1]] == c.id


def test_styles_have_output_and_citations():
    hits = [
        _hit("a", "Alpha sentence one. Alpha sentence two."),
        _hit("b", "Beta sentence one. Beta sentence two."),
    ]
    for style in ("bullet", "abstract", "qa"):
        res = context_summarize(ContextSummarizeRequest(hits=hits, style=style, token_budget=40))
        assert isinstance(res.summary, str)
        assert len(res.summary) > 0
        assert len(res.citations) >= 1


def test_no_hits_returns_empty():
    res = context_summarize(ContextSummarizeRequest(hits=[], style="bullet", token_budget=50))
    assert res.summary == ""
    assert res.citations == []
