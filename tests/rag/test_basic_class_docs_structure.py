import re
from pathlib import Path

ROOT = Path("knowledge/basic/classes")
EXAMPLE = ROOT / "example_class.md"

def _read(path: Path) -> str:
    assert path.exists(), f"Missing {path}"
    return path.read_text(encoding="utf-8")

def _extract_section(text: str, heading: str) -> str:
    """
    Extract content of a '## ' section starting at `heading` until the next '## ' or end.
    """
    pattern = rf"(?s){re.escape(heading)}\n(.*?)(?:\n## |\Z)"
    m = re.search(pattern, text)
    return m.group(1) if m else ""

def test_all_class_docs_follow_example_structure():
    # Load the example template and derive required top-level sections
    example_text = _read(EXAMPLE)
    required_sections = re.findall(r"^##\s+.+", example_text, flags=re.M)
    assert required_sections, "No top-level sections found in example_class.md"

    # The example must define both Profiler subsections
    assert "## Profiler Markers" in example_text, "Template missing '## Profiler Markers'"
    assert "### Normal" in example_text, "Template missing '### Normal' under Profiler Markers"
    assert "### Troubleshooting" in example_text, "Template missing '### Troubleshooting' under Profiler Markers"

    # Check every *.md file in the folder (except the template itself)
    for path in sorted(ROOT.glob("*.md")):
        if path.name == EXAMPLE.name:
            continue

        # Debug log for which file is being checked
        print(f"[DEBUG] Checking structure of {path.relative_to(ROOT)}")

        text = _read(path)

        # 1) YAML front matter fence
        assert text.lstrip().startswith("---"), f"{path}: Missing YAML front-matter fence '---'"

        # 2) Minimal required YAML keys
        for key in ("id:", "title:", "kind:"):
            assert re.search(rf"^{key}\s*\S", text, flags=re.M), f"{path}: Missing YAML key: {key}"

        # 3) Validate each links entry contains 'type' and 'url'
        links_block = re.search(r"(?s)^links:\n(.*?)(?:\n[A-Za-z_-]+:|^---|\Z)", text, flags=re.M)
        if links_block:
            entries = links_block.group(1)
            assert "type:" in entries and "url:" in entries, f"{path}: Each link should include 'type' and 'url'"

        # 4) Required top-level sections
        for heading in required_sections:
            assert heading in text, f"{path}: Missing section: {heading}"

        # 5) Profiler Markers must have both subsections
        assert "### Normal" in text, f"{path}: Missing '### Normal' under Profiler Markers"
        assert "### Troubleshooting" in text, f"{path}: Missing '### Troubleshooting' under Profiler Markers"

        # 6) Threads section must include at least one backticked name
        threads_body = _extract_section(text, "## Threads")
        assert threads_body, f"{path}: Couldn't extract Threads section"
        assert re.search(r"^- .*`[^`]+`", threads_body, flags=re.M), \
            f"{path}: Threads section should include at least one backticked thread name"

        # 7) No tooling artifacts
        assert "oaicite" not in text, f"{path}: Contains tooling artifact 'oaicite'"
        assert "contentReference" not in text, f"{path}: Contains tooling artifact 'contentReference'"
