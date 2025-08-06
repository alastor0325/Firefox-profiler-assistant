import pytest
import json
from pathlib import Path
from profiler_assistant.parsing import load_and_parse_profile, Profile

@pytest.fixture
def sample_profile_file(tmp_path):
    """Creates a temporary sample profile.json file for testing."""
    profile_data = {
        "meta": {"product": "Firefox", "startTime": 1000, "endTime": 2000},
        "stringTable": ["js", "css"],
        "frameTable": {"schema": {"name": 0}, "data": []},
        "stackTable": {"schema": {"frame": 0, "prefix": 1}, "data": [[0, None]]},
        "threads": [
            {
                "name": "MediaThread",
                "pid": 1234,
                "tid": 10,
                "processName": "Isolated Web Content",
                "samples": {
                    "stack": [0, 1],
                    "timeDeltas": [10.1, 12.5],
                    "threadCPUDelta": [100, 200],
                    "eventDelay": [0, 1]
                },
                "markers": {
                    "name": [1, 0],
                    "startTime": [278001.123, 278005.987],
                    "endTime": [278002.123, 278006.001],
                    "phase": [2, 0],
                    "category": [1, 1],
                    "data": [{}, {}]
                }
            },
            {
                "name": "GeckoMain",
                "pid": 4321,
                "tid": 11,
                "processType": "webIsolated",
                "samples": {
                    "stack": [],
                    "timeDeltas": [],
                    "threadCPUDelta": [],
                    "eventDelay": []
                },
                "markers": {
                    "name": [],
                    "startTime": [],
                    "endTime": [],
                    "phase": [],
                    "category": [],
                    "data": []
                }
            },
            {
                "name": "NetworkingThread",  # <- does not match filter
                "pid": 5555,
                "tid": 12,
                "processName": "Networking Process",
                "samples": {
                    "stack": [0],
                    "timeDeltas": [5.0],
                    "threadCPUDelta": [50],
                    "eventDelay": [0]
                },
                "markers": {
                    "name": [0],
                    "startTime": [100000],
                    "endTime": [100001],
                    "phase": [0],
                    "category": [1],
                    "data": [{}]
                }
            }
        ]
    }

    file_path = tmp_path / "sample_profile.json"
    file_path.write_text(json.dumps(profile_data))
    return file_path

def test_load_and_parse_profile(sample_profile_file):
    """Tests loading and parsing a valid profile file."""
    profile = load_and_parse_profile(str(sample_profile_file))

    assert isinstance(profile, Profile)
    assert profile.meta['product'] == "Firefox"
    assert isinstance(profile.processes, dict)
    assert len(profile.processes) == 2  # 2 relevant PIDs: 1234 and 4321

    assert 1234 in profile.processes
    assert 4321 in profile.processes
    assert 5555 not in profile.processes  # <- filtered out

    p1 = profile.processes[1234]
    p2 = profile.processes[4321]

    assert p1['name'] == "Isolated Web Content"
    assert p2['name'] == "WEBISOLATED"

    media_thread = next(t for t in p1['threads'] if t['name'] == "MediaThread")
    assert len(media_thread['samples']) == 2
    assert len(media_thread['markers']) == 2

    assert 'stack' in media_thread['samples'].columns
    assert 'startTime' in media_thread['markers'].columns

def test_load_nonexistent_file():
    """Tests that a FileNotFoundError is raised for a missing file."""
    with pytest.raises(FileNotFoundError):
        load_and_parse_profile("nonexistent_file.json")
