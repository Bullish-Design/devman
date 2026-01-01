"""Workspace indexing cache management."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

from devman.models import WorkspaceEntry, WorkspaceIndex

from . import scanner


DEFAULT_CACHE_DIRNAME = "devman"


def cache_dir() -> Path:
    """Return the cache directory for workspace index data."""
    base = os.environ.get("XDG_CACHE_HOME")
    if base:
        return Path(base).expanduser() / DEFAULT_CACHE_DIRNAME
    return Path.home() / ".cache" / DEFAULT_CACHE_DIRNAME


def index_cache_path() -> Path:
    """Return the path to the index cache file."""
    return cache_dir() / "index.json"


class IndexManager:
    """Manage the workspace index cache."""

    def __init__(self, cache_path: Path | None = None) -> None:
        self.cache_path = cache_path or index_cache_path()

    def load(self) -> WorkspaceIndex | None:
        """Load the index cache from disk."""
        if not self.cache_path.exists():
            return None
        payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        return WorkspaceIndex.from_dict(payload)

    def save(self, index: WorkspaceIndex) -> None:
        """Persist the index cache to disk."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(index.to_dict(), indent=2),
            encoding="utf-8",
        )

    def refresh(self, roots: Iterable[Path]) -> WorkspaceIndex:
        """Refresh the index using cache when possible."""
        resolved_roots = scanner.resolve_root_paths(roots)
        cached = self.load()
        if cached and self._is_valid(cached, resolved_roots):
            return cached
        return self.rebuild(resolved_roots)

    def rebuild(self, roots: Iterable[Path]) -> WorkspaceIndex:
        """Rebuild the index by scanning the provided roots."""
        resolved_roots = scanner.resolve_root_paths(roots)
        entries = scanner.scan_roots(resolved_roots)
        index = WorkspaceIndex(
            entries=entries,
            roots=resolved_roots,
            generated_at=scanner.timestamp(),
        )
        self.save(index)
        return index

    def find_entry(
        self, entries: Iterable[WorkspaceEntry], query: str
    ) -> WorkspaceEntry | None:
        """Find a workspace entry by name, tag, group, or path."""
        for entry in entries:
            if entry.matches(query):
                return entry
        return None

    def _is_valid(self, index: WorkspaceIndex, roots: list[Path]) -> bool:
        if roots != index.roots:
            return False
        for entry in index.entries:
            if not entry.devman_dir.is_dir():
                return False
        return True
