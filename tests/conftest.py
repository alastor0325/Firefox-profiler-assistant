"""
Test helper file.

Pytest special file for global test configuration and fixtures.
Registers deterministic in-memory search and docs implementations so tools
return real, predictable results during tests.
"""
from profiler_assistant.rag.runtime import register_search_impl, register_docs_impl
from tests.helpers.vector_index_fixture import make_fixture_search
from tests.helpers.doc_store_fixture import make_fixture_docs

# Search: default tiny corpus used for most tests
_DEFAULT_CORPUS = [
    {
        "id": "doc:media-pipeline",
        "text": "media playback pipeline overview and troubleshooting",
        "meta": {"source": "docs"},
    },
    {
        "id": "doc:render-thread",
        "text": "rendering pipeline stages and frame pacing",
        "meta": {"source": "docs"},
    },
    {"id": "doc:media", "text": "media audio video decoding demuxer", "meta": {"source": "notes"}},
    {"id": "doc:unrelated", "text": "profiling tips and CLI usage", "meta": {"source": "misc"}},
]

# Docs: small parent/chunk corpus
_DOCS_CORPUS = [
    {"id": "doc:media", "text": "MEDIA FULL DOC", "meta": {"source": "docs", "title": "Media"}},
    {
        "id": "doc:media#0-10",
        "text": "MEDIA FULL",
        "meta": {"source": "docs", "title": "Media"},
        "parent_id": "doc:media",
    },
    {
        "id": "doc:media#10-20",
        "text": " DOC TEXT",
        "meta": {"source": "docs", "title": "Media"},
        "parent_id": "doc:media",
    },
    {
        "id": "doc:render-thread",
        "text": "RENDER FULL DOC",
        "meta": {"source": "docs", "title": "Render Thread"},
    },
    {
        "id": "doc:render-thread#0-10",
        "text": "RENDER FULL",
        "meta": {"source": "docs", "title": "Render Thread"},
        "parent_id": "doc:render-thread",
    },
]

# Register implementations for the whole test session
register_search_impl(make_fixture_search(_DEFAULT_CORPUS))
register_docs_impl(make_fixture_docs(_DOCS_CORPUS))
