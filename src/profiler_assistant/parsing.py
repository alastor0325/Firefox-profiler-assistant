# src/profiler_assistant/parsing.py

import orjson
import pandas as pd
from pathlib import Path
from typing import Any, Dict, List

class Profile:
    """
    A container class for storing parsed Profile data.
    It converts the raw parallel arrays into easy-to-use Pandas DataFrames.
    """
    def __init__(self, data: Dict[str, Any]):
        self.meta = data.get('meta', {})
        self.libs = data.get('libs',)
        
        # Convert the core "tables" into DataFrames for fast lookups
        self.string_table = pd.Series(data.get('stringTable',), name="string")
        self.frame_table = self._create_table_df(data, 'frameTable')
        self.stack_table = self._create_table_df(data, 'stackTable')

        # Process detailed data for each thread
        self.threads = self._process_threads(data.get('threads', []) or [])

    def _create_table_df(self, data: Dict[str, Any], table_name: str) -> pd.DataFrame:
        """A helper function to convert table data into a DataFrame."""
        table_data = data.get(table_name)
        # Check if table_data is a dictionary and has the required keys
        if isinstance(table_data, dict) and 'schema' in table_data and 'data' in table_data:
            return pd.DataFrame(table_data['data'], columns=table_data['schema'].keys())
        return pd.DataFrame()

    def _process_threads(self, threads_data: List) -> List:
        """Process all threads, converting their samples and markers into DataFrames."""
        processed_threads = []
        for i, thread_data in enumerate(threads_data):
            thread_name = thread_data.get('name', f'Thread {i}')
            thread_info = {
                'name': thread_name,
                'pid': thread_data.get('pid'),
                'tid': thread_data.get('tid'),
                'samples': self._create_table_df(thread_data, 'samples'),
                'markers': self._create_table_df(thread_data, 'markers')
            }
            processed_threads.append(thread_info)
        return processed_threads

    def __repr__(self) -> str:
        thread_count = len(self.threads)
        total_samples = sum(len(t['samples']) for t in self.threads)
        return f"<Profile with {thread_count} threads and {total_samples} total samples>"


def load_and_parse_profile(file_path: str) -> Profile:
    """
    Loads a Firefox Profiler JSON file from the given path,
    and parses it into a Profile object containing Pandas DataFrames.

    Args:
        file_path (str): The path to the profile.json file.

    Returns:
        Profile: An object containing all the parsed data.
    """
    print(f"[*] Loading profile from: {file_path}")
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Profile file not found at: {file_path}")

    raw_data = orjson.loads(path.read_bytes())
    
    print("[*] Parsing raw data into structured format...")
    profile = Profile(raw_data)
    print("[+] Parsing complete.")
    
    return profile