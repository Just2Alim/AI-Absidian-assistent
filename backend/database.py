"""
ObsidianAI — Database Layer
SQLite for operational data + DuckDB for analytics
"""

import sqlite3
import duckdb
import json
import time
import uuid
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import asyncio
import aiosqlite

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

SQLITE_PATH = DATA_DIR / "obsidian_ai.db"
DUCKDB_PATH = DATA_DIR / "analytics.duckdb"


# ─────────────────────────────────────────────
# SQLite — Operational Database
# ─────────────────────────────────────────────

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id          TEXT PRIMARY KEY,
    path        TEXT UNIQUE NOT NULL,
    title       TEXT,
    folder      TEXT,
    created_at  INTEGER,
    modified_at INTEGER,
    word_count  INTEGER DEFAULT 0,
    char_count  INTEGER DEFAULT 0,
    tags        TEXT DEFAULT '[]',
    frontmatter TEXT DEFAULT '{}',
    checksum    TEXT,
    is_orphan   INTEGER DEFAULT 0,
    vault_path  TEXT
);

CREATE INDEX IF NOT EXISTS idx_notes_path ON notes(path);
CREATE INDEX IF NOT EXISTS idx_notes_folder ON notes(folder);
CREATE INDEX IF NOT EXISTS idx_notes_modified ON notes(modified_at);

CREATE VIRTUAL TABLE IF NOT EXISTS note_fts USING fts5(
    note_id UNINDEXED,
    title,
    path,
    folder,
    tags,
    body,
    tokenize = 'unicode61'
);

CREATE TABLE IF NOT EXISTS links (
    id          TEXT PRIMARY KEY,
    source_id   TEXT NOT NULL,
    target_id   TEXT,
    target_path TEXT,
    link_text   TEXT,
    link_type   TEXT DEFAULT 'wikilink',
    FOREIGN KEY (source_id) REFERENCES notes(id)
);

CREATE INDEX IF NOT EXISTS idx_links_source ON links(source_id);
CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_id);

CREATE TABLE IF NOT EXISTS action_requests (
    id           TEXT PRIMARY KEY,
    action_type  TEXT NOT NULL,
    title        TEXT NOT NULL,
    summary      TEXT,
    status       TEXT DEFAULT 'pending',
    payload      TEXT DEFAULT '{}',
    diff_preview TEXT DEFAULT '',
    result       TEXT DEFAULT '{}',
    error        TEXT,
    created_by   TEXT DEFAULT 'assistant',
    created_at   INTEGER,
    updated_at   INTEGER,
    approved_at  INTEGER,
    applied_at   INTEGER
);

CREATE INDEX IF NOT EXISTS idx_action_requests_status ON action_requests(status);
CREATE INDEX IF NOT EXISTS idx_action_requests_created ON action_requests(created_at);

CREATE TABLE IF NOT EXISTS audit_log (
    id          TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id   TEXT,
    action      TEXT NOT NULL,
    summary     TEXT,
    payload     TEXT DEFAULT '{}',
    created_at  INTEGER
);

CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at);

CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    root_note_id TEXT,
    status      TEXT DEFAULT 'active',
    color       TEXT DEFAULT '#7C6FE0',
    description TEXT,
    created_at  INTEGER,
    updated_at  INTEGER,
    metadata    TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    note_id     TEXT NOT NULL,
    project_id  TEXT,
    content     TEXT NOT NULL,
    status      TEXT DEFAULT 'todo',
    priority    TEXT DEFAULT 'normal',
    due_date    TEXT,
    line_number INTEGER,
    created_at  INTEGER,
    completed_at INTEGER,
    FOREIGN KEY (note_id) REFERENCES notes(id)
);

