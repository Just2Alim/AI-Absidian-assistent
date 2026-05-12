"""
ObsidianAI — AI Engine
Multi-provider: Claude (Anthropic), Gemini (Google), OpenAI
"""

import json
import time
import uuid
from typing import List, Dict, Optional, Any, AsyncGenerator
from pathlib import Path
import anthropic
import httpx
from openai import AsyncOpenAI

from database import get_vault_config


# ─────────────────────────────────────────────
# Provider Configuration
# ─────────────────────────────────────────────

PROVIDERS = {
    "claude": {
        "models": [
            "claude-sonnet-4-5",
            "claude-3-5-haiku-20241022",
            "claude-opus-4-5",
        ],
        "default": "claude-sonnet-4-5"
    },
    "gemini": {
        "models": [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-2.0-flash-exp",
        ],
        "default": "gemini-2.5-flash"
    },
    "openai": {
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
        "default": "gpt-4o"
    },
    "ollama": {
        "models": [
            "qwen3:latest",
            "qwen3:14b",
            "qwen3:8b",
            "llama3.1:8b",
            "llama3:latest",
        ],
        "default": "qwen3:latest",
        "base_url": "http://127.0.0.1:11434",
    }
}

# System prompt — the core of ObsidianAI's personality
SYSTEM_PROMPT = """You are ObsidianAI — an expert knowledge management assistant and project implementation partner.

You have full access to the user's Obsidian vault. Your capabilities:

## What you can do:
- **READ**: Access and analyze any note, folder, tag, or link in the vault
- **WRITE**: Create new notes, update existing ones, add tasks, modify frontmatter
- **ORGANIZE**: Suggest folder structures, tag taxonomies, note templates
- **ANALYZE**: Find connections between ideas, detect orphan notes, suggest links
- **PLAN**: Break down projects into tasks, create roadmaps, estimate timelines
- **SUMMARIZE**: Distill long notes, create MOC (Maps of Content), daily briefings
- **WORKSPACE-SAFE**: Never choose a random filesystem directory. Use the active working directory from context for file work, and ask for a workspace switch when the target project is different.

## Your personality:
- Proactive: anticipate what the user needs next
- Precise: give concrete, actionable answers
- Structured: use markdown formatting in responses
- Context-aware: reference specific notes by name when relevant

## Response format:
- Use **bold** for key points
- Use `code blocks` for note paths and technical content
- Always suggest follow-up actions when relevant
- When creating/modifying notes, show the content you're writing

## Available tools (function calls):
You can call these tools to interact with the vault:
- `read_note(path)` — read a note's content
- `search_notes(query)` — search for notes
- `create_note(folder, title, content)` — create a new note
- `update_note(path, content)` — update a note
- `list_folder(folder)` — list notes in a folder
- `get_tasks(status)` — get tasks from all notes
- `get_stats()` — vault statistics

Always be helpful, precise, and proactive."""


# ─────────────────────────────────────────────
# Tool Definitions (for function calling)
# ─────────────────────────────────────────────

