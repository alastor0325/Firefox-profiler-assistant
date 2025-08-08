import argparse
import os
from profiler_assistant.downloader import get_profile_from_url
from profiler_assistant.parsing import load_and_parse_profile
from profiler_assistant.agent.react_agent import run_react_agent

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

        profile = load_and_parse_profile(profile_path)
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
