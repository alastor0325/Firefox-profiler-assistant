# tests/test_analysis_tools.py

import pytest
import json
from pathlib import Path
from profiler_assistant.parsing import load_and_parse_profile
from profiler_assistant.analysis_tools import find_stutter_markers

@pytest.fixture
def stutter_profile_file(tmp_path):
    """Creates a temporary profile.json file that contains stutter markers."""
    profile_data = {
        "meta": {},
        "stringTable": ["OtherMarker", "Jank", "VideoFallingBehind"],
        "threads": [
            {
                "name": "Compositor",
                "pid": 1,
                "tid": 11,
                "processName": "GPU",
                "markers": {
                    "name": [0, 1],  # OtherMarker, Jank
                    "startTime": [150.0, 250.5],
                    "endTime": [150.5, 251.0],
                    "phase": [0, 0],
                    "category": [1, 1],
                    "data": [{}, {}]
                }
            },
            {
                "name": "MediaDecoder",
                "pid": 1,
                "tid": 12,
                "processName": "GPU",
                "markers": {
                    "name": [2, 2],  # VideoFallingBehind
                    "startTime": [300.1, 450.8],
                    "endTime": [300.2, 451.0],
                    "phase": [0, 0],
                    "category": [1, 1],
                    "data": [{}, {}]
                }
            },
            {
                "name": "GeckoMain",
                "pid": 2,
                "tid": 13,
                "processName": "WEB",
                "markers": {
                    "name": [0],  # OtherMarker
                    "startTime": [100.0],
                    "endTime": [101.0],
                    "phase": [0],
                    "category": [1],
                    "data": [{}]
                }
            }
        ]
    }
    file_path = tmp_path / "stutter_profile.json"
    file_path.write_text(json.dumps(profile_data))
    return file_path

def test_find_stutter_markers(stutter_profile_file):
    """
    Tests that the find_stutter_markers function correctly identifies
    and extracts Jank and VideoFallingBehind markers.
    """
    profile = load_and_parse_profile(str(stutter_profile_file))
    stutter_events = find_stutter_markers(profile)

    assert not stutter_events.empty
    assert len(stutter_events) == 3

    # Check that the correct marker names were found
    assert "Jank" in stutter_events['markerName'].values
    assert "VideoFallingBehind" in stutter_events['markerName'].values

    # Check that the thread names are correct
    assert "Compositor" in stutter_events['threadName'].values
    assert "MediaDecoder" in stutter_events['threadName'].values

    # Check that the times are correct
    assert 250.5 in stutter_events['time'].values
    assert 300.1 in stutter_events['time'].values
    assert 450.8 in stutter_events['time'].values