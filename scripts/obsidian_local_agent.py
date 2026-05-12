#!/usr/bin/env python3
"""
Obsidian mobile bridge for local AI.

Flow:
1. User adds "- [ ] task" to inbox/remote-tasks.md from Obsidian mobile.
2. This script sends the task plus vault context to Ollama.
3. READ blocks are resolved locally in a bounded safe loop.
4. FILE blocks become backend action requests and wait for user approval.

No AI-generated file write is applied directly by this script.
"""

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List

import httpx


PROJECTS_ROOT = (Path.home() / "projects").resolve()
DEFAULT_VAULT = PROJECTS_ROOT / "obsidian-vault"
DEFAULT_BACKEND = "http://127.0.0.1:8765"
DEFAULT_OLLAMA = "http://127.0.0.1:11434"

SYSTEM_PROMPT = """
Ты локальный AI-агент ObsidianAI на Mac пользователя Lim.
Пользователь может ставить задачи с телефона через Obsidian.

Правила безопасности:
- Никогда не утверждай, что файл изменён, пока не создан pending action.
- Если нужен файл, запроси чтение блоком: === READ: ~/projects/path/file.ext ===
- Если хочешь создать или обновить файл, выведи блок:
=== FILE: ~/projects/path/file.ext ===
полное содержимое файла
=== END ===
- FILE блоки НЕ применяются сразу. Они попадут в очередь подтверждений.
- Для заметок Obsidian используй markdown и wikilinks [[note]].
- Отвечай по-русски, коротко фиксируй результат и следующие действия.
"""


READ_PATTERN = re.compile(r"=== READ:\s*(.*?)\s*===", re.DOTALL)
FILE_PATTERN = re.compile(r"=== FILE:\s*(.*?)\s*===\n(.*?)=== END ===", re.DOTALL)


def safe_project_path(raw_path: str) -> Path:
    path = Path(raw_path.strip()).expanduser().resolve()
    path.relative_to(PROJECTS_ROOT)
    if ".git" in path.parts:
        raise PermissionError("Direct .git writes are blocked")
    return path


def read_text(path: Path, limit: int = 40_000) -> str:
    data = path.read_text(encoding="utf-8", errors="ignore")
    return data[:limit] + ("\n\n[TRUNCATED]" if len(data) > limit else "")


def load_context(vault: Path) -> str:
    chunks = []
    for rel in ("CLAUDE.md", "wiki/quick-context.md", "wiki/INDEX.md"):
        path = vault / rel
        if path.exists():
            chunks.append(f"\n--- {rel} ---\n{read_text(path, 18_000)}")

    md_files = []
    for path in vault.rglob("*.md"):
        try:
            rel = path.relative_to(vault)
        except ValueError:
            continue
        if any(part.startswith(".") or part == "agent-env" for part in rel.parts):
            continue
        md_files.append(str(rel))
        if len(md_files) >= 160:
            break
    chunks.append("\n--- VAULT MAP ---\n" + "\n".join(md_files))
    return "\n".join(chunks)


def ollama_chat(ollama_url: str, model: str, messages: List[Dict[str, str]]) -> str:
    with httpx.Client(timeout=None) as client:
        response = client.post(
            f"{ollama_url.rstrip('/')}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.2, "num_ctx": 8192},
            },
        )
        response.raise_for_status()
        return response.json()["message"]["content"]


def resolve_reads(answer: str) -> str:
    blocks = []
    for raw_path in sorted(set(READ_PATTERN.findall(answer))):
        try:
            path = safe_project_path(raw_path)
            if not path.exists():
                blocks.append(f"\n--- READ ERROR: {raw_path} ---\nFile not found")
                continue
            blocks.append(f"\n--- READ RESULT: {raw_path} ---\n{read_text(path)}")
        except Exception as exc:
            blocks.append(f"\n--- READ ERROR: {raw_path} ---\n{exc}")
    return "\n".join(blocks)


