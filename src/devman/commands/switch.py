# src/devman/commands/switch.py
"""Workspace lookup helpers for the switch command."""

from __future__ import annotations

from typing import Iterable

from devman.discovery import IndexManager, resolve_roots
from devman.models import WorkspaceEntry


def resolve_workspace(
    query: str,
    roots: Iterable[str],
    manager: IndexManager | None = None,
) -> WorkspaceEntry | None:
    """Resolve a workspace entry for the given query."""
    index_manager = manager or IndexManager()
    index = index_manager.refresh(resolve_roots(roots))
    return index_manager.find_entry(index.entries, query)
