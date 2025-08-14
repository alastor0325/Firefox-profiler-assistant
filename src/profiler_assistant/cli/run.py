import argparse
import os

from profiler_assistant.downloader import get_profile_from_url
from profiler_assistant.parsing import load_and_parse_profile
from profiler_assistant.agent.react_agent import run_react_agent
from profiler_assistant.rag import pipeline as rag_pipeline
from profiler_assistant.rag.config import load_rag_config, iter_candidate_files


def refresh_rag_knowledge_index() -> None:
    """
    Refresh the RAG knowledge index from local project sources,
    using the fixed config path 'config/rag.toml'.
    Errors are printed (so they're visible) but do not crash the main flow.
    """
    try:
        cfg = load_rag_config()  # fixed path: config/rag.toml
        any_found = False
        for file_path in iter_candidate_files(cfg):
            any_found = True
            rag_pipeline.build_all(file_path, domain="kb", index_dir=".fpa_index")
        if not any_found:
            print("[RAG] No knowledge files matched include/exclude patterns.")
    except FileNotFoundError as e:
        print(f"[RAG] Config error: {e}")
    except Exception as e:
        # Non-fatal: keep CLI usable even if RAG prep fails for other reasons
        print(f"[RAG] Indexing failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="Firefox Profiler Assistant (LLM-powered CLI)")
    parser.add_argument(
        "profile_source",
        type=str,
        help="Path to local profile.json OR a Firefox Profiler share URL"
    )
    args = parser.parse_args()

    profile_path = args.profile_source
    is_temp_file = False

    try:
        if profile_path.startswith("http://") or profile_path.startswith("https://"):
            profile_path = get_profile_from_url(profile_path)
            is_temp_file = True

        # Primary flow: parse profile first
        profile = load_and_parse_profile(profile_path)

        # Then, best-effort (but visible) refresh of the KB index from fixed config
        refresh_rag_knowledge_index()

        history = []

        print("🧠 Firefox Profiler Assistant (LLM CLI)\nType 'exit' to quit.\n")

        while True:
            question = input("👤 You: ")
            if question.strip().lower() in {"exit", "quit"}:
                break

            result = run_react_agent(profile, question, history)

            if "final" in result:
                print("🤖", result["final"])
                history.append({"role": "assistant", "content": result["final"]})
            elif "tool_result" in result:
                summary = str(result["tool_result"])[:1000]
                print("🔧 Tool result:", summary)
                history.append({"role": "assistant", "content": f"Tool result: {summary}"})
            else:
                print("❌", result["error"])

    finally:
        if is_temp_file and os.path.exists(profile_path):
            os.remove(profile_path)
            print(f"[*] Cleaned up temporary file: {profile_path}")

if __name__ == "__main__":
    main()
