from profiler_assistant.agent.react_agent import describe_tools

def test_describe_tools_output():
    output = describe_tools()
    assert isinstance(output, str)
    assert "extract_process" in output or "find_video_sink_dropped_frames" in output