CREATE TABLE IF NOT EXISTS conversations (
    id          TEXT PRIMARY KEY,
    title       TEXT,
    model       TEXT,
    provider    TEXT DEFAULT 'claude',
    created_at  INTEGER,
    updated_at  INTEGER,
    note_context TEXT DEFAULT '[]',
    metadata    TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS messages (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    tokens_used     INTEGER DEFAULT 0,
    created_at      INTEGER,
    metadata        TEXT DEFAULT '{}',
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE TABLE IF NOT EXISTS vault_config (
    key   TEXT PRIMARY KEY,
    value TEXT,
    updated_at INTEGER
);

CREATE TABLE IF NOT EXISTS embeddings (
    note_id   TEXT PRIMARY KEY,
    vector    BLOB,
    model     TEXT,
    created_at INTEGER,
    FOREIGN KEY (note_id) REFERENCES notes(id)
);
"""


async def init_sqlite():
    """Initialize SQLite database with schema."""
    async with aiosqlite.connect(SQLITE_PATH) as db:
        await db.executescript(SQLITE_SCHEMA)
        await db.commit()
    print(f"[DB] SQLite initialized at {SQLITE_PATH}")


async def get_db():
    """Async context manager for SQLite connection."""
    async with aiosqlite.connect(SQLITE_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db


# ─────────────────────────────────────────────
# DuckDB — Analytics Database
# ─────────────────────────────────────────────

DUCKDB_SCHEMA = """
CREATE TABLE IF NOT EXISTS writing_events (
    ts           TIMESTAMP NOT NULL,
    note_id      TEXT NOT NULL,
    note_path    TEXT,
    words_added  INTEGER DEFAULT 0,
    words_deleted INTEGER DEFAULT 0,
    session_id   TEXT
);

CREATE TABLE IF NOT EXISTS daily_stats (
    stat_date        DATE PRIMARY KEY,
    notes_created    INTEGER DEFAULT 0,
    notes_modified   INTEGER DEFAULT 0,
    notes_deleted    INTEGER DEFAULT 0,
    words_written    INTEGER DEFAULT 0,
    words_deleted    INTEGER DEFAULT 0,
    ai_interactions  INTEGER DEFAULT 0,
    active_projects  INTEGER DEFAULT 0,
    tasks_completed  INTEGER DEFAULT 0,
    links_created    INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS vault_snapshots (
    snapshot_ts      TIMESTAMP NOT NULL,
    total_notes      INTEGER,
    total_words      INTEGER,
    total_links      INTEGER,
    total_tags       INTEGER,
    orphan_count     INTEGER,
    avg_word_count   DOUBLE
);

CREATE TABLE IF NOT EXISTS ai_usage (
    ts           TIMESTAMP NOT NULL,
    provider     TEXT,
    model        TEXT,
    tokens_in    INTEGER DEFAULT 0,
    tokens_out   INTEGER DEFAULT 0,
    cost_usd     DOUBLE DEFAULT 0,
    session_id   TEXT
);
"""


def init_duckdb():
    """Initialize DuckDB analytics database."""
    con = duckdb.connect(str(DUCKDB_PATH))
    con.execute(DUCKDB_SCHEMA)
    con.close()
    print(f"[DB] DuckDB initialized at {DUCKDB_PATH}")


def get_analytics_db():
    """Get DuckDB connection for analytics."""
    return duckdb.connect(str(DUCKDB_PATH))


# ─────────────────────────────────────────────
# Note CRUD Operations
# ─────────────────────────────────────────────

async def upsert_note(note_data: Dict[str, Any]) -> str:
    """Insert or update a note record."""
    async with aiosqlite.connect(SQLITE_PATH) as db:
        note_id = note_data.get("id") or str(uuid.uuid4())
        await db.execute("""
            INSERT INTO notes (id, path, title, folder, created_at, modified_at,
                word_count, char_count, tags, frontmatter, checksum, is_orphan, vault_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                title       = excluded.title,
                folder      = excluded.folder,
                modified_at = excluded.modified_at,
                word_count  = excluded.word_count,
                char_count  = excluded.char_count,
                tags        = excluded.tags,
                frontmatter = excluded.frontmatter,
                checksum    = excluded.checksum
        """, (
            note_id,
            note_data["path"],
            note_data.get("title", ""),
            note_data.get("folder", ""),
            note_data.get("created_at", int(time.time())),
            note_data.get("modified_at", int(time.time())),
            note_data.get("word_count", 0),
            note_data.get("char_count", 0),
            json.dumps(note_data.get("tags", [])),
            json.dumps(note_data.get("frontmatter", {})),
            note_data.get("checksum", ""),
            0,
            note_data.get("vault_path", "")
        ))
        await db.execute("DELETE FROM note_fts WHERE note_id = ?", (note_id,))
        await db.execute("""
            INSERT INTO note_fts (note_id, title, path, folder, tags, body)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            note_id,
            note_data.get("title", ""),
            note_data.get("path", ""),
            note_data.get("folder", ""),
            " ".join(note_data.get("tags", [])),
            note_data.get("body", ""),
        ))
        await db.commit()
    return note_id


async def delete_note_index(note_id: str):
    async with aiosqlite.connect(SQLITE_PATH) as db:
        await db.execute("DELETE FROM note_fts WHERE note_id = ?", (note_id,))
        await db.execute("DELETE FROM links WHERE source_id = ? OR target_id = ?", (note_id, note_id))
        await db.execute("DELETE FROM tasks WHERE note_id = ?", (note_id,))
        await db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        await db.commit()


async def clear_note_relations():
    async with aiosqlite.connect(SQLITE_PATH) as db:
        await db.execute("DELETE FROM links")
        await db.execute("DELETE FROM tasks")
        await db.commit()


async def replace_note_links(source_id: str, links: List[Dict[str, Any]]):
    async with aiosqlite.connect(SQLITE_PATH) as db:
        await db.execute("DELETE FROM links WHERE source_id = ?", (source_id,))
        for link in links:
            await db.execute("""
                INSERT INTO links (id, source_id, target_id, target_path, link_text, link_type)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()),
                source_id,
                link.get("target_id"),
                link.get("target_path"),
                link.get("link_text", ""),
                link.get("link_type", "wikilink"),
            ))
        await db.commit()


async def replace_note_tasks(note_id: str, tasks: List[Dict[str, Any]]):
    async with aiosqlite.connect(SQLITE_PATH) as db:
        await db.execute("DELETE FROM tasks WHERE note_id = ?", (note_id,))
        now = int(time.time())
        for task in tasks:
            await db.execute("""
                INSERT INTO tasks (
                    id, note_id, content, status, priority, due_date,
                    line_number, created_at, completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()),
                note_id,
                task.get("content", ""),
                task.get("status", "todo"),
                task.get("priority", "normal"),
                task.get("due_date"),
                task.get("line_number"),
                now,
                now if task.get("status") == "done" else None,
            ))
        await db.commit()


async def get_all_notes(limit: int = 1000, offset: int = 0) -> List[Dict]:
    """Fetch all indexed notes."""
    async with aiosqlite.connect(SQLITE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM notes ORDER BY modified_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def search_notes(query: str, limit: int = 20) -> List[Dict]:
    """Full-text search over title, tags, folder and note body."""
    tokens = re.findall(r"[\w\u0400-\u04FF/-]+", query or "")
    fts_query = " ".join(f"{token}*" for token in tokens[:8])
    async with aiosqlite.connect(SQLITE_PATH) as db:
        db.row_factory = aiosqlite.Row
        if fts_query:
            try:
                cursor = await db.execute("""
                    SELECT
                        n.*,
                        snippet(note_fts, 5, '<mark>', '</mark>', '...', 28) AS snippet,
                        bm25(note_fts) AS rank
                    FROM note_fts
                    JOIN notes n ON n.id = note_fts.note_id
                    WHERE note_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """, (fts_query, limit))
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]
            except sqlite3.OperationalError:
                pass

        cursor = await db.execute("""
            SELECT * FROM notes
            WHERE title LIKE ? OR tags LIKE ? OR folder LIKE ?
            ORDER BY modified_at DESC
            LIMIT ?
        """, (f"%{query}%", f"%{query}%", f"%{query}%", limit))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_note_documents(limit: int = 2000) -> List[Dict[str, Any]]:
    """Return indexed note text for RAG-style ranking."""
    async with aiosqlite.connect(SQLITE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT
                n.id, n.path, n.title, n.folder, n.modified_at, n.word_count,
                n.tags, f.body
            FROM notes n
            LEFT JOIN note_fts f ON f.note_id = n.id
            ORDER BY n.modified_at DESC
            LIMIT ?
        """, (limit,))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_vault_stats() -> Dict[str, Any]:
    """Get aggregate vault statistics."""
    async with aiosqlite.connect(SQLITE_PATH) as db:
        db.row_factory = aiosqlite.Row

        stats_cur = await db.execute("""
            SELECT
                COUNT(*) as total_notes,
                SUM(word_count) as total_words,
                SUM(char_count) as total_chars,
                AVG(word_count) as avg_words,
                COUNT(DISTINCT folder) as total_folders,
                SUM(is_orphan) as orphan_notes
            FROM notes
        """)
        stats = dict(await stats_cur.fetchone())

        tags_cur = await db.execute("""
            SELECT tags FROM notes WHERE tags != '[]'
        """)
        all_tags = set()
        async for row in tags_cur:
            try:
                for t in json.loads(row[0]):
                    all_tags.add(t)
            except Exception:
                pass
        stats["total_tags"] = len(all_tags)

        links_cur = await db.execute("SELECT COUNT(*) FROM links")
        row = await links_cur.fetchone()
        stats["total_links"] = row[0]

        return stats


async def save_vault_config(key: str, value: str):
    async with aiosqlite.connect(SQLITE_PATH) as db:
        await db.execute("""
            INSERT INTO vault_config (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """, (key, value, int(time.time())))
        await db.commit()


async def get_vault_config(key: str) -> Optional[str]:
    async with aiosqlite.connect(SQLITE_PATH) as db:
        cur = await db.execute("SELECT value FROM vault_config WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row[0] if row else None


# ─────────────────────────────────────────────
# Approval Queue / Audit Log
# ─────────────────────────────────────────────

def _parse_json_field(row: Dict[str, Any], field: str, fallback):
    try:
        row[field] = json.loads(row.get(field) or "")
    except Exception:
        row[field] = fallback
    return row


async def create_action_request(
    action_type: str,
    title: str,
    summary: str,
    payload: Dict[str, Any],
    diff_preview: str = "",
    created_by: str = "assistant",
) -> Dict[str, Any]:
    action_id = str(uuid.uuid4())
    now = int(time.time())
    async with aiosqlite.connect(SQLITE_PATH) as db:
        await db.execute("""
            INSERT INTO action_requests (
                id, action_type, title, summary, status, payload, diff_preview,
                created_by, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)
        """, (
            action_id,
            action_type,
            title,
            summary,
            json.dumps(payload, ensure_ascii=False),
            diff_preview,
            created_by,
            now,
            now,
        ))
        await db.commit()
    return await get_action_request(action_id)


async def get_action_request(action_id: str) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(SQLITE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM action_requests WHERE id = ?", (action_id,))
        row = await cur.fetchone()
        if not row:
            return None
        data = dict(row)
        _parse_json_field(data, "payload", {})
        _parse_json_field(data, "result", {})
        return data


async def list_action_requests(status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(SQLITE_PATH) as db:
        db.row_factory = aiosqlite.Row
        if status:
            cur = await db.execute("""
                SELECT * FROM action_requests
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (status, limit))
        else:
            cur = await db.execute("""
                SELECT * FROM action_requests
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
        rows = await cur.fetchall()
        result = []
        for row in rows:
            data = dict(row)
            _parse_json_field(data, "payload", {})
            _parse_json_field(data, "result", {})
            result.append(data)
        return result


async def set_action_status(action_id: str, status: str, error: Optional[str] = None):
    now = int(time.time())
    approved_at = now if status == "approved" else None
    async with aiosqlite.connect(SQLITE_PATH) as db:
        await db.execute("""
            UPDATE action_requests
            SET status = ?,
                error = ?,
                approved_at = COALESCE(?, approved_at),
                updated_at = ?
            WHERE id = ?
        """, (status, error, approved_at, now, action_id))
        await db.commit()


async def mark_action_applied(action_id: str, result: Dict[str, Any]):
    now = int(time.time())
    async with aiosqlite.connect(SQLITE_PATH) as db:
        await db.execute("""
            UPDATE action_requests
            SET status = 'applied',
                result = ?,
                applied_at = ?,
                updated_at = ?
            WHERE id = ?
        """, (json.dumps(result, ensure_ascii=False), now, now, action_id))
        await db.commit()


async def record_audit_log(
    entity_type: str,
    entity_id: Optional[str],
    action: str,
    summary: str,
    payload: Optional[Dict[str, Any]] = None,
):
    async with aiosqlite.connect(SQLITE_PATH) as db:
        await db.execute("""
            INSERT INTO audit_log (id, entity_type, entity_id, action, summary, payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()),
            entity_type,
            entity_id,
            action,
            summary,
            json.dumps(payload or {}, ensure_ascii=False),
            int(time.time()),
        ))
        await db.commit()


async def get_audit_log(limit: int = 100) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(SQLITE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT * FROM audit_log
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        rows = await cur.fetchall()
        result = []
        for row in rows:
            data = dict(row)
            _parse_json_field(data, "payload", {})
            result.append(data)
        return result


# ─────────────────────────────────────────────
# Analytics Operations
# ─────────────────────────────────────────────

def record_writing_event(note_id: str, note_path: str, words_added: int, words_deleted: int = 0):
    """Log a writing event to DuckDB."""
    con = get_analytics_db()
    try:
        con.execute("""
            INSERT INTO writing_events (ts, note_id, note_path, words_added, words_deleted)
            VALUES (NOW(), ?, ?, ?, ?)
        """, [note_id, note_path, words_added, words_deleted])
    finally:
        con.close()


def record_snapshot(stats: Dict[str, Any]):
    """Save a vault snapshot for trend tracking."""
    con = get_analytics_db()
    try:
        con.execute("""
            INSERT INTO vault_snapshots
                (snapshot_ts, total_notes, total_words, total_links, total_tags, orphan_count, avg_word_count)
            VALUES (NOW(), ?, ?, ?, ?, ?, ?)
        """, [
            stats.get("total_notes", 0),
            stats.get("total_words", 0),
            stats.get("total_links", 0),
            stats.get("total_tags", 0),
            stats.get("orphan_notes", 0),
            stats.get("avg_words", 0)
        ])
    finally:
        con.close()


def get_activity_heatmap(days: int = 365) -> List[Dict]:
    """Get writing activity for heatmap."""
    con = get_analytics_db()
    try:
        result = con.execute(f"""
            SELECT
                CAST(ts AS DATE) as day,
                COUNT(*) as events,
                SUM(words_added) as words
            FROM writing_events
            WHERE ts >= NOW() - INTERVAL '{days}' DAY
            GROUP BY CAST(ts AS DATE)
            ORDER BY day
        """).fetchall()
        return [{"day": str(r[0]), "events": r[1], "words": r[2]} for r in result]
    finally:
        con.close()


def get_growth_trend(days: int = 30) -> List[Dict]:
    """Get vault growth over time."""
    con = get_analytics_db()
    try:
        result = con.execute(f"""
            SELECT
                snapshot_ts::DATE as day,
                total_notes,
                total_words,
                total_links
            FROM vault_snapshots
            WHERE snapshot_ts >= NOW() - INTERVAL '{days}' DAY
            ORDER BY snapshot_ts
        """).fetchall()
        return [{"day": str(r[0]), "notes": r[1], "words": r[2], "links": r[3]} for r in result]
    finally:
        con.close()


async def init_databases():
    """Initialize all databases."""
    await init_sqlite()
    init_duckdb()
    print("[DB] All databases ready ✅")
