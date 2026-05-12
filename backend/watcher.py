"""
ObsidianAI — File System Watcher
Real-time monitoring of vault changes using watchdog.
"""

import asyncio
import time
import json
from pathlib import Path
from typing import Callable, Optional, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent


class VaultEventHandler(FileSystemEventHandler):
    def __init__(self, loop: asyncio.AbstractEventLoop, callback: Callable):
        super().__init__()
        self.loop = loop
        self.callback = callback
        self._debounce: dict[str, float] = {}
        self._debounce_delay = 0.5  # seconds

    def _should_process(self, path: str) -> bool:
        """Debounce — ignore rapid successive events for same file."""
        now = time.time()
        last = self._debounce.get(path, 0)
        if now - last < self._debounce_delay:
            return False
        self._debounce[path] = now
        return True

    def _emit(self, event_type: str, path: str):
        if not path.endswith(".md"):
            return
        if any(part.startswith(".") for part in Path(path).parts):
            return
        if not self._should_process(path):
            return

        event_data = {
            "type": event_type,
            "path": path,
            "timestamp": int(time.time()),
        }
        asyncio.run_coroutine_threadsafe(self.callback(event_data), self.loop)

    def on_created(self, event: FileSystemEvent):
        if not event.is_directory:
            self._emit("created", event.src_path)

    def on_modified(self, event: FileSystemEvent):
        if not event.is_directory:
            self._emit("modified", event.src_path)

    def on_deleted(self, event: FileSystemEvent):
        if not event.is_directory:
            self._emit("deleted", event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self._emit("moved", f"{event.src_path} -> {event.dest_path}")


class VaultWatcher:
    def __init__(self):
        self._observer: Optional[Observer] = None
        self._vault_path: Optional[str] = None
        self._ws_clients: Set = set()

    def start(self, vault_path: str, loop: asyncio.AbstractEventLoop, event_callback: Callable):
        """Start watching a vault directory."""
        if self._observer and self._observer.is_alive():
            self._observer.stop()
            self._observer.join()

        self._vault_path = vault_path
        handler = VaultEventHandler(loop, event_callback)
        self._observer = Observer()
        self._observer.schedule(handler, vault_path, recursive=True)
        self._observer.start()
        print(f"[WATCHER] Watching vault: {vault_path}")

    def stop(self):
        if self._observer and self._observer.is_alive():
            self._observer.stop()
            self._observer.join()
            print("[WATCHER] Stopped watching vault")

    @property
    def is_running(self) -> bool:
        return self._observer is not None and self._observer.is_alive()


# Global watcher singleton
vault_watcher = VaultWatcher()
