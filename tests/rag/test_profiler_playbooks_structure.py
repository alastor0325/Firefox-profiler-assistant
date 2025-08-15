import re
from pathlib import Path

ROOT = Path("knowledge/raw/profiler")
TEMPLATE = ROOT / "example_profiler_playbook.md"

REQUIRED_YAML_KEYS = ("id:", "title:", "source:", "product_area:", "tags:", "updated_at:")

def _read(path: Path) -> str:
    assert path.exists(), f"Missing {path}"
    return path.read_text(encoding="utf-8")

def test_profiler_playbooks_match_template():
    # Load the template
    template_text = _read(TEMPLATE)

    # Validate template has required YAML keys
    assert template_text.lstrip().startswith("---"), "Template missing YAML front-matter"
    for key in REQUIRED_YAML_KEYS:
        assert re.search(rf"^{key}\s*\S", template_text, flags=re.M), f"Template missing YAML key: {key}"

    # Validate template headings
    expected_headings = [
        "# Summary",
        "## Signals & Evidence",
        "## Analysis & Reasoning",
        "## Conclusion",
        "## References",
    ]
    for heading in expected_headings:
        assert re.search(rf"^{re.escape(heading)}\s*$", template_text, flags=re.M), f"Template missing '{heading}'"

    # Check all other files
    for path in sorted(ROOT.glob("*.md")):
        if path.name == TEMPLATE.name:
            continue

        print(f"[DEBUG] Checking profiler playbook structure: {path.relative_to(ROOT)}")
        text = _read(path)

        # YAML keys
        assert text.lstrip().startswith("---"), f"{path}: Missing YAML front-matter"
        for key in REQUIRED_YAML_KEYS:
            assert re.search(rf"^{key}\s*\S", text, flags=re.M), f"{path}: Missing YAML key: {key}"

        # Headings
        for heading in expected_headings:
            assert re.search(rf"^{re.escape(heading)}\s*$", text, flags=re.M), f"{path}: Missing '{heading}'"

        # No tooling artifacts
        assert "oaicite" not in text, f"{path}: Contains tooling artifact 'oaicite'"
        assert "contentReference" not in text, f"{path}: Contains tooling artifact 'contentReference'"
