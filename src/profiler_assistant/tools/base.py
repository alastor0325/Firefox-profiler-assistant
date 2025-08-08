from profiler_assistant.analysis_tools import (
    extract_process,
    extract_markers_by_name,
    find_video_sink_dropped_frames,
    get_all_thread_names,
    get_all_marker_names,
    get_cpu_usage_for_thread,
)

TOOLS = {
    "extract_process": {
        "function": extract_process,
        "description": "Extract a process by name or pid",
        "args": ["name", "pid"]
    },
    "find_video_sink_dropped_frames": {
        "function": find_video_sink_dropped_frames,
        "description": "Find dropped frames on MediaDecoder thread",
        "args": []
    },
    "get_all_thread_names": {
        "function": get_all_thread_names,
        "description": "List all thread names in the profile",
        "args": []
    },
    "get_all_marker_names": {
        "function": get_all_marker_names,
        "description": "List all marker names in the profile",
        "args": []
    },
    "extract_markers_by_name": {
        "function": extract_markers_by_name,
        "description": "Extract specific markers by name",
        "args": ["marker_names"]
    },
}
