# Pipeline Overview

## Architecture at a glance
Ingest → Normalize → Chunk → Embed → Index (Vector + optional Sparse) → Retrieve → (optional) Rerank → Context Pack → LLM Orchestration → Answer + Citations

```
Data Sources ─▶ Ingest ─▶ Normalize ─▶ Chunk ─▶ Embed ─▶ Index ─▶ Retrieve ─▶ Rerank ─▶ Pack ─▶ LLM ─▶ Answer
(Profiles, md)                                 (hash/cache)      (FAISS/HNSW + BM25)              (budget-aware)
```

## Data sources & formats
- Firefox Profiler profiles (JSON/URL), repository notes (md).
- Each source is normalized into a canonical doc with metadata.

### Processing stages (current vs planned)

| Stage         | Input / Purpose                                              | Current status in repo | Notes / Evidence |
|---------------|--------------------------------------------------------------|------------------------|------------------|
| **Ingest**    | Load local Markdown “playbooks” (per `config/rag.toml`) and prepare artifacts | ✅ Implemented          | `src/profiler_assistant/rag/ingest.py` (docs mention: converts Markdown → JSONL chunks) |
| **Normalize** | Canonicalize/clean text before chunking                      | ✅ Implemented (basic)  | normalization happens within ingest prior to chunking |
| **Chunk**     | Split docs into retrievable spans                            | ✅ Implemented          | “Ingest — Markdown → JSONL chunks” |
| **Embed**     | Generate embeddings for chunks                               | ✅ Implemented          | `src/profiler_assistant/rag/embeddings.py` with swappable backends (`dummy`, `sentence-transformers`) |
| **Index**     | Build/query vector index (optionally FAISS)                  | ✅ Implemented          | `src/profiler_assistant/rag/index.py` — `NumpyIndex` (default) and `FaissIndex` (not yet) |
| **Retrieve**  | Top‑k search over the index                                  | ✅ Implemented          | Index module provides search used by the pipeline |
| **Orchestrate** | Run RAG pipeline and LLM CLI interaction                   | ✅ Implemented          | `src/profiler_assistant/rag/pipeline.py` |
| **Rerank***   | Reorder candidates with cross‑encoder/LLM                    | ❌ Not implemented      |  |
| **Pack**      | Budget‑aware context packing (dedupe/merge)                  | ❌ Not implemented      |  |


---

## Stage-by-stage Details

> This section explains each stage in the pipeline: what it does, what goes in/out, where artifacts live, validation checks, and operational notes.

---

## 1) Ingest

**What it does**
- Scans configured sources (e.g., local Markdown “playbooks”) and loads document text + minimal front‑matter.
- Produces a **normalized document stream** suitable for chunking.

**Inputs**
- Paths/patterns from `config/rag.toml` (e.g., a `/knowledge/` folder).
- UTF‑8 text files (Markdown).

**Outputs (derived, git‑ignored)**
- `data/rag/chunks.jsonl` (after chunk stage; see stage 3)

**Key behaviors**
- Deterministic traversal for repeatable builds.
- Skips binary/unsupported files; logs what was skipped.
- Associates a stable `doc_id` and basic metadata (source path, title).

**Validation & logging**
- Log counts: scanned files, accepted docs, skipped docs.
- Log reasons for skip (pattern excluded, unreadable).
- Dry‑run mode (recommended in CI) to show what would be ingested.

**Common issues**
- *No files matched:* confirm `config/rag.toml` exists and patterns are correct.
- *Windows/globs mismatch:* prefer `**/*.md` style; normalize path separators.

---

## 2) Normalize

**What it does**
- Cleans and canonicalizes text **before** chunking:
  - Normalize line endings and whitespace.
  - Strip large boilerplate sections if configured.
  - Preserve headings and meaningful structure.

**Inputs**
- Raw text from ingest.

**Outputs**
- Canonical strings (still in‑memory stream) handed to the chunker.

**Validation & logging**
- Log character counts before/after normalization.
- Log any front‑matter keys extracted (if used).
- Emit warnings for extremely short/empty docs.

---

## 3) Chunk

**What it does**
- Splits documents into **retrievable spans** sized for embedding/retrieval.
- Default strategy: **fixed‑token windows with overlap**; optionally aware of headings.

**Inputs**
- Normalized document strings (+ doc metadata).

**Outputs (derived, git‑ignored)**
- `data/rag/chunks.jsonl`, one JSON object per line. Recommended fields:
  - `doc_id` (stable across versions)
  - `chunk_id` (e.g., `sha1(text)` prefix)
  - `text`
  - `section_path` (e.g., `h1 > h2 > ...`)
  - `tokens` (optional cached token count)
  - `source_path` (optional path for traceability)

