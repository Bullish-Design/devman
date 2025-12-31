# src/devman/commands/index.py
"""Index command helpers for llm-core."""

from __future__ import annotations

from typing import Iterable

from devman.discovery import IndexManager, resolve_roots
from devman.models import WorkspaceEntry, WorkspaceIndex


def _manager(manager: IndexManager | None = None) -> IndexManager:
    return manager or IndexManager()


def load_index(manager: IndexManager | None = None) -> WorkspaceIndex | None:
    """Load the cached workspace index."""
    return _manager(manager).load()


def refresh_index(
    roots: Iterable[str],
    manager: IndexManager | None = None,
) -> WorkspaceIndex:
    """Refresh the index based on resolved roots."""
    resolved = resolve_roots(roots)
    return _manager(manager).refresh(resolved)


def rebuild_index(
    roots: Iterable[str],
    manager: IndexManager | None = None,
) -> WorkspaceIndex:
    """Rebuild the index for the provided roots."""
    resolved = resolve_roots(roots)
    return _manager(manager).rebuild(resolved)


def list_entries(entries: Iterable[WorkspaceEntry]) -> list[str]:
    """Return human-friendly lines for each workspace entry."""
    lines: list[str] = []
    for entry in entries:
        extras: list[str] = []
        if entry.group:
            extras.append(entry.group)
        if entry.tags:
            extras.append(", ".join(entry.tags))
        suffix = f" ({'; '.join(extras)})" if extras else ""
        lines.append(f"{entry.name} - {entry.workspace_root}{suffix}")
    return lines


def find_entry(
    entries: Iterable[WorkspaceEntry],
    query: str,
    manager: IndexManager | None = None,
) -> WorkspaceEntry | None:
    """Find a workspace entry matching the provided query."""
    return _manager(manager).find_entry(entries, query)
