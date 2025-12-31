"""Command to stop workspace services."""

from __future__ import annotations

from pathlib import Path

import typer

from devman.discovery import find_devman_dir
from devman.integrations import TmuxIntegration
from devman.loaders import load_workspace_config
from devman.state import read_state


TMUX = TmuxIntegration()


def run() -> None:
    """Stop services started by devman."""
    devman_dir = find_devman_dir(Path.cwd())
    if not devman_dir:
        raise typer.Exit("No workspace detected.")
    config_data = load_workspace_config(devman_dir)
    current_state = read_state(config_data)
    session_name = current_state.tmux_session
    if isinstance(session_name, str):
        typer.echo(f"Stopping tmux session {session_name}...")
        TMUX.kill_session(session_name)
    else:
        typer.echo("No recorded tmux session to stop.")


def down() -> None:
    """Backward-compatible alias for run."""
    run()
