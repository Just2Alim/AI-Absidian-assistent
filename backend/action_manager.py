"""
Approval-first action manager.

All writes proposed by AI, the mobile bridge, or the UI become action requests.
Only an approved action is allowed to touch the vault or project files.
"""

import difflib
import json
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Optional

from database import (
    create_action_request,
    get_action_request,
    list_action_requests,
    mark_action_applied,
    record_audit_log,
    set_action_status,
)
from vault_manager import VaultIndexer


PROJECTS_ROOT = (Path.home() / "projects").resolve()
DATA_BACKUPS = (Path(__file__).parent.parent / "data" / "file-backups").resolve()


def _unified_diff(old: str, new: str, fromfile: str, tofile: str) -> str:
    diff = list(
        difflib.unified_diff(
            old.splitlines(),
            new.splitlines(),
            fromfile=fromfile,
            tofile=tofile,
            lineterm="",
        )
    )
    return "\n".join(diff) + ("\n" if diff else "")


def _safe_workspace_root(path: Optional[str] = None) -> Path:
    root = Path(path).expanduser().resolve() if path else PROJECTS_ROOT
    try:
        root.relative_to(PROJECTS_ROOT)
    except ValueError as exc:
        raise ValueError(f"Workspace must be inside {PROJECTS_ROOT}") from exc
    if ".git" in root.parts:
        raise PermissionError("Workspaces inside .git are not allowed")
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Workspace does not exist: {root}")
    return root


def _safe_project_path(path: str, workspace_root: Optional[str] = None) -> Path:
    workspace = _safe_workspace_root(workspace_root)
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = workspace / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(PROJECTS_ROOT)
    except ValueError as exc:
        raise ValueError(f"File actions are limited to {PROJECTS_ROOT}") from exc
    try:
        resolved.relative_to(workspace)
    except ValueError as exc:
        raise ValueError(f"File actions are limited to selected workspace: {workspace}") from exc
    if ".git" in resolved.parts:
        raise PermissionError("Direct writes inside .git are not allowed")
    return resolved


def _backup_project_file(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    stamp = time.strftime("%Y%m%d-%H%M%S")
    relative = path.relative_to(PROJECTS_ROOT)
    backup_path = DATA_BACKUPS / stamp / relative
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path)
    return str(backup_path)


def _best_effort_vault_backup(indexer: VaultIndexer, path: str) -> Optional[str]:
    try:
        return indexer.backup_file(path)
    except OSError:
        return None


def _build_note_content(content: str, frontmatter: Optional[Dict[str, Any]] = None) -> str:
    if not frontmatter:
        return content
    lines = ["---"]
    for key, value in frontmatter.items():
        if isinstance(value, (list, dict)):
            rendered = json.dumps(value, ensure_ascii=False)
        else:
            rendered = str(value)
        lines.append(f"{key}: {rendered}")
    lines.append("---")
    lines.append("")
    lines.append(content)
    return "\n".join(lines)


async def propose_action(
    action_type: str,
    payload: Dict[str, Any],
    indexer: Optional[VaultIndexer] = None,
    title: Optional[str] = None,
    summary: Optional[str] = None,
    created_by: str = "assistant",
) -> Dict[str, Any]:
    """Create a pending action with a human-readable diff preview."""
    diff_preview = ""

    if action_type == "create_note":
        if not indexer:
            raise ValueError("Vault is not configured")
        folder = payload.get("folder", "")
        note_title = payload["title"]
        rel_path = f"{folder}/{note_title}" if folder else note_title
        if not rel_path.endswith(".md"):
            rel_path += ".md"
        content = _build_note_content(payload.get("content", ""), payload.get("frontmatter"))
        diff_preview = _unified_diff("", content, "/dev/null", rel_path)
        title = title or f"Create note: {rel_path}"
        summary = summary or "Create a new markdown note in the Obsidian vault."

    elif action_type == "update_note":
        if not indexer:
            raise ValueError("Vault is not configured")
        path = payload["path"]
        old_content = indexer.read_note_content(path) or ""
        new_content = payload.get("content", "")
        diff_preview = _unified_diff(old_content, new_content, path, path)
        title = title or f"Update note: {path}"
        summary = summary or "Replace the note content after approval."

    elif action_type == "append_note":
        if not indexer:
            raise ValueError("Vault is not configured")
        path = payload["path"]
        old_content = indexer.read_note_content(path) or ""
        append_content = payload.get("content", "")
        separator = "\n\n" if old_content and not old_content.endswith("\n\n") else ""
        new_content = old_content + separator + append_content.strip() + "\n"
        payload["content"] = append_content.strip() + "\n"
        diff_preview = _unified_diff(old_content, new_content, path, path)
        title = title or f"Append note: {path}"
        summary = summary or "Append markdown content to an Obsidian note after approval."

    elif action_type == "delete_note":
        if not indexer:
            raise ValueError("Vault is not configured")
        path = payload["path"]
        old_content = indexer.read_note_content(path) or ""
        diff_preview = _unified_diff(old_content, "", path, ".trash/" + Path(path).name)
        title = title or f"Move note to trash: {path}"
        summary = summary or "Move the note into the vault .trash folder."

    elif action_type == "rename_note":
        old_path = payload["old_path"]
        new_name = payload["new_name"]
        diff_preview = f"Rename:\n- {old_path}\n+ {new_name}\n"
        title = title or f"Rename note: {old_path}"
        summary = summary or "Rename a note file after approval."

    elif action_type == "write_file":
        workspace_root = payload.get("working_directory") or payload.get("workspace_root")
        path = _safe_project_path(payload["path"], workspace_root)
        old_content = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        new_content = payload.get("content", "")
        fromfile = str(path) if path.exists() else "/dev/null"
        diff_preview = _unified_diff(old_content, new_content, fromfile, str(path))
        title = title or f"Write file: {path}"
        summary = summary or "Create or replace a project file after approval."
        payload["path"] = str(path)
        payload["working_directory"] = str(_safe_workspace_root(workspace_root))

    else:
        raise ValueError(f"Unsupported action type: {action_type}")

    return await create_action_request(
        action_type=action_type,
        title=title,
        summary=summary,
        payload=payload,
        diff_preview=diff_preview,
        created_by=created_by,
    )


