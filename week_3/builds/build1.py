"""
Build 1: Session Store
========================
Save and resume conversations on disk. Load AGENTS.md into the system prompt.

Tasks:
  1. create_session() -> session_id
  2. save_session(session_id, messages, title?)
  3. load_session(session_id) -> {id, title, messages, ...}
  4. list_sessions() -> [{id, title, updated_at}, ...]
  5. build_system_prompt() -> base + AGENTS.md contents

Run twice: save a session in run 1, load it in run 2 and confirm messages restored.
"""

import json
import os
import uuid
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

def now_ist():
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

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

if __name__ == "__main__":
    sid = create_session()
    messages = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": "What is a surface code?"},
        {"role": "assistant", "content": "A surface code is a type of quantum error correcting code."},
    ]
    save_session(sid, messages, title="Quantum error correction")
    print(f"Saved session: {sid}")
    print(f"All sessions: {list_sessions()}")
    print(f"Loaded: {load_session(sid)['title']}")