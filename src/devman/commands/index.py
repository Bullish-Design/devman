"""Index commands for llm-core."""

from __future__ import annotations

import json
from typing import Iterable

import typer

from devman.llm_core import index, workspace


def index_status() -> None:
    """Show index cache status."""
    payload = index.load_index()
    if not payload:
        typer.echo("Index cache missing.")
        raise typer.Exit(code=1)
    typer.echo(json.dumps(payload, indent=2))


def index_rebuild(cli_roots: Iterable[str] | None = None) -> None:
    """Force rebuild the index."""
    entries = index.rebuild_index(workspace.resolve_roots(cli_roots or []))
    for line in index.list_entries(entries):
        typer.echo(line)


def index_list(cli_roots: Iterable[str] | None = None) -> None:
    """List indexed workspaces."""
    entries = index.refresh_index(workspace.resolve_roots(cli_roots or []))
    for line in index.list_entries(entries):
        typer.echo(line)
