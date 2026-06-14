# IRIS (Week-2)
Proper AI agent across 3 builds — starting from manual tool calling all the way to a full agent with web search, MCP integration, and a terminal UI.
 
## Build 1 — Manual Tool Calling
 
The first build was about understanding how tool calling actually works under the hood, without any SDK magic.
 
- Implemented custom tool calling using XML tags (`<tool_call>`)
- Wrote `parse_tool_call` and `strip_tool_call` using regex to manually extract tool names and arguments from the model's response
- Tools: `read_file` and `write_file`
- Agent loop manually checked for `<tool_call>` in the response and sent back results in `<tool_response>` format
The main thing I learned here: the model doesn't actually *run* tools. It just outputs text saying "call this tool with these args." Your code reads that, runs the tool, and sends the result back. The model has no special powers — it's all just text in, text out.
 
## Build 2 — Native SDK Tool Calling
 
Same idea as Build 1, but now using the OpenAI SDK's built-in tool calling instead of manual XML parsing.
 
- Defined tool schemas as Python dicts (`TOOLS` list)
- Tools: `get_weather` and `calculate`
- The SDK handles formatting — no more regex
Key things I understood:
- `finish_reason == "tool_calls"` means the model wants to call a tool, `"stop"` means it's done
- `tool_call.function.name` gives the tool name, `tool_call.function.arguments` gives a JSON string that needs `json.loads()`
- The tool response goes back as `{"role": "tool", "tool_call_id": ..., "content": ...}`
- `**kwargs` unpacking — keys in the args dict must exactly match the function's parameter names
- `dispatch()` uses `TOOL_REGISTRY[name](**args)` — works generically for any tool
Build 2 is cleaner and more reliable than Build 1. The SDK handles edge cases that manual parsing would miss.
 
## Build 3 — TUI on Week 1's Chatbot
 
Took the basic multi-turn chatbot from Week 1 and gave it a proper terminal UI using `textual`. No new tools — just the chat logic with a full-screen interface.
 
- Scrollable chat log (`RichLog`) and input box at the bottom (`Input`)
- Header with clock, footer showing keyboard shortcuts
- Keyboard shortcuts: `Ctrl+Shift+D` (clear display), `Ctrl+Shift+H` (clear history), `Ctrl+Shift+Q` (quit)
- API calls run in a background thread via `run_worker(thread=True)` so the UI doesn't freeze
- Used `call_from_thread(log.write, ...)` to safely update the UI from inside the worker thread
The key thing I learned here: you can't touch UI widgets from a background thread directly. You have to use `call_from_thread` to hand the update back to the main thread safely.
 
## Iris — The Main Agent
 
After the 3 builds, I combined everything into one agent. Added real tools, connected to AlphaXiv via MCP, and plugged the full agent loop into the TUI.
 
### Web Search
Used the Serper API for real-time Google search. `web_search(query)` sends a POST request to Serper and returns a clean list of `{title, link, snippet}` dicts.
 
Understood GET vs POST here — GET fetches a resource from a URL, POST sends data to a server and gets a result back. Serper uses POST because you're sending a query and getting search results back.
 
### Web Fetch
`web_fetch(url)` fetches raw HTML, then `trafilatura` strips ads, navbars, and junk to return just the article content. Truncated to 800 chars — sending a full page to the model drowns its attention and wastes the context window.
 
### File Operations
`read_file` and `write_file` so Iris can save things to disk. Had a Unicode bug when writing — fixed by adding `encoding="utf-8"` to both file opens.
 
### MCP Integration (AlphaXiv)
MCP is a standard for exposing tools — write a tool server once, any MCP-compatible agent can use it. AlphaXiv exposes research paper tools (`discover_papers`, `get_paper_content`) over MCP.
 
AlphaXiv requires OAuth 2.0 authentication. Implemented `FileTokenStorage` to save the login token to `.alphaxiv_tokens.json` so the browser login only happens once. Used `streamable_http_client` because AlphaXiv uses a newer HTTP transport (not SSE).
 
Dispatch logic: if the tool is in local `TOOL_REGISTRY` → call the Python function. If not → forward to MCP server with `await session.call_tool(name, args)`.
 
### Plugging it into the TUI
The agent loop (`run_agent_with_mcp`) is async. The TUI worker thread is sync. Bridged this with `asyncio.run(run_agent_with_mcp(messages))` inside the thread — creates a fresh event loop in the thread and runs the async agent inside it.
 
## Concepts I Actually Understood This Week
 
- **The agent loop**: the model outputs which tool to call, your code runs it, sends the result back, model continues. Just messages going back and forth.
- **async/await vs threads**: async is one thread switching between tasks while waiting on I/O. Threads are actual parallel execution. Needed both — async for MCP, threads for keeping the UI alive.
- **MCP**: like USB for AI tools. Write once, any client can plug in.
- **OAuth**: browser login flow, token saved to file, only login once.
- **Context window**: truncating results matters. Too much context crowds out earlier conversation.
 
## Setup
 
- API keys in `.env`: `OPENROUTER_API_KEY`, `SERPER_API_KEY`
- Dependencies: `openai`, `requests`, `trafilatura`, `httpx`, `mcp`, `textual`, `python-dotenv`
- Model: `openai/gpt-oss-120b:free`