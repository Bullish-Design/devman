"""Up command for devman."""

from __future__ import annotations

import typer


def run() -> None:
    """Start devman services and workspace."""
    typer.echo("Devman is starting...")
