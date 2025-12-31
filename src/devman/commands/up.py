"""Command to start or attach to a workspace."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import typer

from devman.llm_core import index, state, workspace
from devman.llm_core.integrations import tmux, tmuxp
from devman.llm_core.models import WorkspaceConfig, WorkspaceEntry


def _select_workspace(entries: list[WorkspaceEntry]) -> WorkspaceEntry:
    lines = index.list_entries(entries)
    for idx, line in enumerate(lines, 1):
        typer.echo(f"[{idx}] {line}")
    choice = typer.prompt("Select workspace", default="1")
    return entries[int(choice) - 1]


def _load_active_workspace(cli_roots: Iterable[str]) -> WorkspaceConfig:
    devman_dir = workspace.find_devman_dir(Path.cwd())
    if not devman_dir:
        entries = index.refresh_index(workspace.resolve_roots(cli_roots))
        if not entries:
            raise typer.Exit("No workspaces found.")
        selected = _select_workspace(entries)
        devman_dir = selected.root / ".devman"
    return workspace.load_workspace_config(devman_dir)


def _ensure_tmux(config_data: WorkspaceConfig) -> None:
    session_name = config_data.tmuxp_session_name or config_data.name
    if config_data.tmuxp_workspace and config_data.tmuxp_workspace.exists():
        tmuxp.ensure_tmuxp(config_data.tmuxp_workspace, session_name)
        state.write_state(config_data, {"tmux_session": session_name})
        return

    tmux.ensure_session(session_name, config_data.root)
    tmux.ensure_windows(session_name, config_data.root)
    state.write_state(config_data, {"tmux_session": session_name})


def up(cli_roots: Iterable[str] | None = None) -> None:
    """Start or attach to a workspace."""
    config_data = _load_active_workspace(cli_roots or [])
    index.refresh_index(workspace.resolve_roots(cli_roots or []))
    _ensure_tmux(config_data)
