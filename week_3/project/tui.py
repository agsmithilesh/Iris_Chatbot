"""
TUIAgent — full-screen Textual UI inheriting from Agent.

Usage:
  python agent.py --tui
"""

import sys
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, Input, RichLog

from agent import Agent


class TUIAgent(Agent):
    """Agent brain with tool-call logging routed to a callback."""

    def __init__(self, *args, log_callback=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.log_callback = log_callback

    def _emit(self, event, **data):
        if event == "tool_call" and self.log_callback:
            self.log_callback(data.get("name"))


class ResearchDeskApp(App):
    """Full-screen terminal UI wrapping TUIAgent."""

    TITLE = "Research Desk"
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
        height: 3;
    }
    """

    BINDINGS = [
        Binding("ctrl+l", "clear_display", "Clear display"),
        Binding("ctrl+k", "clear_history", "Clear history"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, session_id=None):
        super().__init__()
        self.agent = TUIAgent(session_id=session_id, log_callback=self._log_tool_call)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield RichLog(id="log", wrap=True, markup=True)
        yield Input(placeholder="Ask a research question...")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#log", RichLog)
        log.write(
            f"[bold green]Research Desk[/bold green] "
            f"[session {self.agent.session_id}] — Ctrl+Q quit, Ctrl+L clear display, Ctrl+K clear history\n"
        )
        self.query_one(Input).focus()

    def _log_tool_call(self, name) -> None:
        log = self.query_one("#log", RichLog)
        self.call_from_thread(log.write, f"[dim]  [tool] {name}[/dim]\n")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        user_text = event.value.strip()
        if not user_text:
            return
        self.user_text = user_text
        event.input.clear()

        log = self.query_one("#log", RichLog)
        log.write(f"[bold cyan][You][/bold cyan] {user_text}\n")

        self.run_worker(self._get_response, thread=True)

    def _get_response(self) -> None:
        log = self.query_one("#log", RichLog)
        try:
            reply = self.agent.chat(self.user_text)
            self.call_from_thread(log.write, f"[bold green][Agent][/bold green] {reply}\n")
        except Exception as e:
            self.call_from_thread(log.write, f"[bold red]ERROR:[/bold red] {str(e)}\n")

    def action_clear_display(self) -> None:
        self.query_one("#log", RichLog).clear()

    def action_clear_history(self) -> None:
        self.agent.messages = self.agent.messages[:1]  # keep just system prompt
        self.query_one("#log", RichLog).clear()
        self.query_one("#log", RichLog).write("[bold green][HISTORY CLEARED][/bold green]\n")


if __name__ == "__main__":
    ResearchDeskApp().run()