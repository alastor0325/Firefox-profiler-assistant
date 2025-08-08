import json
from profiler_assistant.agent.prompts import SYSTEM_PROMPT
from profiler_assistant.agent.gemini_client import call_gemini_chat
from profiler_assistant.tools.base import TOOLS

def describe_tools():
    return "\n".join([
        f"- {name}: {spec['description']} (args: {', '.join(spec['args'])})"
        for name, spec in TOOLS.items()
    ])

def run_react_agent(profile, question, history):
    system_prompt = SYSTEM_PROMPT.format(tool_list=describe_tools())
    full_prompt = system_prompt + "\n\n"
    for h in history:
        full_prompt += f"{h['role'].capitalize()}: {h['content']}\n"
    full_prompt += f"User: {question}\n"

    response = call_gemini_chat(full_prompt)

    if "Final Answer:" in response:
        return {"final": response}

    try:
        tool_name = next(line for line in response.splitlines() if line.startswith("Action:")).split(":")[1].strip()
        tool_input_json = next(line for line in response.splitlines() if line.startswith("Action Input:")).split(":", 1)[1].strip()
        tool_input = json.loads(tool_input_json)
    except Exception as e:
        return {"error": f"Failed to parse tool call: {e}"}

    if tool_name not in TOOLS:
        return {"error": f"Unknown tool: {tool_name}"}

    try:
        result = TOOLS[tool_name]["function"](profile, **tool_input)
        return {"tool_name": tool_name, "tool_result": result}
    except Exception as e:
        return {"error": f"Tool execution failed: {type(e).__name__}: {e}"}
