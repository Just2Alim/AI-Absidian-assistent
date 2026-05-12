"""
Project intelligence layer built from the Obsidian vault.

The vault remains the source of truth: wiki/INDEX.md declares projects and
individual wiki pages provide paths, tasks, stack, status and repository links.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECTS_ROOT = (Path.home() / "projects").resolve()


PROJECT_ROW_RE = re.compile(
    r"^\|\s*\[\[([^\]]+)\]\]\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|"
)
ABS_PROJECT_PATH_RE = re.compile(r"(/Users/justalim/projects/[^\n`*)]+)")
LOCAL_RE = re.compile(r"Local:\s*`([^`]+)`")
GITHUB_RE = re.compile(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
TASK_RE = re.compile(r"^\s*-\s*\[\s*\]\s+(.+)$", re.MULTILINE)
H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
QUOTE_RE = re.compile(r"^>\s+(.+)$", re.MULTILINE)


def _read(path: Path) -> str:
    candidates = [path]
    parts = list(path.parts)
    if "obsidian-vault" in parts:
        index = parts.index("obsidian-vault")
        rel = Path(*parts[index + 1:]) if index + 1 < len(parts) else Path()
        fallback = PROJECTS_ROOT / "obsidian-vault" / rel
        if fallback != path:
            candidates.append(fallback)

    for candidate in candidates:
        try:
            return candidate.read_text(encoding="utf-8", errors="ignore")
        except FileNotFoundError:
            continue
        except OSError:
            continue
    return ""


def _clean_cell(value: str) -> str:
    return value.strip().replace("<br>", ", ")


def _project_id(note_slug: str) -> str:
    return note_slug.strip().lower().replace(" ", "-")


def _safe_existing_path(raw_path: str) -> Optional[str]:
    cleaned = raw_path.strip().rstrip("/ .)")
    path = Path(cleaned).expanduser()
    try:
        resolved = path.resolve()
        resolved.relative_to(PROJECTS_ROOT)
    except Exception:
        return None
    if resolved == PROJECTS_ROOT:
        return None
    return str(resolved) if resolved.exists() else None


def _extract_path(page: str) -> Optional[str]:
    local_match = LOCAL_RE.search(page)
    if local_match:
        safe = _safe_existing_path(local_match.group(1))
        if safe:
            return safe

    path_section = re.search(r"##\s+Путь\s*\n+```(.*?)```", page, re.DOTALL)
    if path_section:
        for line in path_section.group(1).splitlines():
            line = line.strip()
            if line.startswith("/Users/justalim/projects/"):
                candidate = line.split("←", 1)[0].strip()
                safe = _safe_existing_path(candidate)
                if safe:
                    return safe

    for match in ABS_PROJECT_PATH_RE.findall(page):
        safe = _safe_existing_path(match)
        if safe:
            return safe
    return None


def _extract_status_details(page: str) -> List[str]:
    match = re.search(r"##\s+Статус\s*\n(?P<body>.*?)(?:\n##\s+|\Z)", page, re.DOTALL)
    if not match:
        return []
    details = []
    for line in match.group("body").splitlines():
        line = line.strip()
        if line.startswith("- "):
            details.append(line[2:].strip())
    return details[:8]


def _detect_runtime(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return {"exists": False, "signals": []}
    root = Path(path)
    signals = []
    files = {
        "package.json": "Node.js",
        "pubspec.yaml": "Flutter",
        "docker-compose.yml": "Docker Compose",
        "compose.yml": "Docker Compose",
        "firebase.json": "Firebase",
        "pyproject.toml": "Python",
        "requirements.txt": "Python",
        "Cargo.toml": "Rust",
    }
    for filename, label in files.items():
        if (root / filename).exists():
            signals.append(label)
    if (root / ".github" / "workflows").exists():
        signals.append("GitHub Actions")
    return {"exists": root.exists(), "signals": sorted(set(signals))}


def _git_status(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return {"available": False, "reason": "No project path"}

    root = Path(path)
    if not root.exists():
        return {"available": False, "reason": "Path does not exist"}

    try:
        top_level = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except Exception:
        return {"available": False, "reason": "Not a git repository"}

    repo_root = Path(top_level.stdout.strip()).resolve()
    if repo_root != root.resolve():
        return {
            "available": False,
            "reason": f"No dedicated git repository; parent repo is {repo_root}",
        }

    status = subprocess.run(
        ["git", "-C", str(root), "status", "--short", "--branch"],
        check=False,
        capture_output=True,
        text=True,
        timeout=4,
    )
    lines = [line for line in status.stdout.splitlines() if line.strip()]
    branch_line = lines[0] if lines else ""
    dirty = [line for line in lines[1:] if line.strip()]

    branch = branch_line.replace("##", "").strip()
    ahead = "ahead" in branch
    behind = "behind" in branch

    return {
        "available": True,
        "branch": branch,
        "dirty": len(dirty),
        "ahead": ahead,
        "behind": behind,
        "changes": dirty[:20],
    }


def _parse_project_sections(index_text: str) -> List[Dict[str, str]]:
    projects: List[Dict[str, str]] = []
    current_group = ""
    for raw_line in index_text.splitlines():
        line = raw_line.strip()
        if line.startswith("## ") and "Проекты" in line:
            current_group = line.replace("#", "").strip()
            continue
        match = PROJECT_ROW_RE.match(line)
        if not match:
            continue
        note_slug, description, stack, status = match.groups()
        projects.append(
            {
                "id": _project_id(note_slug),
                "note_slug": note_slug,
                "note_path": f"wiki/{note_slug}.md",
                "group": current_group,
                "description": _clean_cell(description),
                "stack": _clean_cell(stack),
                "status": _clean_cell(status),
            }
        )
    return projects


def load_projects(vault_root: Path) -> List[Dict[str, Any]]:
    index_text = _read(vault_root / "wiki" / "INDEX.md")
    projects = _parse_project_sections(index_text)

    enriched = []
    for project in projects:
        page_path = vault_root / project["note_path"]
        page = _read(page_path)
        title_match = H1_RE.search(page)
        quote_match = QUOTE_RE.search(page)
        github_match = GITHUB_RE.search(page)
        project_path = _extract_path(page)
        tasks = [task.strip() for task in TASK_RE.findall(page)]

        item = {
            **project,
            "title": title_match.group(1).strip() if title_match else project["note_slug"],
            "summary": quote_match.group(1).strip() if quote_match else project["description"],
            "path": project_path,
            "github": github_match.group(0) if github_match else None,
            "tasks": tasks[:20],
            "task_count": len(tasks),
            "status_details": _extract_status_details(page),
            "runtime": _detect_runtime(project_path),
            "git": _git_status(project_path),
        }
        enriched.append(item)

    return enriched


def load_project(vault_root: Path, project_id: str) -> Optional[Dict[str, Any]]:
    for project in load_projects(vault_root):
        if project["id"] == project_id or project["note_slug"] == project_id:
            return project
    return None


def load_all_project_tasks(vault_root: Path) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    for project in load_projects(vault_root):
        for task in project["tasks"]:
            tasks.append(
                {
                    "project_id": project["id"],
                    "project": project["title"],
                    "note_path": project["note_path"],
                    "task": task,
                    "status": project["status"],
                }
            )
    return tasks
