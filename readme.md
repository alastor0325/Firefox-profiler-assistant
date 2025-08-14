# Firefox Profiler Assistant

An AI-powered command-line tool to analyze performance profiles from the Firefox Profiler. This tool can download a profile directly from a `share.firefox.dev` URL or load a local file, parse the complex JSON structure, and interactively analyze the profile using an LLM assistant (Gemini-powered).

---

## ✨ Features

- **AI Assistant (LLM CLI)**: Ask questions like “Any dropped frames?” or “Which thread used the most CPU?”
- **Direct Download**: Fetches profiles directly from `share.firefox.dev` URLs.
- **Local File Support**: Analyzes `profile.json` files from your disk.
- **Fast Parsing**: Uses `orjson` and `pandas` for high-performance profile handling.
- **Tool-Based Architecture**: Modular tools for media/jank analysis and marker extraction.
- **RAG Knowledge Base**: Ingests local Markdown playbooks, builds embeddings, and creates a small on-disk index that the agent can use for grounded answers.

---

## 🚀 Installation

1. **Clone the repository:**

```bash
git clone https://github.com/alastor0325/Firefox-profiler-assistant.git
cd Firefox-profiler-assistant
```

2. **Set up a virtual environment:**

```bash
python -m venv venv
source venv/bin/activate      # On Windows: venv\Scripts\activate
```

3. **Install the project and dependencies:**

```bash
pip install -e .
```
> We support Python 3.8+. On Python < 3.11, the package `tomli` is used to read the TOML config.

4. **Set up your Gemini API key:**

Create a `.env` file in the project root:

```
GEMINI_API_KEY=your-api-key-here
```

You can get your key from [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)

> 🧪 **Note**: Gemini is currently used as a fast and stable option for building the MVP. We may switch to an open-source LLM in a future phase to support local/offline or more customizable models.

---

## 🧠 Usage (LLM CLI Assistant)

Run the assistant with either a URL or local file:

```bash
profiler-assistant <PROFILE_SOURCE>
```

`<PROFILE_SOURCE>` can be:

- A Firefox Profiler share URL (e.g., `https://share.firefox.dev/3HkKTjj`)
- A path to a local `profile.json` file

### 🔹 Example (from URL):

```bash
profiler-assistant https://share.firefox.dev/3HkKTjj
```

### 🔹 Example (from local file):

```bash
profiler-assistant profiles/sample-profile.json
```

Then interact with the assistant:

```text
👤 You: any dropped frames?
🤖 Final Answer: Yes, 15 dropped frames were detected on MediaDecoderStateMachine.
```

---

## 📚 Retrieval-Augmented Generation (RAG)

### How it works
On startup, the CLI **automatically** looks for a TOML config at `config/rag.toml` and, if present, performs:
1. **Ingest** — Markdown → JSONL chunks
2. **Embeddings** — Encode chunk text with a pluggable embedding backend
3. **Index** — Save lightweight artifacts for fast search

These steps are handled by:
- `profiler_assistant/rag/ingest.py`
- `profiler_assistant/rag/embeddings.py`
- `profiler_assistant/rag/index.py`
- Orchestrated by `profiler_assistant/rag/pipeline.py`

### Required config
In `config/rag.toml`, you can specify where the RAG knowledge sources should come from.

> If this file is missing or no files match, the CLI prints a message and continues without RAG.

### Artifacts (generated)
- `data/rag/chunks.jsonl` — ingested chunks (one JSON per line)
- `data/rag/embeddings.npy` — NumPy array of embeddings for chunks
- `.fpa_index/vectors.npy` and `.fpa_index/metas.jsonl` — lightweight “index” artifacts

> These are derived and **should not be committed**.

### Backends

We use a swappable backend design for both embedding generation and vector indexing:

- **Embeddings**
  - `DummyBackend` (default, deterministic, no deps — best for dev/CI)
  - `SentenceTransformersBackend` (“all-MiniLM-L6-v2”) if `sentence-transformers` is installed
  - Switch via `FPA_EMBEDDINGS` env var (`dummy` / `sentence-transformers`)

- **Index**
  - `NumpyIndex` (default, exact cosine search, no deps)
  - `FaissIndex` (fast large-scale search if `faiss`/`faiss-cpu` is installed)

### Authoring rules
- Start from `example_profiler_playbook.md` when creating a new doc.
- Keep **all** required front-matter keys (even if empty).
- Use **five required sections**:
  1. `# Summary`
  2. `## Signals & Evidence`
  3. `## Analysis & Reasoning`
  4. `## Conclusion`
  5. `## References`

---

## 🧪 Development

To set up for development:

```bash
pip install -e .
```

Then ensure `.env` is present with your Gemini API key.

---

### ✅ Running Tests

We use `pytest` for tests. To run them:

```bash
pytest
```

---

## 📝 Troubleshooting

- **No RAG prints appear**: confirm `config/rag.toml` exists and that files match your `include`/`exclude` patterns.
- **On Windows, excludes don’t seem to work**: we normalize paths and match both relative paths and basenames; use either `**/name.md` or just `name.md` in `exclude`.
- **Using older Python**: `tomli` will be used automatically (declared as a dependency) for reading TOML on Python < 3.11.


---

## 📦 Notes

- Requires Python 3.8+
- LLM agent uses `gemini-1.5-flash` (free-tier friendly)
- `.env` is ignored by Git for API key safety
- RAG artifacts are ephemeral and should be git‑ignored (`data/rag/`, `.fpa_index/`)

---

## 🛠 CI/CD

This project uses **GitHub Actions** to run the test suite automatically on every push and pull request. The workflow is defined in:

```
.github/workflows/python-app.yml
```
