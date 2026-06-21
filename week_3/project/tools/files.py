import os
import sys
import json
import glob as glob_module
from openai import OpenAI
from dotenv import load_dotenv

MAX_READ_CHARS = 12_000
WORKSPACE_ROOT = os.path.abspath(os.environ.get("WORKSPACE_ROOT", "."))

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