async def approve_action(action_id: str, indexer: Optional[VaultIndexer]) -> Dict[str, Any]:
    action = await get_action_request(action_id)
    if not action:
        raise ValueError("Action not found")
    if action["status"] not in {"pending", "failed"}:
        raise ValueError(f"Action is not pending or retryable: {action['status']}")

    await set_action_status(action_id, "approved")
    payload = action["payload"]
    action_type = action["action_type"]
    result: Dict[str, Any] = {}

    try:
        if action_type == "create_note":
            if not indexer:
                raise ValueError("Vault is not configured")
            frontmatter = payload.get("frontmatter")
            rel_path = indexer.create_note(
                payload.get("folder", ""),
                payload["title"],
                payload.get("content", ""),
                frontmatter,
            )
            result = {"path": rel_path}

        elif action_type == "update_note":
            if not indexer:
                raise ValueError("Vault is not configured")
            backup = indexer.backup_file(payload["path"])
            indexer.write_note_content(payload["path"], payload.get("content", ""))
            result = {"path": payload["path"], "backup": backup}

        elif action_type == "append_note":
            if not indexer:
                raise ValueError("Vault is not configured")
            backup = _best_effort_vault_backup(indexer, payload["path"])
            indexer.append_note_content(payload["path"], payload.get("content", ""))
            result = {"path": payload["path"], "backup": backup, "mode": "append"}

        elif action_type == "delete_note":
            if not indexer:
                raise ValueError("Vault is not configured")
            backup = indexer.backup_file(payload["path"])
            ok = indexer.delete_note(payload["path"])
            result = {"path": payload["path"], "deleted": ok, "backup": backup}

        elif action_type == "rename_note":
            if not indexer:
                raise ValueError("Vault is not configured")
            backup = indexer.backup_file(payload["old_path"])
            new_path = indexer.rename_note(payload["old_path"], payload["new_name"])
            result = {"old_path": payload["old_path"], "new_path": new_path, "backup": backup}

        elif action_type == "write_file":
            path = _safe_project_path(payload["path"], payload.get("working_directory"))
            backup = _backup_project_file(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(payload.get("content", ""), encoding="utf-8")
            result = {"path": str(path), "backup": backup}

        else:
            raise ValueError(f"Unsupported action type: {action_type}")

        await mark_action_applied(action_id, result)
        await record_audit_log(
            entity_type="action_request",
            entity_id=action_id,
            action=action_type,
            summary=action.get("summary") or action.get("title") or "",
            payload={"payload": payload, "result": result},
        )
        return await get_action_request(action_id)

    except Exception as exc:
        await set_action_status(action_id, "failed", str(exc))
        raise


async def reject_action(action_id: str, reason: str = "") -> Dict[str, Any]:
    action = await get_action_request(action_id)
    if not action:
        raise ValueError("Action not found")
    if action["status"] not in {"pending", "failed"}:
        raise ValueError(f"Action is not pending or retryable: {action['status']}")
    await set_action_status(action_id, "rejected", reason or None)
    await record_audit_log(
        entity_type="action_request",
        entity_id=action_id,
        action="rejected",
        summary=reason or action.get("title") or "Rejected action",
        payload={"action_type": action["action_type"]},
    )
    return await get_action_request(action_id)


async def pending_actions(limit: int = 50):
    return await list_action_requests(status="pending", limit=limit)
