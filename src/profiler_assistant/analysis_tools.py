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

