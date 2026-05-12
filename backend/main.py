"""
ObsidianAI — FastAPI Backend
Main application entry point with all API routes.
"""

import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import (
    init_databases, get_vault_stats, get_all_notes, search_notes,
    save_vault_config, get_vault_config, get_activity_heatmap, get_growth_trend,
    record_snapshot, upsert_note, replace_note_links, replace_note_tasks,
    list_action_requests, get_action_request, get_audit_log
)
from vault_manager import get_indexer, set_indexer, VaultIndexer
from ai_engine import ai_engine, PROVIDERS
from watcher import vault_watcher
from action_manager import approve_action, propose_action, reject_action
from project_intelligence import load_all_project_tasks, load_project, load_projects

# ─────────────────────────────────────────────
# App Setup
# ─────────────────────────────────────────────

app = FastAPI(
    title="ObsidianAI API",
    description="Intelligent Obsidian Vault Manager",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

ws_manager = ConnectionManager()


# ─────────────────────────────────────────────
# Startup / Shutdown
# ─────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    await init_databases()
    # Restore saved vault path
    vault_path = (
        await get_vault_config("vault_path")
        or os.environ.get("OBSIDIAN_AI_VAULT")
        or "/Users/justalim/projects/obsidian-vault"
    )
    if vault_path and Path(vault_path).expanduser().exists():
        indexer = set_indexer(vault_path)
        loop = asyncio.get_event_loop()
        vault_watcher.start(vault_path, loop, on_vault_change)
        print(f"[APP] Auto-loaded vault: {vault_path}")

    # Restore AI API keys
    for provider in PROVIDERS:
        key = await get_vault_config(f"api_key_{provider}")
        if key:
            ai_engine.configure(provider, key)
            print(f"[APP] Restored {provider} API key")


@app.on_event("shutdown")
async def shutdown():
    vault_watcher.stop()


async def on_vault_change(event: dict):
    """Called when vault files change — broadcast to all WS clients."""
    # Re-index changed file
    indexer = get_indexer()
    if indexer and event["type"] in ("created", "modified"):
        fp = Path(event["path"])
        if fp.exists() and fp.suffix == ".md":
            from vault_manager import parse_note
            note = parse_note(fp, indexer.vault_root)
            if note:
                await upsert_note(note)
                await replace_note_links(note["id"], [
                    {
                        "target_id": None,
                        "target_path": None,
                        "link_text": link,
                        "link_type": "wikilink",
                    }
                    for link in note.get("links", [])
                ])
                await replace_note_tasks(note["id"], note.get("tasks", []))

    await ws_manager.broadcast({"event": "vault_change", "data": event})


# ─────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────

class VaultSetupRequest(BaseModel):
    vault_path: str

class APIKeyRequest(BaseModel):
    provider: str
    api_key: str

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    provider: str = "ollama"
    model: str = "llama3:latest"
    vault_context: Optional[str] = None
    include_vault_context: bool = True

class CreateNoteRequest(BaseModel):
    folder: str = ""
    title: str
    content: str
    tags: List[str] = []

class UpdateNoteRequest(BaseModel):
    path: str
    content: str

class RenameNoteRequest(BaseModel):
    old_path: str
    new_name: str

class ActionProposalRequest(BaseModel):
    action_type: str
    payload: Dict[str, Any]
    title: Optional[str] = None
    summary: Optional[str] = None
    created_by: str = "assistant"

class RejectActionRequest(BaseModel):
    reason: str = ""

class RemoteTaskRequest(BaseModel):
    task: str


# ─────────────────────────────────────────────
# Routes — Health & Config
# ─────────────────────────────────────────────

@app.get("/api/health")
async def health():
    indexer = get_indexer()
    ollama_models = await ai_engine.list_ollama_models()
    return {
        "status": "ok",
        "vault_loaded": indexer is not None,
        "vault_path": str(indexer.vault_root) if indexer else None,
        "watcher_running": vault_watcher.is_running,
        "local_ai": {
            "provider": "ollama",
            "reachable": bool(ollama_models),
            "models": ollama_models,
            "recommended": "qwen3:14b",
            "installed_fallback": "llama3:latest",
        },
        "timestamp": int(time.time()),
    }


@app.post("/api/config/vault")
async def setup_vault(req: VaultSetupRequest, background_tasks: BackgroundTasks):
    """Set vault path and trigger full index."""
    vault_path = Path(req.vault_path).expanduser().resolve()
    if not vault_path.exists():
        raise HTTPException(400, f"Path does not exist: {vault_path}")

    indexer = set_indexer(str(vault_path))
    await save_vault_config("vault_path", str(vault_path))

    # Start watcher
    loop = asyncio.get_event_loop()
    vault_watcher.start(str(vault_path), loop, on_vault_change)

    # Full index in background
    background_tasks.add_task(run_full_index, indexer)

    return {"status": "ok", "vault_path": str(vault_path), "indexing": True}


@app.post("/api/config/apikey")
async def set_api_key(req: APIKeyRequest):
    """Save API key for a provider."""
    if req.provider not in PROVIDERS:
        raise HTTPException(400, f"Unknown provider: {req.provider}")
    ai_engine.configure(req.provider, req.api_key)
    await save_vault_config(f"api_key_{req.provider}", req.api_key)
    return {"status": "ok", "provider": req.provider}


@app.get("/api/config/providers")
async def get_providers():
    return PROVIDERS


@app.get("/api/config/ollama/models")
async def get_ollama_models():
    models = await ai_engine.list_ollama_models()
    return {
        "models": models,
        "recommended": "qwen3:14b",
        "fallback": "llama3:latest",
        "install_hint": "ollama pull qwen3:14b",
    }


async def run_full_index(indexer: VaultIndexer):
    async def progress_cb(data):
        await ws_manager.broadcast({"event": "index_progress", "data": data})

    stats = await indexer.index_all(progress_cb)
    await ws_manager.broadcast({"event": "index_complete", "data": stats})

    # Save snapshot to DuckDB
    vault_stats = await get_vault_stats()
    record_snapshot(vault_stats)
    print(f"[APP] Full index complete: {stats}")


# ─────────────────────────────────────────────
# Routes — Vault & Notes
# ─────────────────────────────────────────────

@app.post("/api/vault/index")
async def trigger_index(background_tasks: BackgroundTasks):
    indexer = get_indexer()
    if not indexer:
        raise HTTPException(400, "Vault not configured")
    background_tasks.add_task(run_full_index, indexer)
    return {"status": "indexing"}


@app.get("/api/vault/stats")
async def vault_stats():
    stats = await get_vault_stats()
    return stats


def _current_vault_root() -> Path:
    indexer = get_indexer()
    if indexer:
        return indexer.vault_root
    return Path("/Users/justalim/projects/obsidian-vault")


@app.get("/api/projects")
async def projects():
    return {"projects": load_projects(_current_vault_root())}


@app.get("/api/projects/tasks")
async def project_tasks():
    return {"tasks": load_all_project_tasks(_current_vault_root())}


@app.get("/api/projects/{project_id}")
async def project_detail(project_id: str):
    project = load_project(_current_vault_root(), project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return {"project": project}


@app.get("/api/notes")
async def list_notes(limit: int = 200, offset: int = 0):
    notes = await get_all_notes(limit, offset)
    return {"notes": notes, "total": len(notes)}


@app.get("/api/notes/search")
async def search(q: str, limit: int = 20):
    results = await search_notes(q, limit)
    return {"results": results, "query": q}


@app.get("/api/notes/content")
async def get_note_content(path: str):
    indexer = get_indexer()
    if not indexer:
        raise HTTPException(400, "Vault not configured")
    content = indexer.read_note_content(path)
    if content is None:
        raise HTTPException(404, "Note not found")
    return {"path": path, "content": content}


@app.post("/api/notes")
async def create_note(req: CreateNoteRequest):
    indexer = get_indexer()
    if not indexer:
        raise HTTPException(400, "Vault not configured")

    fm = {"created": time.strftime("%Y-%m-%d")}
    if req.tags:
        fm["tags"] = req.tags

    action = await propose_action(
        "create_note",
        {
            "folder": req.folder,
            "title": req.title,
            "content": req.content,
            "frontmatter": fm,
        },
        indexer=indexer,
        created_by="api",
    )
    return {"status": "pending_approval", "action": action}


@app.put("/api/notes")
async def update_note(req: UpdateNoteRequest):
    indexer = get_indexer()
    if not indexer:
        raise HTTPException(400, "Vault not configured")
    action = await propose_action(
        "update_note",
        {"path": req.path, "content": req.content},
        indexer=indexer,
        created_by="api",
    )
    return {"status": "pending_approval", "action": action}


@app.delete("/api/notes")
async def delete_note(path: str):
    indexer = get_indexer()
    if not indexer:
        raise HTTPException(400, "Vault not configured")
    action = await propose_action(
        "delete_note",
        {"path": path},
        indexer=indexer,
        created_by="api",
    )
    return {"status": "pending_approval", "action": action}


@app.put("/api/notes/rename")
async def rename_note(req: RenameNoteRequest):
    indexer = get_indexer()
    if not indexer:
        raise HTTPException(400, "Vault not configured")
    action = await propose_action(
        "rename_note",
        {"old_path": req.old_path, "new_name": req.new_name},
        indexer=indexer,
        created_by="api",
    )
    return {"status": "pending_approval", "action": action}


# ─────────────────────────────────────────────
# Routes — Approval Queue / Safe Actions
# ─────────────────────────────────────────────

@app.post("/api/actions")
async def create_action(req: ActionProposalRequest):
    indexer = get_indexer()
    try:
        action = await propose_action(
            req.action_type,
            req.payload,
            indexer=indexer,
            title=req.title,
            summary=req.summary,
            created_by=req.created_by,
        )
        return {"status": "pending_approval", "action": action}
    except Exception as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/actions")
async def actions(status: Optional[str] = None, limit: int = 50):
    return {"actions": await list_action_requests(status, limit)}


@app.get("/api/actions/{action_id}")
async def action_detail(action_id: str):
    action = await get_action_request(action_id)
    if not action:
        raise HTTPException(404, "Action not found")
    return {"action": action}


@app.post("/api/actions/{action_id}/approve")
async def approve(action_id: str):
    indexer = get_indexer()
    try:
        action = await approve_action(action_id, indexer)
        return {"status": "applied", "action": action}
    except Exception as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/actions/{action_id}/reject")
async def reject(action_id: str, req: RejectActionRequest):
    try:
        action = await reject_action(action_id, req.reason)
        return {"status": "rejected", "action": action}
    except Exception as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/audit")
async def audit(limit: int = 100):
    return {"items": await get_audit_log(limit)}


# ─────────────────────────────────────────────
# Routes — Obsidian Mobile Remote Inbox
# ─────────────────────────────────────────────

def _remote_inbox_path() -> Path:
    indexer = get_indexer()
    vault_root = indexer.vault_root if indexer else Path("~/projects/obsidian-vault").expanduser()
    return vault_root / "inbox" / "remote-tasks.md"


@app.get("/api/remote/tasks")
async def get_remote_tasks():
    inbox = _remote_inbox_path()
    content = inbox.read_text(encoding="utf-8", errors="ignore") if inbox.exists() else ""
    return {"path": str(inbox), "content": content}


@app.post("/api/remote/tasks")
async def add_remote_task(req: RemoteTaskRequest):
    inbox = _remote_inbox_path()
    inbox.parent.mkdir(parents=True, exist_ok=True)
    if not inbox.exists():
        inbox.write_text("# Remote Tasks\n\n", encoding="utf-8")
    with inbox.open("a", encoding="utf-8") as f:
        f.write(f"- [ ] {req.task.strip()}\n")
    return {"status": "queued", "path": str(inbox), "task": req.task.strip()}


# ─────────────────────────────────────────────
# Routes — Knowledge Graph
# ─────────────────────────────────────────────

@app.get("/api/graph")
async def get_graph():
    indexer = get_indexer()
    if not indexer:
        raise HTTPException(400, "Vault not configured")
    return indexer.get_graph_data()


@app.get("/api/graph/clusters")
async def get_clusters():
    indexer = get_indexer()
    if not indexer:
        raise HTTPException(400, "Vault not configured")
    return {"clusters": indexer.get_clusters()}


@app.get("/api/graph/hubs")
async def get_hubs(n: int = 10):
    indexer = get_indexer()
    if not indexer:
        raise HTTPException(400, "Vault not configured")
    return {"hubs": indexer.get_top_connected(n)}


@app.get("/api/graph/orphans")
async def get_orphans():
    indexer = get_indexer()
    if not indexer:
        raise HTTPException(400, "Vault not configured")
    return {"orphans": indexer.get_orphans()}


# ─────────────────────────────────────────────
# Routes — Analytics
# ─────────────────────────────────────────────

@app.get("/api/analytics/heatmap")
async def heatmap(days: int = 365):
    return {"heatmap": get_activity_heatmap(days)}


@app.get("/api/analytics/growth")
async def growth(days: int = 30):
    return {"growth": get_growth_trend(days)}


# ─────────────────────────────────────────────
# Routes — AI Chat
# ─────────────────────────────────────────────

@app.post("/api/ai/chat/stream")
async def chat_stream(req: ChatRequest):
    """Server-Sent Events streaming chat endpoint."""
    indexer = get_indexer()
    vault_context = ""

    if req.include_vault_context and indexer:
        stats = await get_vault_stats()
        recent = await get_all_notes(limit=10)
        vault_context = f"""
Vault: {str(indexer.vault_root)}
Total notes: {stats.get('total_notes', 0)}
Total words: {stats.get('total_words', 0)}
Recent notes: {', '.join([n.get('title','') for n in recent[:5]])}
"""

    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    async def generate():
        async for chunk in ai_engine.stream_chat(
            provider=req.provider,
            model=req.model,
            messages=messages,
            vault_context=vault_context,
        ):
            yield f"data: {json.dumps({'text': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/ai/daily-brief")
async def daily_brief(provider: str = "ollama", model: str = "llama3:latest"):
    stats = await get_vault_stats()
    recent = await get_all_notes(limit=5)
    brief = await ai_engine.generate_daily_brief(stats, recent, provider, model)
    return {"brief": brief, "generated_at": int(time.time())}


# ─────────────────────────────────────────────
# WebSocket — Real-time events
# ─────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        # Send initial state
        stats = await get_vault_stats()
        await ws.send_json({"event": "connected", "data": stats})
        while True:
            data = await ws.receive_text()
            # Handle ping
            if data == "ping":
                await ws.send_json({"event": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8765, reload=True)
