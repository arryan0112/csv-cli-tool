import json
import re
from groq import Groq
from openai import OpenAI

from src.config.settings import settings
from src.agent.prompts import build_system_prompt
from src.agent.tools import get_tools_for_groq, TOOLS
from src.memory.session_store import (
    save_turn,
    save_tool_call,
    get_history,
)
from src.tools.csv_tool import (
    load_csv,
    get_schema,
    filter_rows,
    aggregate,
    get_sample,
)

# Conditional client initialization for Groq or OpenRouter
if settings.openrouter_api_key:
    client = OpenAI(
        api_key=settings.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1"
    )
    ACTIVE_MODEL = settings.openrouter_model if settings.openrouter_api_key else settings.model
else:
    client = Groq(api_key=settings.groq_api_key)
    ACTIVE_MODEL = settings.model


def _validate_tool_args(tool_name: str, args: dict) -> dict | None:
    """
    Validate tool arguments against the JSON schema.
    Returns an error dict if validation fails, None if valid.
    """
    # Find tool schema
    tool_schema = None
    for tool in TOOLS:
        if tool["name"] == tool_name:
            tool_schema = tool
            break
    
    if tool_schema is None:
        return {"error": f"Unknown tool: {tool_name}. Check available tools with /help."}
    
    params_schema = tool_schema.get("parameters", {})
    required = params_schema.get("required", [])
    properties = params_schema.get("properties", {})
    
    # Check required parameters
    for req_param in required:
        if req_param not in args:
            return {
                "error": f"Missing required parameter: '{req_param}'. Usage: {tool_name} {' '.join(f'<{p}>' for p in required)}",
                "tip": f"Use /help to see correct syntax for {tool_name}"
            }
    
    # Validate each provided argument
    for param_name, param_value in args.items():
        if param_name not in properties:
            continue  # Skip unknown params (could be extra)
        
        param_schema = properties[param_name]
        expected_type = param_schema.get("type")
        
        # Type validation
        if expected_type == "string":
            if not isinstance(param_value, str):
                return {
                    "error": f"Parameter '{param_name}' must be text, got {type(param_value).__name__}",
                    "tip": "Make sure to provide values in quotes or as plain text"
                }
            # Check minLength
            if "minLength" in param_schema and len(param_value) < param_schema["minLength"]:
                return {
                    "error": f"Parameter '{param_name}' is too short (min {param_schema['minLength']} characters)",
                    "tip": "Provide a longer value"
                }
            # Check pattern (regex) - use search to match anywhere in string
            if "pattern" in param_schema:
                pattern = param_schema["pattern"]
                if not re.search(pattern, param_value):
                    return {
                        "error": f"Parameter '{param_name}' format is invalid",
                        "tip": f"File path must end with .csv extension"
                    }
                
        elif expected_type == "integer":
            if not isinstance(param_value, int):
                # Try to convert from string
                if isinstance(param_value, str) and param_value.isdigit():
                    try:
                        args[param_name] = int(param_value)
                    except (ValueError, TypeError):
                        return {
                            "error": f"Parameter '{param_name}' must be a number",
                            "tip": "Use digits only, e.g., 5 or 10"
                        }
                else:
                    return {
                        "error": f"Parameter '{param_name}' must be a number",
                        "tip": "Use digits only, e.g., 5 or 10"
                    }
            # Check minimum
            if "minimum" in param_schema and param_value < param_schema["minimum"]:
                return {
                    "error": f"Parameter '{param_name}' must be at least {param_schema['minimum']}",
                    "tip": f"Value cannot be less than {param_schema['minimum']}"
                }
            # Check maximum
            if "maximum" in param_schema and param_value > param_schema["maximum"]:
                return {
                    "error": f"Parameter '{param_name}' must be at most {param_schema['maximum']}",
                    "tip": f"Value cannot exceed {param_schema['maximum']}"
                }
        
        # Enum validation
        if "enum" in param_schema:
            if param_value not in param_schema["enum"]:
                return {
                    "error": f"Parameter '{param_name}' must be one of: {', '.join(param_schema['enum'])}",
                    "tip": f"Allowed values: {', '.join(param_schema['enum'])}"
                }
    
    return None  # Validation passed


