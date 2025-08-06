import orjson
import pandas as pd
from pathlib import Path
from typing import Any, Dict, List
from collections import defaultdict

# Thread name filters (case-insensitive)
MEDIA_GFX_THREAD_PATTERNS = [
    "Media", "GeckoMain", "cubeb", "audio", "gmp", "Renderer", "Compositor",
]
MEDIA_GFX_THREAD_PATTERNS_LOWER = [p.lower() for p in MEDIA_GFX_THREAD_PATTERNS]


class Profile:
    """
    A container class for storing parsed Profile data.
    It filters for relevant threads and groups them by process.
    """

    def __init__(self, data: Dict[str, Any]):
        self.meta = data.get("meta", {})
        self.libs = data.get("libs")

        # Convert tables to DataFrames
        self.string_table = pd.Series(data.get("stringTable"), name="string")
        self.frame_table = self._create_table_df(data, "frameTable")
        self.stack_table = self._create_table_df(data, "stackTable")

        # Process and group threads
        self.processes = self._process_and_group_threads(data.get("threads") or [])

    def _create_table_df(self, data: Dict[str, Any], table_name: str) -> pd.DataFrame:
        table_data = data.get(table_name)
        if isinstance(table_data, dict) and "schema" in table_data and "data" in table_data:
            return pd.DataFrame(table_data["data"], columns=table_data["schema"].keys())
        return pd.DataFrame()

    def _is_relevant_thread(self, thread_name: str) -> bool:
        return any(thread_name.lower().startswith(p) for p in MEDIA_GFX_THREAD_PATTERNS_LOWER)

    def _process_and_group_threads(self, threads_data: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
        """
        Filters for media/gfx threads, adds process name to thread,
        and groups threads by PID.
        """
        threads_by_pid = defaultdict(list)

        for thread_data in threads_data:
            thread_name = thread_data.get("name", "")
            if thread_name and self._is_relevant_thread(thread_name):
                pid = thread_data.get("pid")
                if pid is None:
                    continue

                process_name = (
                    thread_data.get("processName")
                    or (thread_data.get("processType") or "").upper()
                    or "Unknown Process"
                )
                thread_info = {
                    "name": thread_name,
                    "pid": pid,
                    "tid": thread_data.get("tid"),
                    "process_name": process_name,
                    "samples": self._create_table_df(thread_data, "samples"),
                    "markers": self._create_table_df(thread_data, "markers"),
                }

                threads_by_pid[pid].append(thread_info)

        # Final structure with per-process info
        processes = {}
        for pid, threads in threads_by_pid.items():
            process_name = threads[0].get("process_name", "Unknown Process")
            processes[pid] = {
                "name": process_name,
                "threads": threads,
            }

        return processes

    def __repr__(self) -> str:
        process_count = len(self.processes)
        thread_count = sum(len(p["threads"]) for p in self.processes.values())
        return f"<Profile with {process_count} processes and {thread_count} relevant threads>"


def load_and_parse_profile(file_path: str) -> Profile:
    """
    Loads a Firefox Profiler JSON file and parses it into a Profile object.
    """
    print(f"[*] Loading profile from: {file_path}")
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Profile file not found at: {file_path}")

    raw_data = orjson.loads(path.read_bytes())

    print("[*] Parsing and filtering raw data...")
    profile = Profile(raw_data)
    print("[+] Parsing complete.")

    return profile
