# src/profiler_assistant/analysis_tools.py

import pandas as pd
from.parsing import Profile

def find_stutter_markers(profile: Profile) -> pd.DataFrame:
    """
    Scans all threads in a profile for common stutter-related markers.
    Returns a DataFrame with matched marker name, thread name, and time.
    """
    stutter_marker_names = {"Jank", "VideoFallingBehind"}
    found = []

    # Map marker name → stringTable index
    string_index_map = {
        idx: name
        for idx, name in profile.string_table.items()
        if name in stutter_marker_names
    }

    if not string_index_map:
        return pd.DataFrame()

    for process in profile.processes.values():
        for thread in process["threads"]:
            markers_df = thread["markers"]
            if markers_df.empty:
                continue
            if "name" not in markers_df or "startTime" not in markers_df:
                continue

            mask = markers_df["name"].isin(string_index_map.keys())
            for _, row in markers_df[mask].iterrows():
                marker_idx = row["name"]
                found.append({
                    "markerName": string_index_map[marker_idx],
                    "threadName": thread["name"],
                    "processName": thread["process_name"],
                    "time": row["startTime"]
                })

    return pd.DataFrame(found)

def find_media_playback_content_processes(profile: Profile) -> pd.DataFrame:
    """
    Return all 'Isolated Web Content' processes that have media playback activity.

    A process qualifies if:
    - It is named 'Isolated Web Content'
    - It contains a thread named 'MediaDecoderStateMachine' with markers

    Parameters:
    profile (Profile): Parsed profiler data.

    Returns:
    pd.DataFrame: Filtered DataFrame with only the matching processes.
    """
    matching_processes = []

    for process in profile.processes.values():
        if process.get("process_name") != "Isolated Web Content":
            continue

        threads = process.get("threads", [])
        for thread in threads:
            if (
                thread.get("name") == "MediaDecoderStateMachine"
                and thread.get("markers")
                and len(thread["markers"]) > 0
            ):
                matching_processes.append(process)
                break

    return pd.DataFrame(matching_processes)

def find_rendering_process(profile: Profile) -> pd.Series:
    """
    Return the first process that contains both a Renderer and Compositor thread.

    Parameters:
    profile (Profile): Parsed profiler data.

    Returns:
    pd.Series: The first matching process row.
    """
    for process in profile.processes.values():
        threads = process.get("threads", [])
        thread_names = {thread.get("name") for thread in threads}

        if "Renderer" in thread_names and "Compositor" in thread_names:
            return pd.Series(process)

    raise ValueError("No rendering process found")
