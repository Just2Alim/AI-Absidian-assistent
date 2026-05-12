"""
ObsidianAI — Vault Manager
Reads, parses and indexes Obsidian vault markdown files.
"""

import os
import re
import json
import time
import uuid
import hashlib
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
import frontmatter
import networkx as nx

from database import (
    upsert_note, get_all_notes, get_vault_config, save_vault_config,
    clear_note_relations, replace_note_links, replace_note_tasks
)


# ─────────────────────────────────────────────
# Markdown Parser
# ─────────────────────────────────────────────

WIKILINK_RE  = re.compile(r'\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]')
TAG_RE       = re.compile(r'(?<!\S)#([a-zA-Z\u0400-\u04FF][a-zA-Z0-9\u0400-\u04FF_/-]*)')
TASK_RE      = re.compile(r'^(\s*)- \[([ xX\-/])\]\s+(.+)$', re.MULTILINE)
HEADING_RE   = re.compile(r'^#{1,6}\s+(.+)$', re.MULTILINE)
CODE_BLOCK   = re.compile(r'```[\s\S]*?```', re.MULTILINE)
PROTECTED_WRITE_PREFIXES = ("raw/",)
PROTECTED_WRITE_FILES = {"CLAUDE.md"}
IGNORED_INDEX_PARTS = {
    ".obsidian",
    ".trash",
    ".git",
    ".obsidian-ai",
    "__pycache__",
    "node_modules",
    "agent-env",
}


def parse_note(file_path: Path, vault_root: Path) -> Dict[str, Any]:
    """Parse a single markdown file into structured data."""
    try:
        raw = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {}

    checksum = hashlib.md5(raw.encode()).hexdigest()

    # Parse frontmatter
    try:
        post = frontmatter.loads(raw)
        meta = dict(post.metadata)
        body = post.content
    except Exception:
        meta = {}
        body = raw

    # Strip code blocks before counting words/tags
    clean_body = CODE_BLOCK.sub("", body)

    # Extract inline tags
    inline_tags = TAG_RE.findall(clean_body)
    fm_tags = meta.get("tags", meta.get("tag", []))
    if isinstance(fm_tags, str):
        fm_tags = [t.strip() for t in fm_tags.split(",")]
    all_tags = list(set(inline_tags + (fm_tags if isinstance(fm_tags, list) else [])))

    # Word count
    words = len(clean_body.split())
    chars = len(clean_body)

    # Wikilinks
    links = WIKILINK_RE.findall(clean_body)

    # Headings
    headings = HEADING_RE.findall(clean_body)

    # Tasks
    tasks = []
    for line_number, line in enumerate(raw.splitlines(), start=1):
        m = re.match(r'^(\s*)- \[([ xX\-/])\]\s+(.+)$', line)
        if not m:
            continue
        indent, status_char, content = m.group(1), m.group(2), m.group(3)
        status = "done" if status_char.lower() == "x" else "todo"
        tasks.append({
            "content": content.strip(),
            "status": status,
            "indent": len(indent),
            "line_number": line_number,
        })

    # Title: frontmatter > first H1 > filename
    title = (
        meta.get("title")
        or (headings[0] if headings else None)
        or file_path.stem
    )

    relative_path = str(file_path.relative_to(vault_root))
    folder = str(file_path.parent.relative_to(vault_root)) if file_path.parent != vault_root else ""

    stat = file_path.stat()

    return {
        "id":          hashlib.sha1(relative_path.encode()).hexdigest()[:16],
        "path":        relative_path,
        "vault_path":  str(vault_root),
        "title":       str(title),
        "folder":      folder,
        "created_at":  int(stat.st_birthtime if hasattr(stat, 'st_birthtime') else stat.st_ctime),
        "modified_at": int(stat.st_mtime),
        "word_count":  words,
        "char_count":  chars,
        "tags":        all_tags,
        "frontmatter": meta,
        "checksum":    checksum,
        "links":       links,
        "headings":    headings,
        "tasks":       tasks,
        "body":        body,
        "excerpt":     clean_body[:500],
        "raw_length":  len(raw),
    }


# ─────────────────────────────────────────────
# Vault Indexer
# ─────────────────────────────────────────────