TOOLS = [
    {
        "name": "read_note",
        "description": "Read the full content of a specific note by its relative path in the vault",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path to the note (e.g. 'Projects/MyProject.md')"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "search_notes",
        "description": "Search for notes by keyword, tag, or content",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max results", "default": 10}
            },
            "required": ["query"]
        }
    },
    {
        "name": "create_note",
        "description": "Create a new note in the vault",
        "input_schema": {
            "type": "object",
            "properties": {
                "folder": {"type": "string", "description": "Folder path (empty for root)"},
                "title": {"type": "string", "description": "Note title (becomes filename)"},
                "content": {"type": "string", "description": "Markdown content of the note"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags for frontmatter"}
            },
            "required": ["title", "content"]
        }
    },
    {
        "name": "update_note",
        "description": "Update (overwrite) the content of an existing note",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "list_folder",
        "description": "List all notes in a specific folder",
        "input_schema": {
            "type": "object",
            "properties": {
                "folder": {"type": "string", "description": "Folder path (empty for root)"}
            },
            "required": ["folder"]
        }
    },
    {
        "name": "get_stats",
        "description": "Get current vault statistics (note count, word count, etc.)",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
]


# ─────────────────────────────────────────────
# AI Engine
# ─────────────────────────────────────────────

class AIEngine:
    def __init__(self):
        self._claude_client: Optional[anthropic.AsyncAnthropic] = None
        self._openai_client: Optional[AsyncOpenAI] = None
        self._gemini_configured = False
        self._ollama_base_url = "http://127.0.0.1:11434"

    def configure(self, provider: str, api_key: str):
        if provider == "claude":
            self._claude_client = anthropic.AsyncAnthropic(api_key=api_key)
        elif provider == "gemini":
            import google.generativeai as genai

            genai.configure(api_key=api_key)
            self._gemini_configured = True
        elif provider == "openai":
            self._openai_client = AsyncOpenAI(api_key=api_key)
        elif provider == "ollama":
            self._ollama_base_url = api_key.rstrip("/") if api_key else self._ollama_base_url

    # ─── Claude ─────────────────────────────

    async def chat_claude(
        self,
        messages: List[Dict],
        model: str,
        vault_context: str = "",
        tool_handler=None,
    ) -> AsyncGenerator[str, None]:
        """Stream chat with Claude, with tool use support."""
        if not self._claude_client:
            yield "[ERROR] Claude API key not configured"
            return

        system = SYSTEM_PROMPT
        if vault_context:
            system += f"\n\n## Current Vault Context:\n{vault_context}"

        # Format messages for Anthropic API
        anthropic_msgs = []
        for m in messages:
            anthropic_msgs.append({"role": m["role"], "content": m["content"]})

        try:
            async with self._claude_client.messages.stream(
                model=model,
                max_tokens=8096,
                system=system,
                messages=anthropic_msgs,
                tools=TOOLS,
            ) as stream:
                async for event in stream:
                    if hasattr(event, 'type'):
                        if event.type == 'content_block_delta':
                            delta = event.delta
                            if hasattr(delta, 'text'):
                                yield delta.text
                        elif event.type == 'content_block_start':
                            block = event.content_block
                            if block.type == 'tool_use' and tool_handler:
                                # Will be handled after stream
                                pass

            # Handle tool calls from final message
            final = await stream.get_final_message()
            for block in final.content:
                if block.type == "tool_use" and tool_handler:
                    tool_result = await tool_handler(block.name, block.input)
                    yield f"\n\n**[Tool: {block.name}]**\n{tool_result}"

        except Exception as e:
            yield f"\n[ERROR] {str(e)}"

    # ─── Gemini ─────────────────────────────

    async def chat_gemini(
        self,
        messages: List[Dict],
        model: str,
        vault_context: str = "",
    ) -> AsyncGenerator[str, None]:
        """Stream chat with Gemini."""
        if not self._gemini_configured:
            yield "[ERROR] Gemini API key not configured"
            return

        try:
            import google.generativeai as genai

            gem_model = genai.GenerativeModel(
                model_name=model,
                system_instruction=SYSTEM_PROMPT + (f"\n\nVault Context:\n{vault_context}" if vault_context else "")
            )

            history = []
            for m in messages[:-1]:
                role = "user" if m["role"] == "user" else "model"
                history.append({"role": role, "parts": [m["content"]]})

            chat = gem_model.start_chat(history=history)
            last_msg = messages[-1]["content"]

            response = await chat.send_message_async(last_msg, stream=True)
            async for chunk in response:
                if chunk.text:
                    yield chunk.text

        except Exception as e:
            yield f"\n[ERROR] {str(e)}"

    # ─── OpenAI ─────────────────────────────

    async def chat_openai(
        self,
        messages: List[Dict],
        model: str,
        vault_context: str = "",
    ) -> AsyncGenerator[str, None]:
        """Stream chat with OpenAI."""
        if not self._openai_client:
            yield "[ERROR] OpenAI API key not configured"
            return

        system_msg = {"role": "system", "content": SYSTEM_PROMPT}
        if vault_context:
            system_msg["content"] += f"\n\nVault Context:\n{vault_context}"

        all_msgs = [system_msg] + messages

        try:
            async with await self._openai_client.chat.completions.create(
                model=model,
                messages=all_msgs,
                stream=True,
                max_tokens=8096,
            ) as stream:
                async for chunk in stream:
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
        except Exception as e:
            yield f"\n[ERROR] {str(e)}"

    # ─── Ollama / Local AI ───────────────────

    async def list_ollama_models(self) -> List[str]:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                res = await client.get(f"{self._ollama_base_url}/api/tags")
                res.raise_for_status()
                data = res.json()
                return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        except Exception:
            return []

    async def chat_ollama(
        self,
        messages: List[Dict],
        model: str,
        vault_context: str = "",
    ) -> AsyncGenerator[str, None]:
        """Stream chat with a local Ollama model."""
        system = SYSTEM_PROMPT
        if vault_context:
            system += f"\n\n## Current Vault Context:\n{vault_context}"

        ollama_messages = [{"role": "system", "content": system}] + messages

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    f"{self._ollama_base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": ollama_messages,
                        "stream": True,
                        "options": {
                            "temperature": 0.2,
                            "num_ctx": 8192,
                        },
                    },
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        data = json.loads(line)
                        if data.get("message", {}).get("content"):
                            yield data["message"]["content"]
                        if data.get("done"):
                            break
        except httpx.ConnectError:
            yield "\n[ERROR] Ollama is not reachable at http://127.0.0.1:11434"
        except Exception as e:
            yield f"\n[ERROR] {str(e)}"

    # ─── Universal Dispatch ──────────────────

    async def stream_chat(
        self,
        provider: str,
        model: str,
        messages: List[Dict],
        vault_context: str = "",
        tool_handler=None,
    ) -> AsyncGenerator[str, None]:
        """Universal chat dispatcher."""
        if provider == "claude":
            async for chunk in self.chat_claude(messages, model, vault_context, tool_handler):
                yield chunk
        elif provider == "gemini":
            async for chunk in self.chat_gemini(messages, model, vault_context):
                yield chunk
        elif provider == "openai":
            async for chunk in self.chat_openai(messages, model, vault_context):
                yield chunk
        elif provider == "ollama":
            async for chunk in self.chat_ollama(messages, model, vault_context):
                yield chunk
        else:
            yield f"[ERROR] Unknown provider: {provider}"

    # ─── Utility ────────────────────────────

    async def generate_daily_brief(self, vault_stats: Dict, recent_notes: List[Dict], provider: str, model: str) -> str:
        """Generate an AI daily briefing about the vault."""
        context = f"""
Vault Stats: {json.dumps(vault_stats, indent=2)}
Recent Notes (last 5 modified): {json.dumps([n.get('title','') + ' (' + n.get('folder','root') + ')' for n in recent_notes[:5]], indent=2)}
Today: {time.strftime('%A, %B %d %Y')}
"""
        prompt = "Generate a concise daily briefing (max 200 words) about my knowledge base. Highlight notable patterns, suggest what to work on today, mention any orphan notes or areas needing attention."

        messages = [{"role": "user", "content": prompt}]
        result = ""
        async for chunk in self.stream_chat(provider, model, messages, context):
            result += chunk
        return result

    async def suggest_links(self, note_content: str, all_notes: List[Dict], provider: str, model: str) -> str:
        """Suggest relevant wikilinks for a note."""
        note_titles = [n.get("title", "") for n in all_notes[:50]]
        prompt = f"""Given this note content:
---
{note_content[:2000]}
---
And these existing notes in the vault: {json.dumps(note_titles)}

Suggest 3-5 relevant wikilinks I should add to this note. Format as: [[NoteTitle]] — reason why it's relevant."""

        messages = [{"role": "user", "content": prompt}]
        result = ""
        async for chunk in self.stream_chat(provider, model, messages):
            result += chunk
        return result


# Global AI engine singleton
ai_engine = AIEngine()
