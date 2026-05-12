"""
AI Action Engine.

Transforms natural-language goals into approval-first actions. The model is only
allowed to propose JSON; action_manager still owns validation, diffing and writes.
"""

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from action_manager import propose_action
from ai_engine import ai_engine
from project_intelligence import load_all_project_tasks, load_projects
from vault_manager import VaultIndexer


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


def _fallback_action(goal: str) -> Dict[str, Any]:
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
    async for chunk in ai_engine.stream_chat(provider, model, messages, vault_context=context):
        result_text += chunk

    try:
        parsed = _extract_json(result_text)
        raw_actions = parsed.get("actions", [])
        if not isinstance(raw_actions, list) or not raw_actions:
            raw_actions = [_fallback_action(goal)]
    except Exception:
        raw_actions = [_fallback_action(goal)]

    proposed: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    for raw in raw_actions[:max_actions]:
        try:
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
        fallback = _fallback_action(goal)
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