def run_agent(session_id: str, user_message: str) -> str:

    history = get_history(session_id)
    turn_number = len(history) + 1
    save_turn(session_id, "user", user_message, turn_number)

    system_prompt = build_system_prompt(session_id)
    messages = [{"role": "system", "content": system_prompt}]

    for msg in get_history(session_id):
        messages.append({
            "role": msg["role"],
            "content": msg["content"],
        })

    tools = get_tools_for_groq()

    # Track tools used in this message to prevent duplicate calls
    tools_used = set()
    last_tool_result = None
    duplicate_detected = False

    for turn in range(settings.max_turns):

        try:
            response = client.chat.completions.create(
                model=ACTIVE_MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.2,
                max_tokens=500,
            )
        except Exception:
            response = client.chat.completions.create(
                model=ACTIVE_MODEL,
                messages=messages,
                temperature=0.2,
                max_tokens=500,
            )

        message = response.choices[0].message

        if not message.tool_calls:
            final_text = message.content or "No response generated."
            save_turn(session_id, "assistant", final_text, turn_number)
            return final_text

        messages.append({
            "role": "assistant",
            "content": message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ],
        })

        # Process each tool call
        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name

            # Check if tool already used successfully in this message
            if tool_name in tools_used:
                duplicate_detected = True
                break

            try:
                tool_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({
                        "error": "Could not parse tool arguments. Please answer from conversation history instead."
                    }),
                })
                continue

            

            result = _execute_tool(tool_name, tool_args)

            save_tool_call(
                session_id=session_id,
                turn_number=turn_number,
                tool_name=tool_name,
                args=json.dumps(tool_args),
                result=json.dumps(result),
            )

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            })

            # If tool succeeded, mark as used
            if "error" not in result:
                tools_used.add(tool_name)
                last_tool_result = result

        if duplicate_detected:
            break

    # After loop
    if duplicate_detected:
        # Summarize last tool result
        if last_tool_result:
            if "rows_found" in last_tool_result:
                summary = f"Found {last_tool_result['rows_found']} rows."
            elif "result" in last_tool_result:
                summary = f"Result: {last_tool_result['result']}"
            elif "data" in last_tool_result:
                summary = f"Showing {len(last_tool_result['data'])} rows."
            elif "error" in last_tool_result:
                summary = f"Error: {last_tool_result['error']}"
            else:
                summary = "Tool completed."
        else:
            summary = "Tool already used."
        save_turn(session_id, "assistant", summary, turn_number)
        return summary

    fallback = "I reached the maximum number of steps. Please try a simpler question."
    save_turn(session_id, "assistant", fallback, turn_number)
    return fallback


def _execute_tool(tool_name: str, args: dict):
    try:
        # Validate arguments before execution
        validation_error = _validate_tool_args(tool_name, args)
        if validation_error:
            return validation_error
        
        # Auto-reload file if it's not in memory
        # This happens because /load command and agent run in the same process
        # but _dataframes can be empty if the file was loaded in a previous turn
        if tool_name in ("get_schema", "filter_rows", "aggregate", "get_sample"):
            file_path = args.get("file_path")
            if file_path:
                from src.tools.csv_tool import _dataframes
                if file_path not in _dataframes:
                    load_csv(file_path)

        if tool_name == "load_csv":
            return load_csv(args["file_path"])

        elif tool_name == "get_schema":
            return get_schema(args["file_path"])

        elif tool_name == "filter_rows":
            return filter_rows(
                args["file_path"],
                args["column"],
                args["operator"],
                args["value"],
            )

        elif tool_name == "aggregate":
            return aggregate(
                args["file_path"],
                args["column"],
                args["operation"],
            )

        elif tool_name == "get_sample":
            return get_sample(
                args["file_path"],
                args.get("n", 5),
            )

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    except KeyError as e:
        return {"error": f"Missing required argument: {e}"}
    except Exception as e:
        return {"error": f"Tool execution failed: {str(e)}"}
