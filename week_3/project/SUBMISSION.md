# Research Desk (Week-3)
Last week my agent forgot everything the second I closed the terminal. This week the goal was to fix that — give it memory, clean up the code into a proper class structure, and replace AlphaXiv's OAuth headache with something that just works.
 
## Build 1 — Sessions + AGENTS.md
 
The problem was simple: `self.messages` only existed in RAM. Close the program, the whole conversation is gone.
 
- Wrote `create_session`, `save_session`, `load_session`, `list_sessions` — each conversation now gets its own JSON file under `.agent/sessions/{id}.json`
- Each file stores `id`, `title`, `created_at`, `updated_at`, and the full message history
- Had to think through the `created_at` logic a bit — if I overwrite it every save, I lose when the conversation actually started. So I check if the file already exists first, and only update `updated_at` on every save
- `build_system_prompt()` reads `AGENTS.md` off disk and tacks it onto the base prompt, so project rules live in a markdown file I can edit, not buried in Python code
Hit a couple of dumb bugs along the way. Forgot to `return` from a function once and silently set `self.messages` to `None` — took a minute to figure out why everything broke. Also had a corrupted leftover session file from an earlier crash that kept breaking `list_sessions` until I wrapped the reads in a try/except.
 
Also swapped UTC timestamps for IST — the ISO format with timezone offsets was genuinely hard to read at a glance.
 
## Build 2 — Agent Class + File Tools
 
This was the big restructuring. Pulled everything out of standalone functions and into a proper `Agent` class so the loop, tools, and sessions all live in one place instead of being scattered globals.
 
- `Agent.__init__` — loads an existing session if given an ID, otherwise starts fresh
- `Agent.chat()` — append the user's message, run the loop, save the session, return the answer
- `Agent._run_loop()` — basically the same loop from Week 2, just using `self.messages` now
- `Agent.dispatch()` — routes tool calls to the right function
- `Agent._emit()` — an empty hook in the base class. The whole point of this is that subclasses (REPL, TUI) can override it to log tool calls without ever touching the loop logic itself
#### File tools, upgraded
Week 2's `read_file`/`write_file` were honestly pretty naive — no safety, no pagination. This week:
- `resolve_path` sandboxes every file operation inside `WORKSPACE_ROOT`. Took me a bit to actually understand why you have to *join* the path first and then check it — if you compare the raw input path before joining anything, you never actually simulate what happens when someone tries to walk out with `../../`
- `read_file` now supports `start_line` and `read_lines`, prefixes every line with its number, and tells you `has_more` so the model knows if there's more content beyond what it just read
- `edit_file` does line-based replace/delete/append, and returns what got removed and added so mistakes are visible instead of silent
- `list_files` uses glob patterns to explore folders
Bugs that got me: I'd write `resolve_path()` but then forget to actually use its return value and just open the raw path anyway. Also spent a while confused why `edit_file` wasn't doing anything — turns out I computed the new lines correctly but never actually wrote them back to the file.
 
#### REPLAgent
Just adds the terminal input loop on top of `Agent`, and overrides `_emit()` to print tool calls to stderr so they don't clutter the actual conversation output.
 
## Lesson 3 — Paper Tools
 
Week 2 leaned on AlphaXiv's MCP server, which meant OAuth and a browser login every time the token expired — kind of annoying for something I wanted to just run quickly. This week I ditched MCP entirely and wrote direct calls to the Hugging Face Papers API instead.
 
- `paper_search(query)` hits HF's search endpoint and returns clean `{id, title, snippet}` dicts. The actual response wraps each result in a `"paper"` key, so I made sure to handle the case where it might not be wrapped too, just to be safe
- `read_paper(url_or_id)` first normalizes whatever gets passed in — strips arxiv.org prefixes, strips version suffixes like `v2` — then makes two separate API calls: one for metadata, one for the actual markdown content. The markdown endpoint isn't always available, so if it 404s, it just falls back to the abstract from the metadata call
Took me a second to actually get why two calls are needed — the metadata endpoint never gives you the full paper text, just the abstract. The `.md` page is a totally different URL that happens to have the real content, when it exists.
 
## Putting It All Together — Research Desk
 
Combined everything into one agent: the `Agent` brain, `REPLAgent` for the terminal, and `TUIAgent` for the Textual UI, with all 8 tools wired in — web search, web fetch, paper search, read paper, and the four file tools.
 
#### The TUI took a wrong turn first
I initially tried making `TUIAgent` inherit from both `Agent` and Textual's `App` at the same time, but that got messy fast — two different `__init__` methods fighting each other. Switched to composition instead: `TUIAgent(Agent)` is just the brain with a logging callback, and a separate `ResearchDeskApp(App)` holds a `TUIAgent` instance and calls `self.agent.chat(...)` whenever the user submits something. Much cleaner than trying to force multiple inheritance to work.
 
#### One script, three ways to run it
```
python agent.py                  # interactive REPL
python agent.py "question"       # one-shot, prints answer and exits
python agent.py --tui            # full Textual UI
python agent.py --session <id>   # resume an old conversation
```
`main()` just parses `--session` and `--tui` out of the args before deciding what to launch.
 
## What Actually Clicked This Week
 
- Sessions are just JSON files. No database needed at this scale — save after every turn so a crash doesn't wipe out the whole conversation.
- AGENTS.md is genuinely nice — rules I want to tweak live in a markdown file I can edit anytime, the code just reads it as a string. No reparsing, no special syntax.
- Sandboxing paths feels like overkill for a personal project, but the point isn't really protecting myself from myself — it's building the habit. Same pattern every real coding agent (Claude Code, Cursor, OpenCode) uses.
- Composition beats inheritance when a class would need two unrelated parents. Fighting Python's MRO to make one class inherit from both an agent brain and a Textual App just isn't worth it.
- Line numbers in file reads aren't just for display — they're literally how `edit_file` and `read_file` stay in sync. The model reads a number, trusts it, edits based on it.
## Setup
 
- API keys in `.env`: `OPENROUTER_API_KEY`, `SERPER_API_KEY`
- Dependencies: `openai`, `python-dotenv`, `requests`, `trafilatura`, `textual`
- Model: `openai/gpt-oss-120b:free`
- Folder: `week_3/project/