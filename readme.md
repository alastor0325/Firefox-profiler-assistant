# Firefox Profiler Assistant

An AI-powered command-line tool to analyze performance profiles from the Firefox Profiler. This tool can download a profile directly from a `share.firefox.dev` URL or load a local file, parse the complex JSON structure, and interactively analyze the profile using an LLM assistant (Gemini-powered).

---

## ✨ Features

- **AI Assistant (LLM CLI)**: Ask questions like “Any dropped frames?” or “Which thread used the most CPU?”
- **Direct Download**: Fetches profiles directly from `share.firefox.dev` URLs.
- **Local File Support**: Analyzes `profile.json` files from your disk.
- **Fast Parsing**: Uses `orjson` and `pandas` for high-performance profile handling.
- **Tool-Based Architecture**: Modular tools for media/jank analysis and marker extraction.

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

## RAG Knowledge Base

We store investigation docs in `knowledge/raw/` as Markdown with YAML front-matter.
These are ingested into JSONL chunks for later retrieval.

### Folder layout
```
knowledge/
  raw/
    profiler/
      example_profiler_playbook.md   # template & schema example (tests validate this)
      bugXXX_ISSUE.md                # real investigation using the template

src/
  profiler_assistant/
    rag/
      ingest.py                      # Markdown → JSONL chunker
      embeddings.py                  # Embedding backends (Dummy, SentenceTransformers, swappable via env)
      index.py                       # Vector index backends (NumpyIndex, optional FaissIndex)

tests/
  test_rag_ingest.py                  # validates example doc & ingestion
  test_rag_embeddings.py              # validates embedding backends
  test_rag_index.py                   # validates vector index backends
```

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

Test folders:
- `tests/` — unit tests for core tools
- `tests/test_agent/` — tests for the ReAct agent, Gemini client, and CLI logic

---

## 📦 Notes

- Requires Python 3.8+
- LLM agent uses `gemini-1.5-flash` (free-tier friendly)
- `.env` is ignored by Git for API key safety

---

## 🛠 CI/CD

This project uses **GitHub Actions** to run the test suite automatically on every push and pull request. The workflow is defined in:

```
.github/workflows/python-app.yml
```
