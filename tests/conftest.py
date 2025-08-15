"""
Test helper file.

Pytest special file for global test configuration and fixtures.
Here we register a deterministic in-memory search implementation so
vector_search returns real, predictable hits during tests.
"""
from profiler_assistant.rag.runtime import register_search_impl
from tests.helpers.vector_index_fixture import make_fixture_search

# Default tiny corpus used for most tests
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
    {
        "id": "doc:media",
        "text": "media audio video decoding demuxer",
        "meta": {"source": "notes"},
    },
    {
        "id": "doc:unrelated",
        "text": "profiling tips and CLI usage",
        "meta": {"source": "misc"},
    },
]

# Register search impl for the whole test session
register_search_impl(make_fixture_search(_DEFAULT_CORPUS))
