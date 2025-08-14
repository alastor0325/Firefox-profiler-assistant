"""
Orchestrate ingest → embeddings → index for the RAG stack used by the
Firefox Profiler Assistant. This wires together existing modules under
`profiler_assistant.rag` while adapting to either:
- The "real" modules in this repo (ingest_file/ingest_tree, get_backend, get_default_index), or
- The minimal test fakes (ingest.run, embeddings.run, index.build/search).
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any
import importlib
import json
import time


@dataclass
class BuildOutputs:
    jsonl_path: Path
    embeddings_path: Path
    index_dir: Path


# Defaults are local, deterministic locations.
_DEF_WORKDIR = Path("data/rag")
_DEF_JSONL = _DEF_WORKDIR / "chunks.jsonl"
_DEF_EMB = _DEF_WORKDIR / "embeddings.npy"  # when using get_backend() path
_DEF_INDEXDIR = Path(".fpa_index")


def _mod(name: str):
    return importlib.import_module(f"profiler_assistant.rag.{name}")


def _load_jsonl_rows(p: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _save_metas_jsonl(metas: List[Dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for m in metas:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")


def build_all(
    input_path: str | Path,
    *,
    domain: str = "profile",  # kept for compatibility
    workdir: Path = _DEF_WORKDIR,
    model: str = "auto",
    jsonl_path: Optional[str | Path] = None,
    emb_path: Optional[str | Path] = None,
    index_dir: Optional[str | Path] = None,
) -> BuildOutputs:
    """Run the end-to-end build. Returns artifact locations."""
    t0 = time.perf_counter()
    input_path = Path(input_path)
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    jsonl = Path(jsonl_path) if jsonl_path else (workdir / _DEF_JSONL.name)
    emb = Path(emb_path) if emb_path else (workdir / _DEF_EMB.name)
    idxdir = Path(index_dir) if index_dir else _DEF_INDEXDIR
    idxdir.mkdir(parents=True, exist_ok=True)

    ingest = _mod("ingest")
    emb_mod = _mod("embeddings")
    idx_mod = _mod("index")

    # ---------------- 1) Ingest ----------------
    print(f"[RAG] Ingest: input={input_path}")
    if hasattr(ingest, "ingest_tree") or hasattr(ingest, "ingest_file"):
        # Real module shape
        if input_path.is_dir() and hasattr(ingest, "ingest_tree"):
            ingest.ingest_tree(input_path, jsonl)
        else:
            if not hasattr(ingest, "ingest_file"):
                raise AttributeError("ingest module lacks ingest_file() for single-file input")
            chunks = ingest.ingest_file(input_path)
            if hasattr(ingest, "write_jsonl"):
                ingest.write_jsonl(chunks, jsonl)
            else:
                # Fallback: expect chunks to have .to_json()
                jsonl.parent.mkdir(parents=True, exist_ok=True)
                with jsonl.open("w", encoding="utf-8") as f:
                    for ch in chunks:
                        f.write(ch.to_json() + "\n")
    elif hasattr(ingest, "run"):
        # Test fake shape
        ingest.run(str(input_path), domain=domain, out_jsonl=str(jsonl))
    else:
        raise AttributeError("ingest module must provide ingest_tree/ingest_file or run()")
    print(f"[RAG] Ingest: wrote {jsonl}")

    # ---------------- 2) Embeddings ----------------
    if hasattr(emb_mod, "get_backend"):
        rows = _load_jsonl_rows(jsonl)
        texts = [r.get("text", "") for r in rows]
        backend = emb_mod.get_backend()
        print(f"[RAG] Embeddings: encoding {len(texts)} chunks with backend={type(backend).__name__}")
        import numpy as np  # local import to avoid hard dep if unused
        vectors = backend.encode(texts)
        emb.parent.mkdir(parents=True, exist_ok=True)
        np.save(emb, vectors.astype(np.float32))
        print(f"[RAG] Embeddings: wrote {emb} shape={vectors.shape}")
        # If we’re going to build a local index, prepare metas now
        prepared_metas: Optional[List[Dict[str, Any]]] = []
        for r in rows:
            doc_id = r.get("doc_id")
            chunk_id = r.get("chunk_id")
            section = r.get("section")
            title = r.get("title") or section
            prepared_metas.append({
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "section_path": f"{doc_id}/{section}" if doc_id and section else section,
                "heading": title,
            })
    elif hasattr(emb_mod, "run"):
        # Test fake shape
        emb.parent.mkdir(parents=True, exist_ok=True)
        emb_mod.run(str(jsonl), model=model, out_path=str(emb))
        prepared_metas = None
    else:
        raise AttributeError("embeddings module must provide get_backend() or run()")

    # ---------------- 3) Index ----------------
    if hasattr(idx_mod, "build"):
        # Test fake shape
        idx_mod.build(str(emb), str(jsonl), index_dir=str(idxdir))
        print(f"[RAG] Index: built via index.build() under {idxdir}")
    elif hasattr(idx_mod, "get_default_index"):
        # Real module shape – build simple on-disk artifacts
        import numpy as np
        vectors = np.load(emb).astype(np.float32)
        metas: List[Dict[str, Any]]
        if prepared_metas is None:
            # If embeddings came from .run path, recreate metas from JSONL
            rows = _load_jsonl_rows(jsonl)
            metas = []
            for r in rows:
                doc_id = r.get("doc_id")
                chunk_id = r.get("chunk_id")
                section = r.get("section")
                title = r.get("title") or section
                metas.append({
                    "doc_id": doc_id,
                    "chunk_id": chunk_id,
                    "section_path": f"{doc_id}/{section}" if doc_id and section else section,
                    "heading": title,
                })
        else:
            metas = prepared_metas

        dim = int(vectors.shape[1]) if vectors.ndim == 2 else 0
        index = idx_mod.get_default_index(dim)
        index.add(vectors, metas)
        # Persist “index” artifacts: vectors + metas
        import numpy as np  # (already imported above, but safe)
        np.save(idxdir / "vectors.npy", vectors.astype(np.float32))
        _save_metas_jsonl(metas, idxdir / "metas.jsonl")
        print(f"[RAG] Index: saved vectors.npy and metas.jsonl under {idxdir}")
    else:
        raise AttributeError("index module must provide build() or get_default_index()")

    print(f"[RAG] Build done in {time.perf_counter() - t0:.3f}s")
    return BuildOutputs(jsonl_path=jsonl, embeddings_path=emb, index_dir=idxdir)


def search(query: str, *, k: int = 5, index_dir: str | Path = _DEF_INDEXDIR) -> List[Dict[str, Any]]:
    """Search using the module's search() if available; otherwise, load artifacts and search locally."""
    idx_mod = _mod("index")
    if hasattr(idx_mod, "search"):
        # Test fake shape
        return idx_mod.search(query, k=k, index_dir=str(index_dir))

    # Fallback: local search using saved vectors/metas and current embeddings backend
    index_dir = Path(index_dir)
    vec_path = index_dir / "vectors.npy"
    meta_path = index_dir / "metas.jsonl"
    if not vec_path.exists() or not meta_path.exists():
        print(f"[RAG] Search: missing index artifacts in {index_dir}")
        return []

    import numpy as np
    vectors = np.load(vec_path).astype(np.float32)
    metas = _load_jsonl_rows(meta_path)

    idx_mod = _mod("index")
    emb_mod = _mod("embeddings")
    dim = int(vectors.shape[1]) if vectors.ndim == 2 else 0
    index = idx_mod.get_default_index(dim)
    index.add(vectors, metas)

    backend = emb_mod.get_backend()
    q_vec = backend.encode([query])[0]
    hits = index.search(q_vec, k=k)
    print(f"[RAG] Search: query={query!r} k={k} -> {len(hits)} hits")
    return hits


def load_chunks(jsonl_path: str | Path) -> List[dict]:
    """Utility to load JSONL rows (useful for debugging/tests)."""
    return _load_jsonl_rows(Path(jsonl_path))
