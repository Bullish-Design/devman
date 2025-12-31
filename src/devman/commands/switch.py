"""Command to switch workspaces."""

from __future__ import annotations

from typing import Iterable

import typer

from devman.commands.up import _ensure_tmux
from devman.llm_core import index, workspace
from devman.llm_core.integrations import nvim


def switch(query: str, cli_roots: Iterable[str] | None = None) -> None:
    """Switch to another workspace."""
    entries = index.refresh_index(workspace.resolve_roots(cli_roots or []))
    match = index.find_entry(entries, query)
    if not match:
        raise typer.Exit("No matching workspace found.")
    config_data = workspace.load_workspace_config(match.root / ".devman")
    _ensure_tmux(config_data)

    if config_data.nvim_listen and config_data.nvim_sessions_dir:
        session_path = config_data.nvim_sessions_dir / (
            config_data.nvim_default_session or "home.vim"
        )
        if session_path.exists():
            for cmd in nvim.build_session_commands(config_data.root, session_path):
                nvim.remote_send(config_data.nvim_listen, cmd)
