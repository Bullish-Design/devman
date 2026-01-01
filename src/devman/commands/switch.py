# src/devman/commands/switch.py
"""Workspace lookup helpers for the switch command."""

from __future__ import annotations

from typing import Iterable

import typer

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


def run(query: str, roots: list[str] | None = None) -> WorkspaceEntry:
    """Switch to a different workspace by name or query."""
    resolved_roots = roots or []
    workspace = resolve_workspace(query, resolved_roots)

    if not workspace:
        raise typer.Exit(f"No workspace found matching '{query}'")

    typer.echo(f"Switching to workspace: {workspace.name}")
    typer.echo(f"Location: {workspace.workspace_root}")

    return workspace


def switch(query: str, roots: list[str] | None = None) -> WorkspaceEntry:
    """Backward-compatible alias for run."""
    return run(query=query, roots=roots)
