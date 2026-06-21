import os
import sys
import json
from openai import OpenAI
from dotenv import load_dotenv
import uuid
from tools.files import read_file, write_file, edit_file, list_files
from tools.web import web_search, web_fetch
from tools.papers import paper_search, read_paper
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))
def now_ist():
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)

MODEL = "openai/gpt-oss-120b:free"
MAX_ITERATIONS = 10

SESSIONS_DIR = os.path.join(os.path.dirname(__file__), ".agent", "sessions")
AGENTS_PATHS = ("AGENTS.md", ".agent/AGENTS.md")
BASE_PROMPT = "You are Research Desk, a helpful research assistant."

def create_session() -> str:
    """Return a new 8-char hex session ID."""
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    return uuid.uuid4().hex[:8]

def save_session(session_id: str, messages: list, title: str = "Untitled") -> None:
    """Write session JSON to .agent/sessions/{id}.json"""
    path = f"{SESSIONS_DIR}/{session_id}.json"
    if os.path.exists(path):
        with open(path) as f:
            existing = json.load(f)
        created_at = existing["created_at"]
    else:
        created_at = now_ist()

    data = {
        "id": session_id,
        "title": title,
        "created_at": created_at,
        "updated_at": now_ist(),
        "messages": messages
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load_session(session_id: str) -> dict:
    """Load and return session dict including messages list."""
    path = f"{SESSIONS_DIR}/{session_id}.json"
    with open(path) as f:
            existing = json.load(f)
    return existing

def list_sessions() -> list[dict]:
    """Return sessions sorted by updated_at descending."""
    sessions = []
    for filename in os.listdir(SESSIONS_DIR):
        path = f"{SESSIONS_DIR}/{filename}"
        with open(path) as f:
            data = json.load(f)
        sessions.append({
            "id": data["id"],
            "title": data["title"],
            "updated_at": data["updated_at"]
        })
    return sorted(sessions, key=lambda s: s["updated_at"], reverse=True)

def build_system_prompt() -> str:
    """Base prompt + AGENTS.md if it exists."""
    prompt = BASE_PROMPT
    for path in AGENTS_PATHS:
        if os.path.isfile(path):
            with open(path) as f:
                rules = f.read()
            prompt = prompt + "\n\n## Project rules\n" + rules
            break
    return prompt

TOOL_REGISTRY = {
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "list_files": list_files,
    "web_search": web_search,
    "web_fetch": web_fetch,
    "paper_search": paper_search,
    "read_paper": read_paper,
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for current information. Use this for news, blogs, "
                "docs, and anything not related to academic papers. "
                "Returns a list of search results with titles, URLs, and snippets."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query. Be specific and targeted.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": (
                "Fetch and read the full content of a web page. Use this after web_search "
                "to read a specific result in detail, or to fetch an arXiv page if "
                "read_paper fails."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The full URL to fetch, including https://",
                    }
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "paper_search",
            "description": (
                "Search for academic/ML research papers indexed on Hugging Face Papers. "
                "Use this for questions about research papers, methods, or ML literature. "
                "Returns a list of papers with id, title, and snippet. Call read_paper "
                "next to get full content."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query describing the paper or topic, e.g. 'FlashAttention' or 'RLHF'.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_paper",
            "description": (
                "Read the full content of a research paper by arxiv ID or URL. "
                "Use this after paper_search to get the actual paper text. "
                "Falls back to the abstract if full markdown isn't available."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "arXiv ID (e.g. '2205.14135') or full arXiv/HF URL.",
                    }
                },
                "required": ["url"],
            },
        },
    },
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
                    "path": {
                        "type": "string",
                        "description": "Path to the file, relative to workspace root.",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "First line to read (1-indexed). Default 1.",
                    },
                    "read_lines": {
                        "type": "integer",
                        "description": "Number of lines to read. Default 200.",
                    },
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
                    "path": {
                        "type": "string",
                        "description": "Path to the file, relative to workspace root.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file.",
                    },
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
                    "operation": {
                        "type": "string",
                        "enum": ["replace", "delete", "append"],
                    },
                    "start_line": {"type": "integer"},
                    "end_line": {
                        "type": "integer",
                        "description": "Required for replace/delete.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Required for replace/append.",
                    },
                },
                "required": ["path", "operation", "start_line"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": (
                "List files in a folder matching a glob pattern. Use before read_file "
                "to explore unknown directories."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Folder to list. Default current directory.",
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern, e.g. '*.md'. Default '*'.",
                    },
                },
                "required": [],
            },
        },
    },
]

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
        self.messages.append({"role":"user", "content":user_message})
        answer = self._run_loop()
        save_session(self.session_id, self.messages)
        return answer

    def run_once(self, prompt: str) -> str:
        return self.chat(prompt)

    def _run_loop(self) -> str:
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
    session_id = None
    args = sys.argv[1:]

    if "--session" in args:
        idx = args.index("--session")
        session_id = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    if "--tui" in args:
        from tui import ResearchDeskApp
        ResearchDeskApp(session_id=session_id).run()
        return

    agent = REPLAgent(session_id=session_id)
    if args:
        print(agent.run_once(" ".join(args)))
        return
    agent.run()


if __name__ == "__main__":
    main()