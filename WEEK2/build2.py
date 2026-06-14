import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)
MODEL = "openrouter/owl-alpha"
# ---------------------------------------------------------------------------
# Tool schemas (the contract between you and the model)
# ---------------------------------------------------------------------------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": (
                "Returns the current weather for a given city. "
                "Call this whenever the user asks about weather, temperature, or climate. "
                "Do not guess weather. Always call this tool."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "The city name, e.g. 'Delhi' or 'San Francisco'",
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "Temperature unit. Default to celsius.",
                    },
                },
                "required": ["city","unit"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": (
                "Evaluates a mathematical expression and returns the result. "
                "Use this for any arithmetic the user asks about. "
                "Pass the expression as a string, e.g. '1337 * 42 + 7'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "A Python arithmetic expression, e.g. '100 / 4 + 3'",
                    }
                },
                "required": ["expression"],
            },
        },
    },
]
# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------
def get_weather(city, unit):
        if(unit=="celsius"):
            if(city== "Delhi"):
                return {"city": city, "temperature": 28, "unit": unit, "condition": "partly cloudy"}
            else:
                return {"city": city, "temperature": 34, "unit": unit, "condition": "sunny"}
        elif(unit=="fahrenheit"):
            if(city== "Delhi"):
                return {"city": city, "temperature": 82.4, "unit": unit, "condition": "partly cloudy"}
            else:
                return {"city": city, "temperature": 93.2, "unit": unit, "condition": "sunny"}
            
def calculate(expression):
     try:
          soln = eval(expression,{"__builtins__":{}},{})
          return {"result": soln}
     except:
          return {"error": "cannot do this calculation"}
# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------
TOOL_REGISTRY = {
    "get_weather": get_weather,
    "calculate": calculate,}

def dispatch(tool_call):
    """
    Execute a single tool_call object from the API response.

    tool_call has:
        tool_call.function.name       (the tool name)
        tool_call.function.arguments  (a JSON string of arguments)

    Return a JSON string of the result dict.
    On unknown tool or exception, return a JSON error dict.

    Note: tool_call.function.arguments is a *string*, not a dict. Parse it first.
    """
    name = tool_call.function.name
    ar = tool_call.function.arguments
    arg = json.loads(ar)
    func_run = TOOL_REGISTRY[name](**arg)
    return(json.dumps(func_run))
# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------
MAX_ITERATIONS = 8

def run_agent(user_message):
    messages = [
        {"role": "system", "content": "You are a helpful assistant. Use tools when appropriate."},
        {"role": "user", "content": user_message},]

    for _ in range(MAX_ITERATIONS):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,)
        reply = response.choices[0].message
        finish_reason = response.choices[0].finish_reason
        if finish_reason == "tool_calls":
            tool_call = reply.tool_calls[0]
            messages.append(reply)
            func_reply = dispatch(tool_call)
            messages.append({"role":"tool", "tool_call_id":tool_call.id, "content":func_reply})
        else:
            reply = response.choices[0].message.content
            messages.append({"role":"assistant", "content":reply})
            return reply

    return f"[Agent stopped after {MAX_ITERATIONS} iterations without a final answer]"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_queries = [
        "What's the weather in Tokyo?",
        "Calculate: (2**10) - 1",
    ]

    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print(f"{'='*60}")
        result = run_agent(query)
        print(f"\nFinal answer:\n{result}")