"""Down command for devman."""

from __future__ import annotations

import typer


def run() -> None:
    """Stop devman services and workspace."""
    typer.echo("Devman is stopping...")
