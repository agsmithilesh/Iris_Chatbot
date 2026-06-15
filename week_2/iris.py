import os
import requests
import trafilatura
import json
import asyncio
from openai import OpenAI
from dotenv import load_dotenv
import httpx
from mcp import ClientSession
from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, Input, RichLog
from textual.containers import Vertical

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],)

TOKEN_FILE = ".alphaxiv_tokens.json"
MODEL = "openai/gpt-oss-120b:free"
SERPER_API_KEY = os.environ["SERPER_API_KEY"]
MAX_CHARS = 800
MCP_SERVER_URL = "https://api.alphaxiv.org/mcp/v1"
REDIRECT_URI = "http://localhost:8765/callback"

class FileTokenStorage(TokenStorage):
    def __init__(self):
        self.tokens: OAuthToken | None = None
        self.client_info: OAuthClientInformationFull | None = None
        if os.path.exists(TOKEN_FILE):
            try:
                data = json.loads(open(TOKEN_FILE).read())
                if data.get("tokens"):
                    self.tokens = OAuthToken(**data["tokens"])
                if data.get("client_info"):
                    self.client_info = OAuthClientInformationFull(**data["client_info"])
            except Exception:
                pass

    def _save(self):
        # mode="json" converts Pydantic types like AnyUrl to plain strings
        data = {}
        if self.tokens:
            data["tokens"] = self.tokens.model_dump(mode="json")
        if self.client_info:
            data["client_info"] = self.client_info.model_dump(mode="json")
        open(TOKEN_FILE, "w").write(json.dumps(data, indent=2))

    async def get_tokens(self) -> OAuthToken | None:
        return self.tokens

    async def set_tokens(self, tokens: OAuthToken) -> None:
        self.tokens = tokens
        self._save()

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        return self.client_info

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        self.client_info = client_info
        self._save()

# ---------------------------------------------------------------------------
# Tool schemas (the contract between you and the model)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",     # WEB_SEARCH
            "description": (
                "Search the web for current information. Use this when the user asks "
                "about recent events, specific facts, or anything you are uncertain about. "
                "Returns a list of search results with titles, URLs, and snippets."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query. Be specific and targeted.",}},
                        "required": ["query"],},},},
    {
        "type": "function",
        "function": {
            "name": "read_file",     # READ FILE
            "description": (
                "reads a file from disk and returns its content"
                "Returns a dictionary in the format {'content':..., 'path'...:}"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "tells the exact file to read from",}},
                        "required": ["path"],},},},
    {
        "type": "function",
        "function": {
            "name": "write_file",     # WRITE FILE
            "description": (
                "writes content to a file on disk"
                "Whenever asked to write something in a file or create a new file, STRICTLY USE WRITE_FILE TOOL."
                "Returns a dictionary in the format {'success':..., 'path':..., 'bytes':...}"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "tells the exact file to read from"},
                    "content":{
                        "type": "string",
                        "description": "the content what to write in the file"}},
                        "required": ["path","content"],},},},
    {
        "type": "function",
        "function": {
            "name": "web_fetch",    # WEB_FETCH
            "description": (
                "Fetch and read the full content of a web page. Use this after web_search "
                "to read a specific result in detail."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The full URL to fetch, including https://",}},
                        "required": ["url"],},},},]
def web_search(query):
    try:
        response = requests.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
        json={"q": query, "num":5},
        timeout=10,)
        response.raise_for_status()    # WEB SEARCH
        data = response.json()
        results = []
        for item in data.get("organic", []):
            results.append({
                            "title": item.get("title", ""),
                            "link": item.get("link", ""),
                            "snippet": item.get("snippet", ""),})
        return results
    except Exception as e:
            return {"error": f"could not fetch the page {str(e)}"}
    
def read_file(path):
    try:
        file = open(path,"r",encoding="utf-8")
        data = file.read()    # READ FILE
        return {"content":data, "path" : path}
    except:
        return {"error": "The file can't be read"}

def write_file(path , content):
    try:
        file = open(path,"w",encoding="utf-8")    # WRITE FILE
        file.write(content)
        return {"success":True, "path":path, "Bytes":len(content)}
    except Exception as e:
        return{"error": f"Unable to write to the file due to {str(e)}"}
    
def web_fetch(url):
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"}
    response = requests.get(url, headers=headers,timeout=10)    # WEB FETCH
    response.raise_for_status()
    return response.text

def fetch_clean(url):
    html = web_fetch(url)
    text = trafilatura.extract(html, include_comments=False, include_tables=True)
    return text or ""

def fetch_limit(url):
    text = fetch_clean(url)
    if(len(text))>=MAX_CHARS:
        text = text[:MAX_CHARS]
    return(text)
# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

async def open_browser(auth_url: str) -> None:
    import webbrowser
    webbrowser.open(auth_url)

async def wait_for_callback():
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import parse_qs, urlparse
    code = state = None
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal code, state
            params = parse_qs(urlparse(self.path).query)
            code = params.get("code", [None])[0]
            state = params.get("state", [None])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h1>Authorized. Close this tab.</h1>")
        def log_message(self, *args): pass
    server = HTTPServer(("localhost", 8765), Handler)
    server.timeout = 120
    server.handle_request()
    server.server_close()
    return code, state

# ---------------------------------------------------------------------------
# TUI
# ---------------------------------------------------------------------------

