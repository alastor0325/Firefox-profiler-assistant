# src/profiler_assistant/analysis_tools.py

import pandas as pd
from.parsing import Profile

def find_stutter_markers(profile: Profile) -> pd.DataFrame:
    """
    Scans all threads in a profile for common stutter-related markers.

    Args:
        profile (Profile): The parsed profile object.

    Returns:
        pd.DataFrame: A DataFrame containing information about each found stutter
                      marker, including thread name, marker name, and time.
                      Returns an empty DataFrame if no markers are found.
    """
    # Define the marker names we want to extract
    stutter_marker_names = ["Jank", "VideoFallingBehind"]
    found_markers = []

    # Map string names to their index in the string table
    stutter_marker_indices = profile.string_table[
        profile.string_table.isin(stutter_marker_names)
    ].index.tolist()

    if not stutter_marker_indices:
        return pd.DataFrame()  # No relevant markers exist

    for thread_data in profile.threads:
        markers_df = thread_data['markers']
        if markers_df.empty or 'name' not in markers_df.columns:
            continue

        relevant_markers = markers_df[markers_df['name'].isin(stutter_marker_indices)].copy()

        if not relevant_markers.empty:
            relevant_markers['threadName'] = thread_data['name']
            relevant_markers['markerName'] = relevant_markers['name'].map(profile.string_table)
            found_markers.append(relevant_markers)

    if not found_markers:
        return pd.DataFrame()

    result_df = pd.concat(found_markers, ignore_index=True)
    return result_df[['threadName', 'markerName', 'time']]
