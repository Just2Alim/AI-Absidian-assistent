"""Controlled learning memory for the local assistant."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from database import (
    create_learning_item,
    get_vault_config,
    list_learning_items,
    record_learning_feedback,
    save_vault_config,
    set_learning_item_status,
)


DEFAULT_LEARNING_SETTINGS = {
    "mode": "review",
    "include_in_chat": True,
    "auto_promote_feedback": False,
    "max_context_items": 12,
}


async def get_learning_settings() -> Dict[str, Any]:
    raw = await get_vault_config("learning_settings")
    settings = dict(DEFAULT_LEARNING_SETTINGS)
    if raw:
        import json

        try:
            settings.update(json.loads(raw))
        except Exception:
            pass
    return settings


async def save_learning_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    import json

    current = await get_learning_settings()
    current.update({key: value for key, value in settings.items() if value is not None})
    await save_vault_config("learning_settings", json.dumps(current, ensure_ascii=False))
    return current


async def add_learning_item(
    kind: str,
    title: str,
    content: str,
    scope: str = "global",
    project_id: Optional[str] = None,
    workspace: Optional[str] = None,
    source: str = "manual",
    confidence: float = 0.8,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    settings = await get_learning_settings()
    item_status = status or ("pending" if settings.get("mode") == "review" else "active")
    return await create_learning_item(
        kind=kind,
        title=title,
        content=content,
        scope=scope,
        project_id=project_id,
        workspace=workspace,
        source=source,
        confidence=confidence,
        status=item_status,
    )


async def add_feedback_as_learning(
    feedback: str,
    title: str = "User correction",
    workspace: Optional[str] = None,
    rating: Optional[int] = None,
) -> Dict[str, Any]:
    settings = await get_learning_settings()
    await record_learning_feedback(feedback=feedback, rating=rating)
    status = "active" if settings.get("auto_promote_feedback") else "pending"
    return await create_learning_item(
        kind="correction",
        scope="workspace" if workspace else "global",
        workspace=workspace,
        title=title,
        content=feedback,
        source="feedback",
        confidence=0.9 if rating and rating > 0 else 0.75,
        status=status,
    )


async def activate_learning_item(item_id: str):
    await set_learning_item_status(item_id, "active")


async def archive_learning_item(item_id: str):
    await set_learning_item_status(item_id, "archived")


async def list_memory(status: Optional[str] = None, workspace: Optional[str] = None, limit: int = 100):
    return await list_learning_items(status=status, workspace=workspace, limit=limit)


async def build_learning_context(workspace: Optional[Path] = None) -> str:
    settings = await get_learning_settings()
    if not settings.get("include_in_chat", True):
        return ""
    items = await list_learning_items(
        status="active",
        workspace=str(workspace.resolve()) if workspace else None,
        limit=int(settings.get("max_context_items", 12)),
    )
    if not items:
        return ""
    lines = ["Assistant learning memory:"]
    for item in items:
        scope = item.get("scope") or "global"
        kind = item.get("kind") or "memory"
        lines.append(f"- [{kind}/{scope}] {item['title']}: {item['content']}")
    return "\n".join(lines)