**Heuristics**
- Token size: 600–800 tokens; overlap: 10–20% (tune per eval).
- Avoid splitting within code blocks or stack traces.
- Merge tiny trailing sections into a neighbor.

**Validation & logging**
- Log number of chunks per doc; flag extremes.
- Ensure `chunk_id` uniqueness per build.

**Common issues**
- *Context fragmentation:* increase chunk size or use heading‑aware splits.
- *Duplicates:* dedupe by content hash.

---

## 4) Embed

**What it does**
- Encodes each chunk into a vector using a pluggable **embedding backend**.

**Inputs**
- `data/rag/chunks.jsonl` (text and metadata).

**Outputs (derived, git‑ignored)**
- `data/rag/embeddings.npy` — `float32` matrix with shape `[num_chunks, dim]`.

**Backends**
- **Dummy** (deterministic; zero external deps) — great for dev/CI.
- **SentenceTransformers** (e.g., `all-MiniLM-L6-v2`) when installed.
- Select via env var (e.g., `FPA_EMBEDDINGS=dummy|sentence-transformers`).

**Caching**
- Key by `(model_name, sha1(chunk_text))`.
- Re‑embed only when content hash or model version changes.

**Validation & logging**
- Log vector dimension and row count; assert rows == chunks.
- Emit distribution stats (min/max norms) in debug to catch anomalies.

---

## 5) Index

**What it does**
- Builds a vector index for cosine/dot similarity search.
- Keeps lightweight metadata for result reconstruction.

**Inputs**
- `data/rag/embeddings.npy` + chunk metadata.

**Outputs (derived, git‑ignored)**
- `.fpa_index/vectors.npy` — contiguous vectors (optional copy from embeddings).
- `.fpa_index/metas.jsonl` — aligned metadata for each vector.

**Implementations**
- **NumpyIndex (default):** exact search, simple, no external deps.
- **FaissIndex (optional):** faster large‑scale search (if `faiss`/`faiss-cpu` installed).

**Validation & logging**
- Log index type, vector count, and build time.
- For FAISS, log factory string / metric; for NumPy, log exact mode.

**Common issues**
- *Misalignment:* ensure vector rows == metas rows; fail fast if not.

---

## 6) Retrieve

**What it does**
- Executes **top‑k similarity search** against the index for a user query.

**Inputs**
- User query string.
- Index artifacts + metadata.

**Outputs**
- Ranked list of candidates: `(chunk_id, score, doc_id, section_path, text_snippet)`.

**Flow**
1. Normalize query (trim, lowercase where safe, collapse whitespace).
2. Encode query with the same embedding backend.
3. Search `top_n` (e.g., 50) to maximize recall.
4. Return `top_k` (e.g., 8–12) for downstream use.

**Validation & logging**
- Log query vector norm and latency.
- Log `top_n`/`top_k` and scores histogram (debug).
- If no results, log the fact and fallback guidance.

---

## 7) Orchestrate (LLM CLI)

**What it does**
- On CLI startup, **optionally** runs the RAG build (ingest → embed → index) if `config/rag.toml` exists.
- At query time, runs retrieve → (optional) rerank/pack → prompts the LLM.

**Inputs**
- A Firefox Profiler profile (URL or local file) for analysis.
- Optional RAG artifacts for grounded answers.

**Outputs**
- Final answer text; when RAG is active, include citations (doc/chunk provenance).

**Operational notes**
- If `config/rag.toml` is missing or no files match, the CLI continues **without** RAG.
- LLM backend: Gemini model (configurable in env); tool calls perform profiler analysis.
- Keep logs: RAG enabled/disabled; counts (docs, chunks, embeddings); retrieval latency.

---

## 8) (Optional) Rerank — not implemented yet

**Purpose**
- Re‑order `top_n` retrieved candidates using a higher‑cost scorer (cross‑encoder or LLM) to improve **precision@k**.

**Minimal design (future)**
- Gate by flag (e.g., `--rerank`).
- Cache scores by `(query_hash, chunk_id)`.
- Evaluate with golden queries; success = +10–15% nDCG@5 without recall loss.

**Risks**
- Latency, cost, added complexity.

---

## 9) (Optional) Pack — not implemented yet

**Purpose**
- Select and **order** chunks to fit token budget; dedupe and merge adjacent spans for coherence.

**Minimal heuristics (future)**
1. Group by `(doc_id, section_path)`.
2. Merge adjacent chunks if combined ≤ max span threshold.
3. Always include the top‑1 unmerged chunk; then fill until budget.

**Validation**
- Log decisions: kept/dropped, token counts, merged ranges.
- Tests assert determinism (fixed seeds, fixed token budgets).

---