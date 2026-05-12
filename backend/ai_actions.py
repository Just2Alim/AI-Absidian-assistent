"""
AI Action Engine.

Transforms natural-language goals into approval-first actions. The model is only
allowed to propose JSON; action_manager still owns validation, diffing and writes.
"""

import json
import re
import time
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

from action_manager import propose_action
from ai_engine import ai_engine
from project_intelligence import load_all_project_tasks, load_projects
from vault_manager import VaultIndexer

ACTION_TIMEOUT_SECONDS = 55
CODE_FILE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".scss", ".json",
    ".mdx", ".yaml", ".yml", ".toml", ".rs", ".dart", ".java", ".kt", ".swift",
    ".c", ".cpp", ".h", ".hpp", ".go", ".php", ".sh", ".sql", ".txt",
}


ACTION_SCHEMA = """
Return ONLY JSON, no markdown:
{
  "actions": [
    {
      "action_type": "create_note|update_note|append_note|write_file|rename_note|delete_note",
      "title": "short human title",
      "summary": "why this action is useful",
      "payload": {}
    }
  ]
}

Payload examples:
- create_note: {"folder":"wiki","title":"new-note","content":"# Title\\n...","frontmatter":{"tags":["ai"]}}
- append_note: {"path":"wiki/learning-log.md","content":"## 2026-05-12 – Insight\\n..."}
- update_note: {"path":"wiki/project.md","content":"full markdown content"}
- write_file: {"path":"relative/path/inside/active/workspace.ext","content":"full file content"}

Rules:
- Obsidian note paths are always vault-relative, for example "inbox/test.md" or "wiki/decisions.md".
- File paths for write_file must stay inside the active working directory. Prefer relative paths.
- If the user asks for a code file, script, component, page, config, JSON, HTML, CSS, Python, JS, TS or similar artifact, you MUST use write_file and MUST NOT use create_note.
- If the requested target project is not the active working directory, ask for a workspace switch by creating an append_note plan instead of writing a file.
- Prefer append_note for decisions, learning-log, daily notes and project updates.
- Never modify CLAUDE.md or raw/.
- Never claim changes are applied. They are pending approvals.
- Keep actions small and reviewable.
"""


def _extract_json(text: str) -> Dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", stripped)
        if not match:
            raise
        return json.loads(match.group(0))


def _vault_digest(vault_root: Path) -> str:
    projects = load_projects(vault_root)
    tasks = load_all_project_tasks(vault_root)
    lines = ["Projects:"]
    for project in projects:
        lines.append(
            f"- {project['id']}: {project['title']} | {project['status']} | "
            f"path={project.get('path') or 'unknown'} | tasks={project.get('task_count', 0)}"
        )
    lines.append("\nOpen tasks:")
    for task in tasks[:30]:
        lines.append(f"- {task['project']}: {task['task']}")
    return "\n".join(lines)


def _python_pi_gui_content() -> str:
    return """import math
import tkinter as tk


root = tk.Tk()
root.title("Pi Display")
root.geometry("360x220")
root.configure(bg="#f7f4ea")

frame = tk.Frame(root, bg="#f7f4ea", padx=24, pady=24)
frame.pack(expand=True, fill="both")

title = tk.Label(frame, text="Number Pi", font=("Helvetica", 22, "bold"), bg="#f7f4ea", fg="#16302b")
title.pack(pady=(0, 12))

value = tk.Label(frame, text=f"pi = {math.pi:.12f}", font=("Helvetica", 18), bg="#f7f4ea", fg="#1f4d45")
value.pack(pady=(0, 18))

button = tk.Button(frame, text="Close", command=root.destroy, padx=16, pady=8)
button.pack()

root.mainloop()
"""


def _suggest_code_path(goal: str) -> str:
    text = goal.lower()
    folder_match = re.search(r'папк[ауеы]\s+"?([a-zA-Z0-9_./ -]+)"?', goal, re.IGNORECASE)
    folder = folder_match.group(1).strip().replace(" ", "_") if folder_match else ""
    if "pi" in text or "пи" in text:
        filename = "pi_display.py"
    elif "python" in text or "пайтон" in text:
        filename = "main.py"
    else:
        filename = "generated_file.txt"
    return f"{folder}/{filename}" if folder else filename


def _fallback_action(goal: str, workspace: Optional[Path] = None) -> Dict[str, Any]:
    if workspace and _looks_like_code_request(goal):
        path = _suggest_code_path(goal)
        content = _python_pi_gui_content() if ("pi" in goal.lower() or "пи" in goal.lower()) and ("python" in goal.lower() or "пайтон" in goal.lower()) else "# Generated file\n"
        return {
            "action_type": "write_file",
            "title": f"Create code file: {path}",
            "summary": "Fallback action for a code-file request when the local model did not return valid JSON.",
            "payload": {
                "path": path,
                "content": content,
                "working_directory": str(workspace),
            },
        }
    today = time.strftime("%Y-%m-%d")
    return {
        "action_type": "append_note",
        "title": "Record AI action plan",
        "summary": "Fallback action because the local model did not return valid JSON.",
        "payload": {
            "path": f"daily/{today}.md",
            "content": (
                f"## AI Action Draft – {time.strftime('%H:%M')}\n\n"
                f"- **Goal:** {goal}\n"
                "- **Status:** Needs manual review\n"
            ),
        },
    }


