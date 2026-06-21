"""
Build 2: Agent + REPLAgent
===========================
Agent = brain (loop, tools, sessions). REPLAgent = terminal UI.

Before running:
  mkdir -p notes

Tasks:
  1. Agent — chat(), run_once(), _run_loop(), dispatch(), _emit(), session I/O
  2. REPLAgent(Agent) — run() interactive loop
  3. resolve_path, read_file, write_file, list_files, edit_file
  4. main() — one-shot: python build2_agent_class.py "hello"

TUIAgent comes in the project (tui.py). No Textual imports here.
"""

import os
import sys
import json
import glob as glob_module
from openai import OpenAI
from dotenv import load_dotenv
from build1 import create_session, load_session, save_session, build_system_prompt

load_dotenv()

MAX_ITERATIONS = 10
MAX_READ_CHARS = 12_000

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)
MODEL = "openai/gpt-oss-120b:free"
WORKSPACE_ROOT = os.path.abspath(os.environ.get("WORKSPACE_ROOT", "."))

# --- File tools ---

def resolve_path(path: str) -> str:
    full = os.path.abspath(os.path.join(WORKSPACE_ROOT, path))
    if full.startswith(WORKSPACE_ROOT):
        return full
    else:
        raise ValueError("Path escapes workspace")

def read_file(path, start_line=1, read_lines=200):
    full = resolve_path(path)
    try:
        with open(full, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        return {"error": str(e)}

    total = len(lines)
    window = lines[start_line-1 : start_line-1+read_lines]
    numbered = [f"{i+start_line:5}| {line}" for i, line in enumerate(window)]
    content = "".join(numbered)

    if len(content) > MAX_READ_CHARS:
        content = content[:MAX_READ_CHARS] + "\n[...truncated]"

    return {
        "content": content,
        "path": path,
        "total_lines": total,
        "has_more": (start_line - 1 + read_lines) < total
    }


def write_file(path: str, content: str) -> dict:
    full = resolve_path(path)
    try:
        file = open(full,"w",encoding = "utf-8")
        data = file.write(content)
        return {"success":True, "path":path, "Bytes":len(content)}
    except Exception as e:
        return{"error": str(e)}


def edit_file(
    path: str,
    operation: str,
    start_line: int,
    end_line: int | None = None,
    content: str | None = None,
) -> dict:
    full = resolve_path(path)
    try:
        with open(full, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        return {"error": str(e)}

    if operation == "replace":
        old_lines = lines[start_line-1 : end_line]
        new_lines = [l + "\n" for l in content.split("\n")]
        lines[start_line-1 : end_line] = new_lines

    elif operation == "delete":
        old_lines = lines[start_line-1 : end_line]
        del lines[start_line-1 : end_line]

    elif operation == "append":
        old_lines = []
        new_lines = [l + "\n" for l in content.split("\n")]
        lines[start_line:start_line] = new_lines

    else:
        return {"error": f"unknown operation: {operation}"}

    try:
        with open(full, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except Exception as e:
        return {"error": str(e)}

    return {
        "operation": operation,
        "removed": "".join(old_lines),
        "added": content,
        "path": path,
        "task": "completed"
    }

def list_files(path=".", pattern="*"):
    full = resolve_path(path)
    matches = glob_module.glob(os.path.join(full, pattern))
    relative = [os.path.relpath(m, WORKSPACE_ROOT) for m in matches]
    return {"files": relative}


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a file's content with line numbers. Supports pagination via "
                "start_line and read_lines. Check has_more in the response to see "
                "if there's more content beyond what was returned."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file, relative to workspace root."},
                    "start_line": {"type": "integer", "description": "First line to read (1-indexed). Default 1."},
                    "read_lines": {"type": "integer", "description": "Number of lines to read. Default 200."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create a new file or overwrite an existing file with content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file, relative to workspace root."},
                    "content": {"type": "string", "description": "Content to write to the file."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": (
                "Edit specific lines of an existing file. Always read_file first to get "
                "correct line numbers before editing. Supports replace, delete, and append."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "operation": {"type": "string", "enum": ["replace", "delete", "append"]},
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer", "description": "Required for replace/delete."},
                    "content": {"type": "string", "description": "Required for replace/append."},
                },
                "required": ["path", "operation", "start_line"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a folder matching a glob pattern. Use before read_file to explore unknown directories.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Folder to list. Default current directory."},
                    "pattern": {"type": "string", "description": "Glob pattern, e.g. '*.md'. Default '*'."},
                },
                "required": [],
            },
        },
    },
]

TOOL_REGISTRY = {
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "list_files": list_files,
}

class Agent:
    """Core agent: loop, tools, sessions. No UI."""

    def __init__(self, workspace: str = ".", session_id: str | None = None):
        self.workspace = os.path.abspath(workspace)
        if session_id:
            session = load_session(session_id)
            self.session_id = session_id
            self.messages = session["messages"]
        else:
            self.session_id = create_session()
            self.messages = [{"role": "system", "content": build_system_prompt()}]

    def chat(self, user_message: str) -> str:
        # TODO: append user msg, _run_loop(), save session, return answer
        self.messages.append({"role":"user", "content":user_message})
        answer = self._run_loop()
        save_session(self.session_id, self.messages)
        return answer

    def run_once(self, prompt: str) -> str:
        return self.chat(prompt)

    def _run_loop(self) -> str:
        # TODO: agent loop — call self.dispatch(), self._emit() on tool calls
        for _ in range(MAX_ITERATIONS):
            response = client.chat.completions.create(
                model=MODEL,
                messages=self.messages,
                tools=TOOLS,)
            if response is None or response.choices is None:
                return "[No response from model]"
            reply = response.choices[0].message
            finish_reason = response.choices[0].finish_reason
            if finish_reason == "tool_calls":
                tool_call = reply.tool_calls[0]
                self.messages.append(reply.model_dump())
                self._emit("tool_call", name=tool_call.function.name)
                func_reply = self.dispatch(tool_call)
                self.messages.append({"role":"tool", "tool_call_id":tool_call.id, "content":func_reply})
            else:
                reply = response.choices[0].message.content
                self.messages.append({"role":"assistant", "content":reply})
                return reply
            
        return f"[Agent stopped after {MAX_ITERATIONS} iterations without a final answer]"


    def dispatch(self, tool_call) -> str:
        # TODO: route to file tools, return JSON string
        name = tool_call.function.name
        ar = tool_call.function.arguments
        arg = json.loads(ar)
        if name not in TOOL_REGISTRY:
            return json.dumps({"error": f"unknown tool: {name}"})
        func_run = TOOL_REGISTRY[name](**arg)
        return json.dumps(func_run)

    def _emit(self, event: str, **data) -> None:
        """Override in REPLAgent/TUIAgent for tool logging."""
        pass


class REPLAgent(Agent):
    """Terminal REPL + one-shot CLI."""

    def run(self) -> None:
        print(f"Research Desk [{self.session_id}] — /quit to exit")
        while True:
            try:
                user_input = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not user_input or user_input in ("quit", "exit"):
                break
            print(self.chat(user_input))
            print()

    def _emit(self, event: str, **data) -> None:
        if event == "tool_call":
            print(f"  [tool] {data.get('name')}", file=sys.stderr)


def main():
    agent = REPLAgent()
    if len(sys.argv) > 1:
        print(agent.run_once(" ".join(sys.argv[1:])))
        return
    agent.run()


if __name__ == "__main__":
    main()