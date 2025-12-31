"""Command to check external dependencies."""

from __future__ import annotations

import typer

from devman.llm_core.integrations import claude, nvim, tmux, tmuxp


def doctor() -> None:
    """Check external dependencies."""
    tools = {
        "tmux": tmux.is_available(),
        "tmuxp": tmuxp.is_available(),
        "nvim": nvim.is_available(),
        "claude": claude.is_available(),
    }
    for tool, available in tools.items():
        typer.echo(f"{tool}: {'ok' if available else 'missing'}")
