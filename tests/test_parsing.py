# tests/test_parsing.py

import pytest
import json
from pathlib import Path
from profiler_assistant.parsing import load_and_parse_profile, Profile

@pytest.fixture
def sample_profile_file(tmp_path):
    """Creates a temporary sample profile.json file for testing."""
    # FIX: Provide a minimal but valid 'threads' list
    profile_data = {
        "meta": {"product": "Firefox", "startTime": 1000, "endTime": 2000},
        "stringTable": ["string1", "string2"],
        "threads": [
            {
                "name": "MainThread",
                "samples": {
                    "schema": {"time": 0, "category": 1},
                    "data": [
                        [100, "js"],
                        [200, "css"]
                    ]
                },
                "markers": {
                    "schema": {"name": 0},
                    "data": []
                }
            }
        ],
        "frameTable": {"schema": {"name": 0}, "data": []},
        "stackTable": {"schema": {"frame": 0, "prefix": 1}, "data": [[0, None]]}
    }
    file_path = tmp_path / "sample_profile.json"
    file_path.write_text(json.dumps(profile_data))
    return file_path

def test_load_and_parse_profile(sample_profile_file):
    """Tests loading and parsing a valid profile file."""
    profile = load_and_parse_profile(str(sample_profile_file))

    assert isinstance(profile, Profile)
    assert profile.meta['product'] == "Firefox"
    assert len(profile.threads) == 1

    # Find the thread named "MainThread"
    main_thread = next(t for t in profile.threads if t['name'] == "MainThread")

    assert main_thread['name'] == "MainThread"
    assert len(main_thread['samples']) == 2
    assert 'time' in main_thread['samples'].columns

def test_load_nonexistent_file():
    """Tests that a FileNotFoundError is raised for a missing file."""
    with pytest.raises(FileNotFoundError):
        load_and_parse_profile("nonexistent_file.json")