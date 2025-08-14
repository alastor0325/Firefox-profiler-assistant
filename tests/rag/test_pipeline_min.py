"""
Minimal, fast tests for the RAG pipeline glue. These tests monkeypatch the
rag modules so no heavy models or FAISS are required.
"""
from __future__ import annotations
from pathlib import Path
import json
import types
import profiler_assistant.rag.pipeline as pipeline


class _TmpMod(types.SimpleNamespace):
    pass


def _fake_modules(monkeypatch, tmp_path: Path):
    # Fake rag.ingest
    ingest = _TmpMod()
    def _ingest_run(input_path: str, *, domain: str, out_jsonl: str):
        rows = [{"doc_id": "d", "chunk_id": 0, "text": "hello world", "source": str(input_path), "domain": domain}]
        Path(out_jsonl).parent.mkdir(parents=True, exist_ok=True)
        with open(out_jsonl, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        return out_jsonl
    ingest.run = _ingest_run

    # Fake rag.embeddings
    embeddings = _TmpMod()
    def _emb_run(jsonl_path: str, *, model: str, out_path: str):
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(b"FAKEVEC")
        return out_path
    embeddings.run = _emb_run

    # Fake rag.index
    index = _TmpMod()
    def _build(emb_path: str, meta_jsonl: str, *, index_dir: str):
        Path(index_dir).mkdir(parents=True, exist_ok=True)
        with open(Path(index_dir)/"ok", "w") as f:
            f.write("ok")
        return index_dir
    def _search(query: str, *, k: int, index_dir: str):
        return [{"score": 1.0, "source": "fake", "text": "hello world"}]
    index.build = _build
    index.search = _search

    monkeypatch.setattr(pipeline, "_mod", lambda name: {"ingest": ingest, "embeddings": embeddings, "index": index}[name])


def test_build_all_and_search(monkeypatch, tmp_path):
    _fake_modules(monkeypatch, tmp_path)
    inp = tmp_path/"doc.md"
    inp.write_text("hi")
    outs = pipeline.build_all(inp, workdir=tmp_path/"work", model="mini")
    assert outs.jsonl_path.exists()
    assert outs.embeddings_path.exists()
    assert outs.index_dir.exists()
    hits = pipeline.search("hello", index_dir=outs.index_dir)
    assert hits and hits[0]["text"].startswith("hello")
