"""Command to stop workspace services."""

from __future__ import annotations

from pathlib import Path

import typer

from devman.integrations import TmuxIntegration
from devman.llm_core import state, workspace


TMUX = TmuxIntegration()


def down() -> None:
    """Stop services started by llm-core."""
    devman_dir = workspace.find_devman_dir(Path.cwd())
    if not devman_dir:
        raise typer.Exit("No workspace detected.")
    config_data = workspace.load_workspace_config(devman_dir)
    current_state = state.read_state(config_data)
    session_name = current_state.get("tmux_session")
    if isinstance(session_name, str):
        typer.echo(f"Stopping tmux session {session_name}...")
        TMUX.kill_session(session_name)
    else:
        typer.echo("No recorded tmux session to stop.")
