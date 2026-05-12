"""Project health and verification command detection."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List


SAFE_COMMAND_PREFIXES = (
    "npm run ",
    "npm test",
    "python -m unittest",
    "python3 -m unittest",
    "pytest",
    "ruff check",
    "cargo check",
    "cargo test",
    "flutter analyze",
    "flutter test",
)


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}


def _git_lines(root: Path, args: List[str], timeout: int = 4) -> List[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception:
        return []
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def detect_verification_commands(root: Path) -> List[Dict[str, str]]:
    commands: List[Dict[str, str]] = []
    package_json = root / "package.json"
    if package_json.exists():
        scripts = _read_json(package_json).get("scripts") or {}
        if "build" in scripts:
            commands.append({"command": "npm run build", "reason": "Node build script"})
        if "test" in scripts:
            commands.append({"command": "npm test", "reason": "Node test script"})
        if "lint" in scripts:
            commands.append({"command": "npm run lint", "reason": "Node lint script"})

    if (root / "Cargo.toml").exists():
        commands.append({"command": "cargo check", "reason": "Rust compile check"})
        commands.append({"command": "cargo test", "reason": "Rust tests"})

    if (root / "pubspec.yaml").exists():
        commands.append({"command": "flutter analyze", "reason": "Flutter static analysis"})
        commands.append({"command": "flutter test", "reason": "Flutter tests"})

    if (root / "pyproject.toml").exists() or (root / "requirements.txt").exists():
        if (root / "tests").exists():
            commands.append({"command": "python -m unittest discover -s tests", "reason": "Python tests folder"})
        if (root / "pyproject.toml").exists():
            commands.append({"command": "ruff check .", "reason": "Python lint candidate"})

    seen = set()
    unique = []
    for item in commands:
        if item["command"] in seen:
            continue
        seen.add(item["command"])
        unique.append(item)
    return unique


def is_safe_verification_command(command: str) -> bool:
    normalized = " ".join(command.strip().split())
    if any(token in normalized for token in (";", "&&", "||", "|", ">", "<", "`", "$(")):
        return False
    return any(normalized == prefix.rstrip() or normalized.startswith(prefix) for prefix in SAFE_COMMAND_PREFIXES)


def build_project_health(root: Path) -> Dict[str, Any]:
    checks = {
        "readme": (root / "README.md").exists(),
        "gitignore": (root / ".gitignore").exists(),
        "tests": (root / "tests").exists() or (root / "test").exists(),
        "ci": (root / ".github" / "workflows").exists(),
        "env_example": (root / ".env.example").exists(),
        "docs": (root / "docs").exists(),
    }
    git_status = _git_lines(root, ["status", "--short", "--branch"])
    dirty = max(len(git_status) - 1, 0) if git_status else 0
    commands = detect_verification_commands(root)

    score = 100
    missing = [name for name, ok in checks.items() if not ok]
    score -= min(len(missing) * 8, 36)
    score -= min(dirty * 3, 24)
    if not commands:
        score -= 16

    recommendations = []
    if missing:
        recommendations.append(f"Add or verify: {', '.join(missing)}.")
    if dirty:
        recommendations.append("Review local git changes before broad AI execution.")
    if not commands:
        recommendations.append("Add standard verification scripts for this project.")

    return {
        "score": max(score, 0),
        "checks": checks,
        "missing": missing,
        "git_dirty": dirty,
        "git_branch": git_status[0].replace("##", "").strip() if git_status else "",
        "verification_commands": commands,
        "recommendations": recommendations,
    }