def submit_file_actions(backend_url: str, answer: str) -> List[Dict]:
    created = []
    with httpx.Client(timeout=30) as client:
        for raw_path, content in FILE_PATTERN.findall(answer):
            path = safe_project_path(raw_path)
            response = client.post(
                f"{backend_url.rstrip('/')}/api/actions",
                json={
                    "action_type": "write_file",
                    "payload": {
                        "path": str(path),
                        "content": content.strip() + "\n",
                    },
                    "title": f"Remote AI write: {path.name}",
                    "summary": f"AI proposed writing {path} from Obsidian remote task.",
                    "created_by": "obsidian-local-agent",
                },
            )
            response.raise_for_status()
            created.append(response.json()["action"])
    return created


def clean_answer(answer: str, actions: List[Dict]) -> str:
    answer = READ_PATTERN.sub(lambda m: f"*(прочитал: `{m.group(1).strip()}`)*", answer)
    answer = FILE_PATTERN.sub(lambda m: f"*(предложил изменение файла: `{m.group(1).strip()}`)*", answer)
    if actions:
        answer += "\n\n**Ожидают подтверждения:**\n"
        for action in actions:
            answer += f"- `{action['id']}` — {action['title']}\n"
    return answer.strip()


def process_task(task: str, vault: Path, backend_url: str, ollama_url: str, model: str) -> str:
    context = load_context(vault)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + context},
        {"role": "user", "content": task},
    ]

    answer = ollama_chat(ollama_url, model, messages)
    for _ in range(3):
        read_results = resolve_reads(answer)
        if not read_results:
            break
        messages.append({"role": "assistant", "content": answer})
        messages.append({"role": "user", "content": read_results + "\n\nПродолжай задачу."})
        answer = ollama_chat(ollama_url, model, messages)

    actions = submit_file_actions(backend_url, answer)
    return clean_answer(answer, actions)


def process_inbox_once(vault: Path, backend_url: str, ollama_url: str, model: str) -> bool:
    inbox = vault / "inbox" / "remote-tasks.md"
    inbox.parent.mkdir(parents=True, exist_ok=True)
    if not inbox.exists():
        inbox.write_text("# Remote Tasks\n\n", encoding="utf-8")

    lines = inbox.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)
    for index, line in enumerate(lines):
        if not line.startswith("- [ ] "):
            continue

        task = line[6:].strip()
        if not task:
            continue

        print(f"[agent] task: {task}")
        lines[index] = f"- [~] {task} (local AI is thinking...)\n"
        inbox.write_text("".join(lines), encoding="utf-8")

        try:
            result = process_task(task, vault, backend_url, ollama_url, model)
            status = "?"
            footer = "\n\n---\n"
        except Exception as exc:
            result = f"**Ошибка:** {exc}"
            status = "!"
            footer = "\n\n---\n"

        fresh = inbox.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)
        for j, fresh_line in enumerate(fresh):
            if fresh_line.startswith(f"- [~] {task}"):
                fresh[j] = f"- [{status}] {task}\n\n**Local AI:**\n{result}{footer}"
                break
        inbox.write_text("".join(fresh), encoding="utf-8")
        return True

    return False


def main():
    parser = argparse.ArgumentParser(description="Run the ObsidianAI local mobile bridge")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT))
    parser.add_argument("--backend", default=DEFAULT_BACKEND)
    parser.add_argument("--ollama", default=DEFAULT_OLLAMA)
    parser.add_argument("--model", default=os.environ.get("OBSIDIAN_AI_MODEL", "llama3:latest"))
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    vault = Path(args.vault).expanduser().resolve()
    print(f"[agent] vault: {vault}")
    print(f"[agent] model: {args.model}")
    print(f"[agent] backend: {args.backend}")

    while True:
        processed = process_inbox_once(vault, args.backend, args.ollama, args.model)
        if args.once:
            break
        time.sleep(0.1 if processed else args.interval)


if __name__ == "__main__":
    main()
