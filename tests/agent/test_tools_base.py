from profiler_assistant.tools import base

def test_tools_registry_structure():
    assert isinstance(base.TOOLS, dict)
    assert "find_video_sink_dropped_frames" in base.TOOLS

    for tool_name, spec in base.TOOLS.items():
        assert "function" in spec
        assert "description" in spec
        assert "args" in spec
