"""Higher-level local analytics for vault and project health."""

from pathlib import Path
from typing import Any, Dict

from database import get_vault_stats
from project_intelligence import load_all_project_tasks, load_projects


async def build_overview(vault_root: Path) -> Dict[str, Any]:
    stats = await get_vault_stats()
    projects = load_projects(vault_root)
    tasks = load_all_project_tasks(vault_root)

    dirty_projects = [project for project in projects if project.get("git", {}).get("dirty", 0) > 0]
    unmapped_projects = [project for project in projects if not project.get("path")]
    active_projects = [project for project in projects if "Актив" in project.get("group", "")]

    orphan_count = stats.get("orphan_notes") or 0
    total_notes = stats.get("total_notes") or 0
    total_links = stats.get("total_links") or 0

    quality_score = 100
    if total_notes and total_links / max(total_notes, 1) < 1.2:
        quality_score -= 12
    if orphan_count:
        quality_score -= min(orphan_count * 3, 24)
    if dirty_projects:
        quality_score -= min(len(dirty_projects) * 4, 20)
    if unmapped_projects:
        quality_score -= min(len(unmapped_projects) * 3, 15)
    if len(tasks) > 20:
        quality_score -= 8

    return {
        "quality_score": max(0, quality_score),
        "vault": {
            "notes": total_notes,
            "words": stats.get("total_words") or 0,
            "links": total_links,
            "orphans": orphan_count,
            "folders": stats.get("total_folders") or 0,
        },
        "projects": {
            "total": len(projects),
            "active": len(active_projects),
            "dirty": len(dirty_projects),
            "unmapped": len(unmapped_projects),
            "dirty_ids": [project["id"] for project in dirty_projects],
            "unmapped_ids": [project["id"] for project in unmapped_projects],
        },
        "tasks": {
            "open": len(tasks),
            "by_project": {
                project["id"]: project.get("task_count", 0)
                for project in projects
                if project.get("task_count", 0)
            },
        },
        "recommendations": [
            item for item in [
                "Map missing project paths in wiki notes." if unmapped_projects else "",
                "Review dirty git projects before starting large AI actions." if dirty_projects else "",
                "Add links between orphan notes and project MOCs." if orphan_count else "",
                "Use qwen3:latest for stronger local reasoning.",
            ] if item
        ],
    }
