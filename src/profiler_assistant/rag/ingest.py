"""
Minimal Markdown -> JSONL chunker for the knowledge base.
- No external deps (naive front‑matter parser with safe fallbacks)
- Produces one chunk per top-level section (# or ##)
- Fields: doc_id, chunk_id, text, section, tags, source, updated_at
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
HEADER_RE = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass
class Chunk:
    doc_id: str
    chunk_id: str
    text: str
    section: str
    tags: List[str]
    source: Optional[str] = None
    updated_at: Optional[str] = None
    title: Optional[str] = None
    meta: Dict[str, object] = field(default_factory=dict)  # full front-matter passthrough

    def to_json(self) -> str:
        return json.dumps(
            {
                "doc_id": self.doc_id,
                "chunk_id": self.chunk_id,
                "text": self.text.strip(),
                "section": self.section,
                "tags": self.tags,
                "source": self.source,
                "updated_at": self.updated_at,
                "title": self.title,
                "meta": self.meta,
                "embedding": None, # filled later
            },
            ensure_ascii=False,
        )



def _slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s


def parse_markdown(md_text: str) -> Tuple[Dict[str, object], str]:
    """Return (front_matter_dict, body_markdown). If no front‑matter, returns ({} , text)."""
    m = FRONT_MATTER_RE.match(md_text)
    if not m:
        return {}, md_text
    fm_raw, body = m.group(1), m.group(2)
    return _parse_front_matter_naive(fm_raw), body


def _parse_front_matter_naive(fm_raw: str) -> Dict[str, object]:
    """Parse a small subset of YAML used in our docs without external deps.
    Supports lines like `key: value` and JSON-ish lists: tags: ["a","b"].
    """
    import ast

    data: Dict[str, object] = {}
    for line in fm_raw.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key, val = key.strip(), val.strip()
        if not val:
            data[key] = ""
            continue
        # Try to parse list or quoted scalars with ast.literal_eval after a quick normalization
        if val.startswith("[") and val.endswith("]"):
            try:
                data[key] = ast.literal_eval(val)
                continue
            except Exception:
                pass
        # Unquote simple quoted strings
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            data[key] = val[1:-1]
        else:
            data[key] = val
    return data


def split_into_sections(md_body: str) -> List[Tuple[str, str]]:
    """Return list of (section_title, section_text). Uses first H1/H2 headers as boundaries."""
    lines = md_body.splitlines()
    sections: List[Tuple[str, List[str]]] = []
    current_title = "preamble"
    current_buf: List[str] = []

    for line in lines:
        h = HEADER_RE.match(line)
        if h and len(h.group(1)) <= 2:  # H1 or H2 start a new section
            if current_buf:
                sections.append((current_title, current_buf))
            current_title = h.group(2).strip()
            current_buf = []
        else:
            current_buf.append(line)

    # flush
    if current_buf:
        sections.append((current_title, current_buf))

    # Join buffers
    return [(title, "\n".join(buf).strip()) for title, buf in sections if "".join(buf).strip()]


def build_chunks(meta: Dict[str, object], sections: List[Tuple[str, str]]) -> List[Chunk]:
    doc_id = str(meta.get("id") or meta.get("doc_id") or "unknown-doc")
    tags_val = meta.get("tags")
    tags = tags_val if isinstance(tags_val, list) else []
    source_val = meta.get("source")
    source = str(source_val) if isinstance(source_val, str) or source_val is None else None
    updated_at_val = meta.get("updated_at")
    updated_at = str(updated_at_val) if updated_at_val is not None else None
    title_val = meta.get("title")
    title = str(title_val) if isinstance(title_val, str) else None  # Ensure type is str or None

    chunks: List[Chunk] = []
    for idx, (title_raw, text) in enumerate(sections):
        section_slug = _slugify(title_raw) or f"section-{idx}"
        chunk_id = f"{doc_id}#{idx}"
        chunks.append(
            Chunk(
                doc_id=doc_id,
                chunk_id=chunk_id,
                text=text,
                section=section_slug,
                tags=tags,
                source=source,
                updated_at=updated_at,
                title=title,
                meta=meta,   # keep everything (bugzilla_id, links, product_area…)
            )
        )
    return chunks

def write_jsonl(chunks: Iterable[Chunk], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(ch.to_json() + "\n")


def ingest_file(path: Path) -> List[Chunk]:
    text = path.read_text(encoding="utf-8")
    meta, body = parse_markdown(text)
    sections = split_into_sections(body)
    return build_chunks(meta, sections)


def discover_markdown(root: Path) -> List[Path]:
    return [p for p in root.rglob("*.md") if p.is_file()]


def ingest_tree(input_dir: Path, out_file: Path) -> int:
    """Ingest all markdown files under input_dir into a single JSONL file. Returns chunk count."""
    files = discover_markdown(input_dir)
    all_chunks: List[Chunk] = []
    for p in sorted(files):
        all_chunks.extend(ingest_file(p))
    write_jsonl(all_chunks, out_file)
    return len(all_chunks)