class VaultIndexer:
    def __init__(self, vault_path: str):
        self.vault_root = Path(vault_path).expanduser().absolute()
        self.notes_cache: Dict[str, Dict] = {}
        self.graph: nx.DiGraph = nx.DiGraph()

    def _is_indexable(self, path: Path) -> bool:
        try:
            relative = path.relative_to(self.vault_root)
        except ValueError:
            return False
        if any(part in IGNORED_INDEX_PARTS or part.startswith(".") for part in relative.parts):
            return False
        return path.suffix == ".md"

    def _safe_path(self, relative_path: str) -> Path:
        rel = Path(relative_path)
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError("Vault paths must stay inside the configured vault")
        full_path = self.vault_root / rel
        return full_path

    def _ensure_writable(self, relative_path: str):
        normalized = Path(relative_path).as_posix().lstrip("/")
        if normalized in PROTECTED_WRITE_FILES:
            raise PermissionError(f"{normalized} is protected and cannot be changed by actions")
        if any(normalized.startswith(prefix) for prefix in PROTECTED_WRITE_PREFIXES):
            raise PermissionError(f"{normalized} is in a protected vault area")

    def backup_file(self, relative_path: str) -> Optional[str]:
        full_path = self._safe_path(relative_path)
        if not full_path.exists():
            return None
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup_path = self.vault_root / ".obsidian-ai" / "backups" / stamp / relative_path
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(full_path, backup_path)
        return str(backup_path.relative_to(self.vault_root))

    def find_all_notes(self) -> List[Path]:
        """Find all markdown files in vault."""
        return [
            p for p in self.vault_root.rglob("*.md")
            if self._is_indexable(p)
        ]

    async def index_all(self, progress_cb=None) -> Dict[str, Any]:
        """Full vault index scan."""
        files = self.find_all_notes()
        total = len(files)
        indexed = 0
        errors = 0

        self.graph.clear()
        all_notes = {}

        for i, fp in enumerate(files):
            try:
                note = parse_note(fp, self.vault_root)
                if not note:
                    continue

                await upsert_note(note)
                all_notes[note["path"]] = note
                self.graph.add_node(note["id"], **{
                    "title": note["title"],
                    "path": note["path"],
                    "word_count": note["word_count"],
                    "tags": note["tags"],
                    "folder": note["folder"],
                })
                indexed += 1

                if progress_cb and i % 10 == 0:
                    await progress_cb({"indexed": indexed, "total": total, "current": fp.name})

            except Exception as e:
                errors += 1
                print(f"[VAULT] Error parsing {fp}: {e}")

        await clear_note_relations()

        # Build link graph and DB relations
        for path, note in all_notes.items():
            db_links = []
            for link_target in note.get("links", []):
                target = self._resolve_link(link_target, all_notes)
                if target:
                    self.graph.add_edge(note["id"], target["id"], label=link_target)
                db_links.append({
                    "target_id": target["id"] if target else None,
                    "target_path": target["path"] if target else None,
                    "link_text": link_target,
                    "link_type": "wikilink",
                })
            await replace_note_links(note["id"], db_links)
            await replace_note_tasks(note["id"], note.get("tasks", []))

        # Mark orphans (no in/out edges)
        self.notes_cache = all_notes

        stats = {
            "total": total,
            "indexed": indexed,
            "errors": errors,
            "graph_nodes": self.graph.number_of_nodes(),
            "graph_edges": self.graph.number_of_edges(),
        }
        print(f"[VAULT] Indexed {indexed}/{total} notes, {errors} errors")
        return stats

    def _resolve_link(self, link_text: str, all_notes: Dict) -> Optional[Dict]:
        """Try to find a note matching a wikilink."""
        link_clean = link_text.strip().lower()
        for path, note in all_notes.items():
            stem = Path(path).stem.lower()
            if stem == link_clean or path.lower() == link_clean + ".md":
                return note
        return None

    def get_graph_data(self) -> Dict[str, Any]:
        """Export graph as nodes/edges for frontend visualization."""
        nodes = []
        for node_id, data in self.graph.nodes(data=True):
            degree = self.graph.degree(node_id)
            nodes.append({
                "id": node_id,
                "label": data.get("title", node_id),
                "path": data.get("path", ""),
                "folder": data.get("folder", ""),
                "tags": data.get("tags", []),
                "wordCount": data.get("word_count", 0),
                "degree": degree,
                "size": min(max(degree * 3 + 5, 5), 40),
            })

        edges = []
        for src, tgt, data in self.graph.edges(data=True):
            edges.append({
                "source": src,
                "target": tgt,
                "label": data.get("label", ""),
            })

        return {"nodes": nodes, "edges": edges}

    def get_clusters(self) -> List[Dict]:
        """Detect note clusters via connected components."""
        undirected = self.graph.to_undirected()
        clusters = []
        for i, component in enumerate(nx.connected_components(undirected)):
            sub = undirected.subgraph(component)
            clusters.append({
                "id": i,
                "size": len(component),
                "nodes": list(component),
                "density": nx.density(sub),
            })
        return sorted(clusters, key=lambda c: c["size"], reverse=True)

    def get_top_connected(self, n: int = 10) -> List[Dict]:
        """Get most connected (hub) notes."""
        degrees = sorted(self.graph.degree(), key=lambda x: x[1], reverse=True)[:n]
        result = []
        for node_id, deg in degrees:
            data = self.graph.nodes.get(node_id, {})
            result.append({
                "id": node_id,
                "title": data.get("title", node_id),
                "path": data.get("path", ""),
                "connections": deg,
                "in_links": self.graph.in_degree(node_id),
                "out_links": self.graph.out_degree(node_id),
            })
        return result

    def get_orphans(self) -> List[Dict]:
        """Get notes with no links at all."""
        result = []
        for node_id, data in self.graph.nodes(data=True):
            if self.graph.degree(node_id) == 0:
                result.append({
                    "id": node_id,
                    "title": data.get("title", node_id),
                    "path": data.get("path", ""),
                    "folder": data.get("folder", ""),
                })
        return result

    def read_note_content(self, relative_path: str) -> Optional[str]:
        """Read full markdown content of a note."""
        full_path = self._safe_path(relative_path)
        if full_path.exists():
            return full_path.read_text(encoding="utf-8", errors="ignore")
        return None

    def write_note_content(self, relative_path: str, content: str) -> bool:
        """Write content to a note (create if not exists)."""
        self._ensure_writable(relative_path)
        full_path = self._safe_path(relative_path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return True

    def create_note(self, folder: str, filename: str, content: str, frontmatter_data: Dict = None) -> str:
        """Create a new note with optional frontmatter."""
        filename = sanitize_note_filename(filename)
        if frontmatter_data:
            fm_lines = ["---"]
            for k, v in frontmatter_data.items():
                if isinstance(v, list):
                    fm_lines.append(f"{k}: {json.dumps(v)}")
                else:
                    fm_lines.append(f"{k}: {v}")
            fm_lines.append("---")
            fm_lines.append("")
            full_content = "\n".join(fm_lines) + content
        else:
            full_content = content

        rel_path = f"{folder}/{filename}" if folder else filename
        if not rel_path.endswith(".md"):
            rel_path += ".md"

        self.write_note_content(rel_path, full_content)
        return rel_path

    def delete_note(self, relative_path: str) -> bool:
        """Move note to trash folder."""
        self._ensure_writable(relative_path)
        full_path = self._safe_path(relative_path)
        if not full_path.exists():
            return False
        trash = self.vault_root / ".trash"
        trash.mkdir(exist_ok=True)
        full_path.rename(trash / full_path.name)
        return True

    def rename_note(self, old_path: str, new_name: str) -> str:
        """Rename a note file."""
        self._ensure_writable(old_path)
        old_full = self._safe_path(old_path)
        clean_name = sanitize_note_filename(new_name)
        new_full = old_full.parent / (clean_name if clean_name.endswith(".md") else clean_name + ".md")
        old_full.rename(new_full)
        return str(new_full.relative_to(self.vault_root))


# Global indexer instance (singleton)
_indexer: Optional[VaultIndexer] = None


def get_indexer() -> Optional[VaultIndexer]:
    return _indexer


def set_indexer(vault_path: str) -> VaultIndexer:
    global _indexer
    _indexer = VaultIndexer(vault_path)
    return _indexer


def sanitize_note_filename(filename: str) -> str:
    """Keep Obsidian-friendly filenames while removing path separators."""
    name = filename.strip().replace("\\", "-").replace("/", "-")
    name = re.sub(r'[:*?"<>|]+', "-", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name or "Untitled"
