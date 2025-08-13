from pathlib import Path
import json
import pytest

from profiler_assistant.rag.ingest import parse_markdown, split_into_sections, ingest_file

EXAMPLE_PATH = Path("knowledge/raw/profiler/example_profiler_playbook.md")

REQUIRED_KEYS = [
    "id", "title", "source", "bugzilla_id", "bugzilla_link",
    "profile_link", "tags", "product_area", "updated_at",
]

REQUIRED_SECTIONS = {
    "summary",
    "signals & evidence",
    "analysis & reasoning",
    "conclusion",
    "references",
}

@pytest.mark.skipif(not EXAMPLE_PATH.exists(), reason="example file missing")
def test_example_front_matter_and_sections():
    meta, body = parse_markdown(EXAMPLE_PATH.read_text(encoding="utf-8"))
    assert all(k in meta for k in REQUIRED_KEYS)
    assert isinstance(meta["tags"], list)
    assert str(meta["title"]).startswith("EXAMPLE")
    assert "example" in [t.lower() for t in meta["tags"]]

    sections = split_into_sections(body)
    titles = {t.strip().lower() for t, _ in sections}
    missing = REQUIRED_SECTIONS - titles
    assert not missing, f"example missing sections: {missing}"

@pytest.mark.skipif(not EXAMPLE_PATH.exists(), reason="example file missing")
def test_example_ingestion_preserves_meta():
    chunks = ingest_file(EXAMPLE_PATH)
    assert chunks
    first = json.loads(chunks[0].to_json())
    assert first.get("title")
    assert isinstance(first.get("meta"), dict)
    for k in REQUIRED_KEYS:
        assert k in first["meta"]
    assert first["tags"] == first["meta"]["tags"]
