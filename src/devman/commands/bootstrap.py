"""Command to bootstrap a workspace."""

from __future__ import annotations

from pathlib import Path

import typer

from devman.claude_code import CLAUDE_INSTALL_MESSAGE, ClaudeCodeWorkspace
from devman.commands.up import _ensure_tmux
from devman.discovery import find_devman_dir
from devman.integrations import ClaudeIntegration, NvimIntegration
from devman.loaders import load_workspace_config
from devman.models import SessionState
from devman.models.workspace import validate_required_files
from devman.state import StateManager


CLAUDE = ClaudeIntegration()
CLAUDE_WORKSPACE = ClaudeCodeWorkspace()
NVIM = NvimIntegration()
STATE_MANAGER = StateManager()


def run(root: str | None = None) -> None:
    """Bootstrap tmux, Claude, and Neovim integrations for the current workspace."""
    workspace_root = Path(root).expanduser() if root else Path.cwd()
    devman_dir = find_devman_dir(workspace_root)
    if not devman_dir:
        raise typer.Exit("No workspace detected.")

    if not CLAUDE_WORKSPACE.is_available():
        raise typer.Exit(CLAUDE_INSTALL_MESSAGE)

    missing_files = validate_required_files(devman_dir)
    for missing in missing_files:
        typer.echo(f"Missing required file: {missing}", err=True)

    config_data = load_workspace_config(devman_dir)
    _ensure_tmux(config_data)

    if config_data.claude_emit_project_config:
        CLAUDE.emit_project_config(
            config_data.root,
            config_data.claude_interaction,
        )

    listen = config_data.nvim_listen
    init = config_data.nvim_init if config_data.nvim_init and config_data.nvim_init.exists() else None

    if listen:
        NVIM.launch(config_data.root, listen, init)
        current_state = STATE_MANAGER.read(config_data)
        updated_state = SessionState(
            tmux_session=current_state.tmux_session,
            nvim_listen=listen,
        )
        STATE_MANAGER.write(config_data, updated_state)


def bootstrap(root: str | None = None) -> None:
    """Backward-compatible alias for run."""
    run(root=root)
