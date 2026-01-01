# src/devman/commands/index.py
"""Index command helpers for devman."""

from __future__ import annotations

import json
from typing import Iterable

import typer

from devman.discovery import IndexManager, resolve_roots
from devman.models import WorkspaceEntry, WorkspaceIndex

app = typer.Typer(help="Manage workspace index")


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


@app.command(name="status")
def index_status() -> None:
    """Show index cache status."""
    payload = load_index()
    if not payload:
        typer.echo("Index cache missing.")
        raise typer.Exit(code=1)

    # Convert to dict for JSON serialization
    index_dict = {
        "entries": [
            {
                "name": entry.name,
                "workspace_root": str(entry.workspace_root),
                "devman_dir": str(entry.devman_dir),
                "group": entry.group,
                "tags": entry.tags,
            }
            for entry in payload.entries
        ]
    }
    typer.echo(json.dumps(index_dict, indent=2))


@app.command(name="rebuild")
def index_rebuild(
    roots: list[str] = typer.Argument(None, help="Roots to index")
) -> None:
    """Force rebuild the index."""
    resolved_roots = roots or []
    index = rebuild_index(resolved_roots)
    for line in list_entries(index.entries):
        typer.echo(line)


@app.command(name="list")
def index_list(
    roots: list[str] = typer.Argument(None, help="Roots to index")
) -> None:
    """List indexed workspaces."""
    resolved_roots = roots or []
    index = refresh_index(resolved_roots)
    for line in list_entries(index.entries):
        typer.echo(line)
