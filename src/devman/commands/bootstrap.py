"""Command to bootstrap a workspace."""

from __future__ import annotations

from pathlib import Path

import typer

from devman.commands.up import _ensure_tmux
from devman.llm_core import state, workspace
from devman.llm_core.integrations import claude, nvim
from devman.models.workspace import validate_required_files


def bootstrap(root: str | None = None) -> None:
    """Bootstrap tmux, Claude, and Neovim integrations for the current workspace."""
    workspace_root = Path(root).expanduser() if root else Path.cwd()
    devman_dir = workspace.find_devman_dir(workspace_root)
    if not devman_dir:
        raise typer.Exit("No workspace detected.")

    missing_files = validate_required_files(devman_dir)
    for missing in missing_files:
        typer.echo(f"Missing required file: {missing}", err=True)

    config_data = workspace.load_workspace_config(devman_dir)
    _ensure_tmux(config_data)

    if config_data.claude_emit_project_config:
        claude.emit_project_config(config_data.root, config_data.claude_interaction)

    if config_data.nvim_listen:
        listen = config_data.nvim_listen
    else:
        listen = config_data.root / ".devman" / ".state" / "nvim.sock"
    if config_data.nvim_init and config_data.nvim_init.exists():
        init = config_data.nvim_init
    else:
        init = None
    if listen:
        nvim.launch(config_data.root, listen, init)
        state.write_state(config_data, {"nvim_listen": str(listen)})
