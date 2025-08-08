import json
from profiler_assistant.agent.prompts import SYSTEM_PROMPT
from profiler_assistant.agent.gemini_client import call_gemini_chat
from profiler_assistant.tools.base import TOOLS

ALLOWED_TOOLS = set(TOOLS.keys())

def describe_tools():
    return "\n".join([
        f"- {name}: {spec['description']} (args: {', '.join(spec['args'])})"
        for name, spec in TOOLS.items()
    ])

def run_react_agent(profile, question, history):
    # Step 1: Build prompt
    system_prompt = SYSTEM_PROMPT.format(tool_list=describe_tools())
    full_prompt = system_prompt + "\n\n"
    for h in history:
        full_prompt += f"{h['role'].capitalize()}: {h['content']}\n"
    full_prompt += f"User: {question}\n"

    # Step 2: Get first LLM response
    response = call_gemini_chat(full_prompt)

    if "Final Answer:" in response:
        return {"final": response}

    # Step 3: Try parsing Action and Action Input
    try:
        tool_name = next(line for line in response.splitlines() if line.startswith("Action:")).split(":", 1)[1].strip().strip("`")
        tool_input_json = next(line for line in response.splitlines() if line.startswith("Action Input:")).split(":", 1)[1].strip()
        tool_input = json.loads(tool_input_json)
    except Exception:
        # No valid tool call → retry with reminder
        full_prompt += "\nAssistant: Please follow the format using Action and Action Input.\n"
        response = call_gemini_chat(full_prompt)
        if "Final Answer:" in response:
            return {"final": response}
        return {"error": "⚠️ No tool call or Final Answer detected after retry."}

    # Step 4: Validate tool and args
    if tool_name not in ALLOWED_TOOLS:
        return {"error": f"❌ Tool '{tool_name}' is not recognized or allowed."}

    expected_args = set(TOOLS[tool_name]["args"])
    if not set(tool_input.keys()).issubset(expected_args):
        return {
            "error": f"❌ Invalid arguments for tool '{tool_name}'. Expected: {expected_args}, got: {set(tool_input.keys())}"
        }

    # Step 5: Execute tool and return result
    try:
        result = TOOLS[tool_name]["function"](profile, **tool_input)
        return {"tool_name": tool_name, "tool_result": result}
    except Exception as e:
        return {"error": f"Tool execution failed: {type(e).__name__}: {e}"}
