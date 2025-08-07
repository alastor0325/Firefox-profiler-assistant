# src/profiler_assistant/analysis_tools.py

import pandas as pd
from copy import deepcopy
from.parsing import Profile
from typing import Optional

def find_stutter_markers(profile: Profile) -> pd.DataFrame:
    """
    Scans all threads in a profile for common stutter-related markers.
    Returns a DataFrame with matched marker name, thread name, and time.
    """
    return extract_markers_by_name(profile, ["Jank", "VideoFallingBehind"])

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


def find_video_sink_dropped_frames(profile: Profile) -> pd.DataFrame:
    """
    Return all VideoSinkDroppedFrame markers from MediaDecoderStateMachine threads
    within 'Isolated Web Content' processes (media processes).

    Parameters:
    profile (Profile): Parsed profiler data.

    Returns:
    pd.DataFrame: Rows with marker name, thread name, process name, and time.
    """
    media_profile = extract_process(profile, name="Isolated Web Content")
    df = extract_markers_by_name(media_profile, ["VideoSinkDroppedFrame"])
    return df[df["threadName"] == "MediaDecoderStateMachine"].reset_index(drop=True)

def extract_markers_from_threads(profile: Profile, thread_names: list[str]) -> pd.DataFrame:
    """
    Extract all markers from threads whose name matches any in the given list.

    Parameters:
    profile (Profile): Parsed profiler data.
    thread_names (list[str]): Names of threads to extract markers from.

    Returns:
    pd.DataFrame: DataFrame of marker entries with thread name and process name.
    """
    collected = []

    for process in profile.processes.values():
        for thread in process.get("threads", []):
            if thread.get("name") not in thread_names:
                continue

            markers_df = thread.get("markers")
            if markers_df is None or markers_df.empty:
                continue

            if "name" not in markers_df or "startTime" not in markers_df:
                continue

            for _, row in markers_df.iterrows():
                collected.append({
                    "markerName": profile.string_table.get(row["name"], f"stringId:{row['name']}"),
                    "threadName": thread["name"],
                    "processName": thread.get("process_name", "unknown"),
                    "time": row["startTime"]
                })

    return pd.DataFrame(collected)

def crop_profile_by_time(profile: Profile, start: float, end: float) -> Profile:
    """
    Return a new Profile with all time-based thread data (e.g., markers, samples)
    cropped to the given time range.

    Parameters:
    profile (Profile): The original full profile.
    start (float): Start time (inclusive).
    end (float): End time (inclusive).

    Returns:
    Profile: A new Profile instance with all relevant thread data cropped.
    """
    cropped = deepcopy(profile)

    for process in cropped.processes.values():
        for thread in process.get("threads", []):
            for key, df in thread.items():
                if isinstance(df, pd.DataFrame) and "startTime" in df.columns:
                    mask = (df["startTime"] >= start) & (df["startTime"] <= end)
                    thread[key] = df[mask].reset_index(drop=True)

    return cropped

def extract_markers_by_name(profile: Profile, marker_names: list[str]) -> pd.DataFrame:
    """
    Extract all markers with names in the given list from all relevant threads.

    Parameters:
    profile (Profile): Parsed profiler data.
    marker_names (list[str]): Marker names to look for.

    Returns:
    pd.DataFrame: DataFrame of matching markers with thread and process metadata.
    """
    name_to_id = {
        idx: name for idx, name in profile.string_table.items()
        if name in marker_names
    }

    collected = []

    for process in profile.processes.values():
        for thread in process.get("threads", []):
            markers_df = thread.get("markers")
            if markers_df is None or markers_df.empty or "name" not in markers_df:
                continue

            mask = markers_df["name"].isin(name_to_id.keys())
            for _, row in markers_df[mask].iterrows():
                marker_id = row["name"]
                collected.append({
                    "markerName": name_to_id[marker_id],
                    "threadName": thread["name"],
                    "processName": thread.get("process_name", "unknown"),
                    "time": row.get("startTime")
                })

    return pd.DataFrame(collected)


def extract_process(profile: Profile, *, name: Optional[str] = None, pid: Optional[int] = None) -> Profile:
    if name is None and pid is None:
        raise ValueError("Either 'name' or 'pid' must be provided.")

    for candidate_pid, process in profile.processes.items():
        if pid is not None and candidate_pid == pid:
            result = deepcopy(profile)
            result.processes = {candidate_pid: deepcopy(process)}
            return result
        elif name is not None:
            # Match on process["name"]
            if process.get("name") == name:
                result = deepcopy(profile)
                result.processes = {candidate_pid: deepcopy(process)}
                return result
            # OR match based on any thread's `process_name`
            elif any(t.get("process_name") == name for t in process.get("threads", [])):
                result = deepcopy(profile)
                result.processes = {candidate_pid: deepcopy(process)}
                return result

    raise ValueError("No matching process found.")

def get_all_marker_names(profile: Profile) -> list[str]:
    return sorted(set(profile.string_table.tolist()))

def get_all_thread_names(profile: Profile) -> list[str]:
    names = {
        thread.get("name")
        for process in profile.processes.values()
        for thread in process.get("threads", [])
    }
    return sorted(name for name in names if name)

def get_cpu_usage_for_thread(thread: dict) -> pd.DataFrame:
    samples = thread.get("samples")
    if samples is None or samples.empty or "time" not in samples or "threadCPUDelta" not in samples:
        return pd.DataFrame()
    df = samples[["time", "threadCPUDelta"]].copy()
    return df