class ChatApp(App):
    """A full-screen terminal chatbot."""

    TITLE = "IRIS"
    CSS = """
    Screen {
        layout: vertical;
    }

    RichLog {
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
    }

    Input {
        dock: bottom;
        height: 5;
    }
    """

    BINDINGS = [
        Binding("ctrl+shift+d", "clear_display", "Clear display"),
        Binding("ctrl+shift+h", "clear_history", "Clear history"),
        Binding("ctrl+shift+q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.messages: list[dict] = [
            {"role": "system", "content": "You are a helpful assistant." "Use tools when appropriate."
                        "For finding research papers, always use discover_papers tool, not web_search."
                        "If user has asked about research papers, do not do web_search. Use discover_papers and get_paper_content. get_paper_content should always be called after discover_papers."
                        "If asked to write in a file or create a file, you will STRICTLY USE WRITE_FILE TOOL. You can use it after getting the content to write in the file."}
        ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield RichLog(id="log", wrap=True, markup=True, highlight=True)
        yield Input(placeholder="Type a message and press Enter...")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#log", RichLog)
        log.write("[bold green]Hi i am IRIS. How can I help you today?[/bold green]  Ctrl+ Shift+ Q to quit, Ctrl+ Shift+ D to clear display, Ctrl+ Shift+ H to clear history.\n")
        self.query_one(Input).focus()

    # -----------------------------------------------------------------------
    # Event handlers
    # -----------------------------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Called when the user presses Enter."""
        user_text = event.value.strip()
        if not user_text:
            return
        event.input.clear()
        log = self.query_one("#log", RichLog)
        log.write(f"[bold cyan][You][/bold cyan] {user_text}\n")
        # Append user message to history
        self.messages.append({"role": "user", "content": user_text})
        self.run_worker(self._get_response, thread=True)

    def _get_response(self) -> None:
        log = self.query_one("#log", RichLog)
        try:
            reply = asyncio.run(run_agent_with_mcp(self.messages))
            self.messages.append({"role": "assistant", "content": reply})
            self.call_from_thread(log.write, f"[bold green][Agent][/bold green] {reply}\n")
        except Exception as e:
            import traceback
            self.call_from_thread(log.write, f"[bold red]ERROR:[/bold red] {traceback.format_exc()}\n")

    # -----------------------------------------------------------------------
    # Actions (bound to keyboard shortcuts)
    # -----------------------------------------------------------------------

    def action_clear_display(self) -> None:
        self.query_one("#log", RichLog).clear()

    def action_clear_history(self) -> None:
        log = self.query_one("#log", RichLog)
        del self.messages[1:]
        log.clear()
        log.write("[bold green][HISTORY CLEARED][/bold green]")

async def run_agent_with_mcp(messages):
    storage = FileTokenStorage()
    auth = OAuthClientProvider(
        server_url=MCP_SERVER_URL,
        client_metadata=OAuthClientMetadata(
            client_name="Iris",
            redirect_uris=[REDIRECT_URI],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            scope="read",
        ),
        storage=storage,
        redirect_handler=open_browser,
        callback_handler=wait_for_callback,
    )
    async with httpx.AsyncClient(auth=auth, follow_redirects=True, timeout=60) as http:
        async with streamable_http_client(MCP_SERVER_URL, http_client=http) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                mcp_tools = await session.list_tools()

                for tool in mcp_tools.tools:
                    TOOLS.append({
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.inputSchema,}})
                # ---------------------------------------------------------------------------
                # Dispatcher
                # ---------------------------------------------------------------------------
                TOOL_REGISTRY = {"web_search":web_search,"web_fetch": fetch_limit,
                                "read_file":read_file,"write_file":write_file}

                async def dispatch(tool_call):
                    name = tool_call.function.name
                    ar = tool_call.function.arguments
                    arg = json.loads(ar)
                    if name in TOOL_REGISTRY:
                        func_run = TOOL_REGISTRY[name](**arg)
                        return(json.dumps(func_run))
                    else:
                        result = await session.call_tool(name, arg)
                        return result.content[0].text
                # ---------------------------------------------------------------------------
                # Agent loop
                # ---------------------------------------------------------------------------
                MAX_ITERATIONS = 8

                async def run_agent(messages):
                    for _ in range(MAX_ITERATIONS):
                        response = client.chat.completions.create(
                            model=MODEL,
                            messages=messages,
                            tools=TOOLS,)
                        if response is None or response.choices is None:
                            return (print("NULL RESPONSE"))
                        reply = response.choices[0].message
                        finish_reason = response.choices[0].finish_reason

                        if finish_reason == "tool_calls":
                            tool_call = reply.tool_calls[0]
                            messages.append(reply)
                            func_reply = await dispatch(tool_call)
                            messages.append({"role":"tool", "tool_call_id":tool_call.id, 
                                            "content":func_reply})
                        else:
                            reply = response.choices[0].message.content
                            messages.append({"role":"assistant", "content":reply})
                            return reply

                    return f"[Agent stopped after {MAX_ITERATIONS} iterations without a final answer]"
                
                return await run_agent(messages)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ChatApp().run()
    test_queries = [
        "What were the main announcements at Google I/O 2024?",
        "Find recent papers on chain-of-thought prompting and create and write the key findings in a file named research.txt.",
        "What is llms.txt and which major websites have adopted it?."
    ]