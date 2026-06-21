import os
from openai import OpenAI
from dotenv import load_dotenv
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, Input, RichLog
from textual.containers import Vertical

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)

MAX_HISTORY_TURNS = 7   # keep last N user+assistant pairs

# ---------------------------------------------------------------------------
# Chat logic (reuse / adapt from your Week 1 submission)
# ---------------------------------------------------------------------------

def call_model(messages):
    response = client.chat.completions.create(model="openai/gpt-oss-120b:free", messages=messages)
    reply = response.choices[0].message.content
    return reply

def trim_history(messages, max_turns):
    if(len(messages)>=max_turns*2+1):
        messages.append({"role":"system","content":"Summarize the key points and also keep your response simple."})
        response = client.chat.completions.create(model="openai/gpt-oss-120b:free", messages=messages)
        reply = response.choices[0].message.content
        messages.append({"role": "assistant", "content": reply})
        del messages[1:len(messages)-2]
    return messages

# ---------------------------------------------------------------------------
# TUI
# ---------------------------------------------------------------------------

class ChatApp(App):
    """A full-screen terminal chatbot."""

    TITLE = "IRIS (week-1)"
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
        height: 4;
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
            {"role": "system", "content": "You are IRIS, a very famous detective. You are also very witty and sarcastic. You have a great sense of humor and you love to make jokes. You remember key details about the conversation but answer in a concise manner. You are also very good at summarizing the conversation when needed."}
        ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield RichLog(id="log", wrap=True, markup=True, highlight=True)
        yield Input(placeholder="Type a message and press Enter...")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#log", RichLog)
        log.write("[bold green]Hi i am IRIS, your detective assistant. How can I help you today?[/bold green] Ctrl+Q to quit, Ctrl+L to clear.\n")
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
        self.messages = trim_history(self.messages, MAX_HISTORY_TURNS)
        self.run_worker(self._get_response(), thread=True)

    async def _get_response(self) -> None:
        log = self.query_one("#log", RichLog)
        try:
            reply = call_model(self.messages)
            self.messages.append({"role": "assistant", "content": reply})
            self.call_from_thread(log.write, f"[bold green][Agent][/bold green] {reply}\n")
        except Exception as e:
            self.call_from_thread(log.write, f"[bold red]ERROR:[/bold red] {str(e)}\n")

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

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ChatApp().run()