# src/devman/commands/up.py
"""Workspace selection helpers for the up command."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable

from devman.core.index import IndexManager, WorkspaceEntry
from devman.core.paths import find_devman_dir, index_cache_path, resolve_roots


SelectCallback = Callable[[list[WorkspaceEntry]], WorkspaceEntry]


def resolve_active_workspace(
    roots: Iterable[str],
    manager: IndexManager | None = None,
    selector: SelectCallback | None = None,
    start_path: Path | None = None,
) -> WorkspaceEntry:
    """Resolve the active workspace based on cwd or index selection."""
    current_path = start_path or Path.cwd()
    devman_dir = find_devman_dir(current_path)
    if devman_dir:
        return WorkspaceEntry.from_workspace(devman_dir.parent, devman_dir)

    index_manager = manager or IndexManager(index_cache_path())
    index = index_manager.refresh(resolve_roots(roots))
    if not index.entries:
        raise ValueError("No workspaces found.")

    if selector:
        return selector(index.entries)

    return index.entries[0]
