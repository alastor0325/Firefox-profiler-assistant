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
                "markers": {
                    "schema": {"name": 0, "time": 1},
                    "data": [
                        [0, 150.0],  # OtherMarker
                        [1, 250.5]   # Jank
                    ]
                },
            },
            {
                "name": "MediaDecoder",
                "markers": {
                    "schema": {"name": 0, "time": 1},
                    "data": [
                        [2, 300.1],  # VideoFallingBehind
                        [2, 450.8]
                    ]
                }
            },
            {
                "name": "GeckoMain",
                "markers": {
                    "schema": {"name": 0, "time": 1},
                    "data": [[0, 100.0]]
                }
            }
        ],
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