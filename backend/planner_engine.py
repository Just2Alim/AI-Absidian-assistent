"""Execution planner for approval-first project work."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any, Dict, List

from ai_engine import ai_engine
from context_pack import build_workspace_context_pack, context_pack_prompt
from database import (
    create_execution_plan,
    create_execution_session,
    replace_execution_plan_steps,
    update_execution_session_status,
)
from learning_engine import build_learning_context
from project_health import detect_verification_commands


PLAN_TIMEOUT_SECONDS = 60

PLAN_SCHEMA = """
Return ONLY JSON, no markdown:
{
  "title": "short plan title",
  "summary": "what this plan will achieve",
  "risk_level": "low|medium|high",
  "steps": [
    {
      "title": "short step title",
      "objective": "what to do",
      "expected_result": "what should be true after the step",
      "files": ["relative/or/absolute/path"],
      "checks": ["safe verification command"],
      "risks": ["risk to review"],
      "approval_required": true
    }
  ]
}

Rules:
- Do not claim work is done.
- Create an execution plan only. File writes happen later through pending actions.
- Every step must be small, reviewable, and tied to the active workspace.
- Use safe checks such as npm run build, npm test, python -m unittest, cargo check, flutter analyze.
- If unsure, add an investigation step first.
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


def _fallback_plan(goal: str, workspace: Path) -> Dict[str, Any]:
    checks = [item["command"] for item in detect_verification_commands(workspace)[:4]]
    return {
        "title": "Controlled execution plan",
        "summary": "Fallback plan generated locally because the model did not return valid JSON in time.",
        "risk_level": "medium",
        "steps": [
            {
                "title": "Inspect current context",
                "objective": "Review workspace context, vault project note, git status and relevant files before editing.",
                "expected_result": "The assistant knows the active project boundaries and risks.",
                "files": [],
                "checks": [],
                "risks": ["Skipping context review can cause edits in the wrong project."],
                "approval_required": True,
            },
            {
                "title": "Prepare focused changes",
                "objective": f"Implement the requested goal inside {workspace}.",
                "expected_result": "Small pending actions are ready for user approval.",
                "files": [],
                "checks": checks,
                "risks": ["Generated changes still need diff review before approval."],
                "approval_required": True,
            },
            {
                "title": "Verify and summarize",
                "objective": "Run safe checks, summarize results, and save the session back into Obsidian.",
                "expected_result": "The user sees verification output and a saved session record.",
                "files": [],
                "checks": checks,
                "risks": [],
                "approval_required": True,
            },
        ],
    }


def _normalize_steps(raw_steps: Any, workspace: Path) -> List[Dict[str, Any]]:
    safe_checks = {item["command"] for item in detect_verification_commands(workspace)}
    steps = raw_steps if isinstance(raw_steps, list) else []
    normalized = []
    for index, step in enumerate(steps[:12], start=1):
        if not isinstance(step, dict):
            continue
        checks = step.get("checks") or []
        if isinstance(checks, str):
            checks = [checks]
        checks = [check for check in checks if isinstance(check, str)]
        approved_checks = [check for check in checks if check in safe_checks or any(check.startswith(prefix) for prefix in safe_checks)]
        normalized.append(
            {
                "title": step.get("title") or f"Step {index}",
                "objective": step.get("objective", ""),
                "expected_result": step.get("expected_result", ""),
                "files": step.get("files") if isinstance(step.get("files"), list) else [],
                "checks": approved_checks or checks[:4],
                "risks": step.get("risks") if isinstance(step.get("risks"), list) else [],
                "approval_required": bool(step.get("approval_required", True)),
            }
        )
    return normalized


async def propose_execution_plan(
    goal: str,
    vault_root: Path,
    workspace: Path,
    provider: str = "ollama",
    model: str = "qwen3:latest",
) -> Dict[str, Any]:
    context_pack = build_workspace_context_pack(vault_root, workspace)
    session = await create_execution_session(goal, str(workspace), provider, model, context_pack)
    learning_context = await build_learning_context(workspace)
    prompt = (
        f"{PLAN_SCHEMA}\n\n"
        f"{context_pack_prompt(context_pack)}\n\n"
        f"{learning_context}\n\n"
        f"User goal:\n{goal}"
    )

    messages = [{"role": "user", "content": prompt}]
    result_text = ""
    try:
        async with asyncio.timeout(PLAN_TIMEOUT_SECONDS):
            async for chunk in ai_engine.stream_chat(provider, model, messages, vault_context=prompt):
                result_text += chunk
        parsed = _extract_json(result_text)
    except Exception:
        parsed = _fallback_plan(goal, workspace)
        result_text = result_text or "Fallback plan generated locally."

    steps = _normalize_steps(parsed.get("steps"), workspace)
    if not steps:
        parsed = _fallback_plan(goal, workspace)
        steps = parsed["steps"]

    plan = await create_execution_plan(
        session_id=session["id"],
        title=parsed.get("title") or "Execution plan",
        summary=parsed.get("summary") or goal,
        risk_level=parsed.get("risk_level") or "medium",
        raw_model_output=result_text,
    )
    await replace_execution_plan_steps(plan["id"], steps)
    await update_execution_session_status(session["id"], "plan_ready", parsed.get("summary") or "")
    from database import get_execution_plan

    return {
        "session": await create_session_snapshot(session["id"]),
        "plan": await get_execution_plan(plan["id"]),
    }


async def create_session_snapshot(session_id: str) -> Dict[str, Any]:
    from database import get_execution_session

    session = await get_execution_session(session_id)
    return session or {"id": session_id}
