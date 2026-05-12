"""Workspace context packs for AI prompts and UI previews."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from project_intelligence import load_projects


MARKER_FILES = (
    ("package.json", "Node.js"),
    ("pyproject.toml", "Python"),
    ("requirements.txt", "Python"),
    ("pubspec.yaml", "Flutter"),
    ("Cargo.toml", "Rust"),
    ("docker-compose.yml", "Docker Compose"),
    ("compose.yml", "Docker Compose"),
    ("firebase.json", "Firebase"),
)

IMPORTANT_FILES = (
    "CLAUDE.md",
    "README.md",
    "AGENTS.md",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "pubspec.yaml",
    "Cargo.toml",
    "vite.config.js",
    "docker-compose.yml",
)


def _run_git(path: Path, args: List[str], timeout: int = 4) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _file_tree(root: Path, limit: int = 90) -> List[str]:
    ignored = {".git", "node_modules", "target", "dist", ".venv", "__pycache__", ".next"}
    items: List[str] = []
    for path in sorted(root.rglob("*"), key=lambda item: str(item).lower()):
        rel = path.relative_to(root)
        if any(part in ignored for part in rel.parts):
            continue
        depth = len(rel.parts)
        if depth > 3:
            continue
        suffix = "/" if path.is_dir() else ""
        items.append(f"{rel}{suffix}")
        if len(items) >= limit:
            break
    return items


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}


def _runtime_summary(root: Path) -> Dict[str, Any]:
    signals = [label for filename, label in MARKER_FILES if (root / filename).exists()]
    package = _read_json(root / "package.json") if (root / "package.json").exists() else {}
    scripts = package.get("scripts") if isinstance(package.get("scripts"), dict) else {}
    dependencies = []
    for key in ("dependencies", "devDependencies"):
        section = package.get(key)
        if isinstance(section, dict):
            dependencies.extend(section.keys())
    return {
        "signals": sorted(set(signals)),
        "scripts": sorted(scripts.keys())[:16],
        "dependencies": sorted(set(dependencies))[:24],
    }


def _git_summary(root: Path) -> Dict[str, Any]:
    top = _run_git(root, ["rev-parse", "--show-toplevel"])
    if not top:
        return {"available": False, "reason": "Not a git repository"}
    status = _run_git(root, ["status", "--short", "--branch"]) or ""
    lines = [line for line in status.splitlines() if line.strip()]
    return {
        "available": True,
        "root": top,
        "branch": lines[0].replace("##", "").strip() if lines else "",
        "changes": lines[1:21],
        "dirty": max(len(lines) - 1, 0),
    }


def _matching_project(vault_root: Path, workspace: Path) -> Optional[Dict[str, Any]]:
    workspace_resolved = workspace.resolve()
    for project in load_projects(vault_root):
        raw_path = project.get("path")
        if not raw_path:
            continue
        try:
            project_path = Path(raw_path).resolve()
        except Exception:
            continue
        if project_path == workspace_resolved:
            return project
    return None


def _important_file_excerpt(root: Path, filename: str, char_limit: int = 1200) -> Optional[str]:
    path = root / filename
    if not path.exists() or not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return None
    return text[:char_limit]


def build_workspace_context_pack(vault_root: Path, workspace: Path) -> Dict[str, Any]:
    workspace = workspace.resolve()
    project = _matching_project(vault_root, workspace)
    runtime = _runtime_summary(workspace)
    git = _git_summary(workspace)
    important = [
        {
            "path": filename,
            "excerpt": excerpt,
        }
        for filename in IMPORTANT_FILES
        if (excerpt := _important_file_excerpt(workspace, filename))
    ][:5]

    risks = []
    if git.get("dirty"):
        risks.append("Workspace has local git changes. Avoid broad rewrites until reviewed.")
    if not project:
        risks.append("Workspace is not mapped to a vault project note.")
    if not runtime["signals"]:
        risks.append("No runtime markers detected at workspace root.")

    instructions = [
        f"Work only inside: {workspace}",
        "Use Obsidian vault context before proposing project actions.",
        "Create file changes only through pending approval actions.",
        "Prefer existing scripts and repository conventions.",
    ]

    return {
        "workspace": str(workspace),
        "project": project,
        "runtime": runtime,
        "git": git,
        "tree": _file_tree(workspace),
        "important_files": important,
        "risks": risks,
        "instructions": instructions,
    }


def context_pack_prompt(pack: Dict[str, Any]) -> str:
    project = pack.get("project") or {}
    runtime = pack.get("runtime") or {}
    git = pack.get("git") or {}
    files = ", ".join(item["path"] for item in pack.get("important_files", [])) or "none"
    tree = "\n".join(f"- {item}" for item in pack.get("tree", [])[:40])
    risks = "\n".join(f"- {item}" for item in pack.get("risks", [])) or "- No immediate risks detected."
    tasks = "\n".join(f"- {task}" for task in (project.get("tasks") or [])[:8]) or "- No mapped project tasks."
    return f"""
Workspace context pack:
Workspace: {pack.get('workspace')}
Mapped vault project: {project.get('title') or 'not mapped'}
Project note: {project.get('note_path') or 'none'}
Stack from vault: {project.get('stack') or 'unknown'}
Runtime signals: {', '.join(runtime.get('signals') or []) or 'none'}
Available package scripts: {', '.join(runtime.get('scripts') or []) or 'none'}
Git: {git.get('branch') or git.get('reason') or 'unknown'}; dirty files: {git.get('dirty', 0)}
Important files present: {files}

Open project tasks:
{tasks}

Current risks:
{risks}

Top workspace tree:
{tree}
"""
