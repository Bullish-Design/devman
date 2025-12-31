"""Switch command for devman."""

from __future__ import annotations

import typer


def run() -> None:
    """Switch the active devman workspace."""
    typer.echo("Switching devman workspace...")
