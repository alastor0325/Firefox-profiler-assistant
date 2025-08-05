# src/profiler_assistant/main.py

import argparse
import os
from.parsing import load_and_parse_profile
from.downloader import get_profile_from_url
from.analysis_tools import find_stutter_markers

def main():
    """
    The main entry point for the project.
    Handles command-line arguments and initiates the analysis process.
    """
    parser = argparse.ArgumentParser(
        description="An AI assistant to analyze Firefox Profiler results."
    )
    parser.add_argument(
        "profile_source",
        type=str,
        help="Path to a local profile.json file or a share.firefox.dev URL."
    )

    args = parser.parse_args()
    profile_path = args.profile_source
    is_temp_file = False

    try:
        if profile_path.startswith("http://") or profile_path.startswith("https://"):
            profile_path = get_profile_from_url(profile_path)
            is_temp_file = True

        profile = load_and_parse_profile(profile_path)

        print("\n--- Profile Summary ---")
        start_time = profile.meta.get('startTime', 0)
        end_time = profile.meta.get('endTime', 0)
        duration = (end_time - start_time) / 1000 if end_time > start_time else 0
        print(f"Duration: {duration:.2f} seconds")
        print(f"Found {len(profile.threads)} threads.")

        # --- Run Analysis Tools ---
        print("\n--- Running Analysis ---")

        stutter_events = find_stutter_markers(profile)

        if not stutter_events.empty:
            print(f"[!] Found {len(stutter_events)} potential stutter/jank events:")
            # Print the results in a clean table format
            print(stutter_events.to_string(index=False))
        else:
            print("[+] No common stutter or jank markers found in the profile.")

        print("\nAnalysis complete.")

    except (FileNotFoundError, ConnectionError, ValueError) as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if is_temp_file and os.path.exists(profile_path):
            os.remove(profile_path)
            print(f"\n[*] Cleaned up temporary file: {profile_path}")

if __name__ == "__main__":
    main()