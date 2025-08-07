# tests/test_analysis_tools.py

import pandas as pd
import pytest
import json
from pathlib import Path
from profiler_assistant.parsing import Profile, load_and_parse_profile
from profiler_assistant.analysis_tools import (
    find_stutter_markers,
    find_media_playback_content_processes,
    find_rendering_process,
    find_video_sink_dropped_frames,
    extract_markers_from_threads,
    crop_profile_by_time,
)

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

def test_find_media_playback_content_processes():
    class MockProfile(Profile):
        def __init__(self):
            self.processes = {
                "0": {
                    "process_name": "Isolated Web Content",
                    "pid": 100,
                    "threads": [
                        {"name": "MediaDecoderStateMachine", "markers": ["marker1"]},
                        {"name": "OtherThread", "markers": []},
                    ]
                },
                "1": {
                    "process_name": "Isolated Web Content",
                    "pid": 101,
                    "threads": [
                        {"name": "MediaDecoderStateMachine", "markers": []}
                    ]
                },
                "2": {
                    "process_name": "Web Content",
                    "pid": 102,
                    "threads": [
                        {"name": "MediaDecoderStateMachine", "markers": ["marker2"]}
                    ]
                },
            }

    profile = MockProfile()
    result = find_media_playback_content_processes(profile)

    assert len(result) == 1
    assert result.iloc[0]["pid"] == 100

def test_find_rendering_process():
    class MockProfile(Profile):
        def __init__(self):
            self.processes = {
                "a": {
                    "process_name": "Web Content",
                    "pid": 200,
                    "threads": [
                        {"name": "Renderer", "markers": ["draw"]},
                        {"name": "Compositor", "markers": ["composite"]},
                    ]
                },
                "b": {
                    "process_name": "Web Content",
                    "pid": 201,
                    "threads": [
                        {"name": "Renderer", "markers": ["draw"]},
                    ]
                },
                "c": {
                    "process_name": "Web Content",
                    "pid": 202,
                    "threads": [
                        {"name": "Compositor", "markers": ["composite"]},
                    ]
                },
            }

    profile = MockProfile()
    result = find_rendering_process(profile)

    assert isinstance(result, pd.Series)
    assert result["pid"] == 200

def test_find_rendering_process_no_match():
    class MockProfile(Profile):
        def __init__(self):
            self.processes = {
                "x": {
                    "process_name": "Web Content",
                    "pid": 301,
                    "threads": [
                        {"name": "Renderer", "markers": ["draw"]},
                    ]
                },
                "y": {
                    "process_name": "Web Content",
                    "pid": 302,
                    "threads": [
                        {"name": "Compositor", "markers": ["composite"]},
                    ]
                },
            }

    profile = MockProfile()
    with pytest.raises(ValueError, match="No rendering process found"):
        find_rendering_process(profile)

def test_find_video_sink_dropped_frames():
    class MockProfile(Profile):
        def __init__(self):
            self.string_table = {
                0: "VideoSinkDroppedFrame",
                1: "OtherMarker"
            }
            self.processes = {
                "1": {
                    "process_name": "Isolated Web Content",
                    "pid": 10,
                    "threads": [
                        {
                            "name": "MediaDecoderStateMachine",
                            "process_name": "Isolated Web Content",
                            "markers": pd.DataFrame({
                                "name": [0, 1, 0],
                                "startTime": [10.5, 20.0, 30.25]
                            })
                        },
                        {
                            "name": "OtherThread",
                            "process_name": "Isolated Web Content",
                            "markers": pd.DataFrame()
                        }
                    ]
                },
                "2": {
                    "process_name": "Web Content",
                    "pid": 20,
                    "threads": [
                        {
                            "name": "MediaDecoderStateMachine",
                            "process_name": "Web Content",
                            "markers": pd.DataFrame({
                                "name": [0],
                                "startTime": [100.0]
                            })
                        }
                    ]
                }
            }

    profile = MockProfile()
    result = find_video_sink_dropped_frames(profile)

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 2
    assert all(result["markerName"] == "VideoSinkDroppedFrame")
    assert all(result["threadName"] == "MediaDecoderStateMachine")
    assert all(result["processName"] == "Isolated Web Content")
    assert set(result["time"]) == {10.5, 30.25}

def test_extract_markers_from_threads():
    class MockProfile(Profile):
        def __init__(self):
            self.string_table = {
                0: "MarkerA",
                1: "MarkerB"
            }
            self.processes = {
                "a": {
                    "process_name": "Web Content",
                    "threads": [
                        {
                            "name": "Decoder",
                            "process_name": "Web Content",
                            "markers": pd.DataFrame({
                                "name": [0, 1],
                                "startTime": [123.0, 456.0]
                            })
                        },
                        {
                            "name": "Compositor",
                            "process_name": "Web Content",
                            "markers": pd.DataFrame({
                                "name": [1],
                                "startTime": [789.0]
                            })
                        }
                    ]
                },
                "b": {
                    "process_name": "GPU",
                    "threads": [
                        {
                            "name": "Renderer",
                            "process_name": "GPU",
                            "markers": pd.DataFrame()
                        }
                    ]
                }
            }

    profile = MockProfile()
    result = extract_markers_from_threads(profile, ["Decoder", "Compositor"])

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 3
    assert set(result["markerName"]) == {"MarkerA", "MarkerB"}
    assert set(result["threadName"]) == {"Decoder", "Compositor"}
    assert set(result["processName"]) == {"Web Content"}
    assert set(result["time"]) == {123.0, 456.0, 789.0}

def test_crop_profile_by_time():
    class MockProfile(Profile):
        def __init__(self):
            self.string_table = {0: "MarkerA", 1: "MarkerB"}
            self.processes = {
                1: {
                    "name": "Web Content",
                    "threads": [
                        {
                            "name": "Compositor",
                            "process_name": "Web Content",
                            "markers": pd.DataFrame({
                                "name": [0, 1, 0],
                                "startTime": [100.0, 150.0, 300.0]
                            })
                        }
                    ]
                }
            }

    profile = MockProfile()
    cropped = crop_profile_by_time(profile, start=120.0, end=200.0)

    thread = cropped.processes[1]["threads"][0]
    markers = thread["markers"]

    assert len(markers) == 1
    assert markers.iloc[0]["startTime"] == 150.0
    assert profile.processes[1]["threads"][0]["markers"].shape[0] == 3  # original untouched