def _looks_like_code_request(goal: str) -> bool:
    text = goal.lower()
    hints = [
        "файл", "python", "пайтон", "скрипт", "код", "gui", "интерфейс", "tkinter",
        "html", "css", "javascript", "typescript", "react", "component", "json",
        "config", "script", "app", "create file", "write file",
    ]
    return any(hint in text for hint in hints)


def _looks_like_code_path(value: str) -> bool:
    suffix = Path(value.strip()).suffix.lower()
    return suffix in CODE_FILE_EXTENSIONS


def _normalize_action(raw: Dict[str, Any], workspace: Path, goal: str) -> Dict[str, Any]:
    action = dict(raw)
    payload = dict(action.get("payload", {}))
    action["payload"] = payload

    if action.get("action_type") == "write_file":
        payload["working_directory"] = str(workspace)
        return action

    if action.get("action_type") == "create_note":
        title = str(payload.get("title", "")).strip()
        folder = str(payload.get("folder", "")).strip().strip("/")
        if _looks_like_code_path(title) or _looks_like_code_request(goal):
            file_name = title or "generated_file.txt"
            relative_path = f"{folder}/{file_name}" if folder else file_name
            action["action_type"] = "write_file"
            action["title"] = action.get("title") or f"Write file: {relative_path}"
            action["summary"] = action.get("summary") or "Create a real project file inside the active workspace."
            action["payload"] = {
                "path": relative_path,
                "content": payload.get("content", ""),
                "working_directory": str(workspace),
            }
    elif action.get("action_type") in {"append_note", "update_note"}:
        path = str(payload.get("path", "")).strip()
        if _looks_like_code_path(path):
            action["action_type"] = "write_file"
            action["title"] = action.get("title") or f"Write file: {path}"
            action["summary"] = action.get("summary") or "Write code content into a real project file."
            action["payload"] = {
                "path": path,
                "content": payload.get("content", ""),
                "working_directory": str(workspace),
            }
    return action


async def propose_ai_actions(
    goal: str,
    indexer: VaultIndexer,
    provider: str = "ollama",
    model: str = "qwen3:latest",
    max_actions: int = 5,
    working_directory: Optional[Path] = None,
) -> Dict[str, Any]:
    context = _vault_digest(indexer.vault_root)
    workspace = working_directory.resolve() if working_directory else Path.home() / "projects"
    prompt = (
        f"{ACTION_SCHEMA}\n\n"
        f"Active working directory:\n{workspace}\n\n"
        f"Vault context:\n{context}\n\n"
        "Important: any write_file action must be inside the active working directory. "
        "Use relative paths whenever possible. Do not write elsewhere on the computer.\n\n"
        f"User goal:\n{goal}"
    )
    messages = [{"role": "user", "content": prompt}]

    result_text = ""
    try:
        async with asyncio.timeout(ACTION_TIMEOUT_SECONDS):
            async for chunk in ai_engine.stream_chat(provider, model, messages, vault_context=context):
                result_text += chunk
    except TimeoutError:
        result_text = (
            "Action generation timed out. The request was saved as a reviewable "
            "plan instead of waiting forever."
        )
        raw_actions = [_fallback_action(goal, workspace)]
    else:
        raw_actions = None

    try:
        if raw_actions is None:
            parsed = _extract_json(result_text)
            raw_actions = parsed.get("actions", [])
        if not isinstance(raw_actions, list) or not raw_actions:
            raw_actions = [_fallback_action(goal, workspace)]
    except Exception:
        raw_actions = [_fallback_action(goal, workspace)]

    proposed: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    for raw in raw_actions[:max_actions]:
        try:
            raw = _normalize_action(raw, workspace, goal)
            if raw.get("action_type") == "write_file":
                payload = raw.setdefault("payload", {})
                payload["working_directory"] = str(workspace)
            action = await propose_action(
                raw["action_type"],
                raw.get("payload", {}),
                indexer=indexer,
                title=raw.get("title"),
                summary=raw.get("summary"),
                created_by="ai-action-engine",
            )
            proposed.append(action)
        except Exception as exc:
            errors.append({"title": raw.get("title", "Action"), "error": str(exc)})

    if not proposed:
        fallback = _fallback_action(goal, workspace)
        try:
            proposed.append(await propose_action(
                fallback["action_type"],
                fallback["payload"],
                indexer=indexer,
                title=fallback["title"],
                summary=fallback["summary"],
                created_by="ai-action-engine",
            ))
        except Exception as exc:
            errors.append({"title": fallback["title"], "error": str(exc)})

    return {
        "model_output": result_text,
        "actions": proposed,
        "errors": errors,
    }
