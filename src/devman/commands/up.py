"""Workspace bootstrap command."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable

import typer

from devman.claude_code import CLAUDE_INSTALL_MESSAGE, ClaudeCodeWorkspace
from devman.discovery import IndexManager, build_entry, find_devman_dir, resolve_roots
from devman.integrations import (
    ClaudeIntegration,
    NvimIntegration,
    TmuxIntegration,
    TmuxpIntegration,
)
from devman.loaders import load_workspace_config
from devman.models import SessionState, WorkspaceConfig, WorkspaceEntry
from devman.state import StateManager


CLAUDE = ClaudeIntegration()
CLAUDE_WORKSPACE = ClaudeCodeWorkspace()
NVIM = NvimIntegration()
TMUX = TmuxIntegration()
TMUXP = TmuxpIntegration()
STATE_MANAGER = StateManager()

SelectCallback = Callable[[list[WorkspaceEntry]], WorkspaceEntry]


def resolve_active_workspace(
    roots: Iterable[str],
    manager: IndexManager | None = None,
    selector: SelectCallback | None = None,
    start_path: Path | None = None,
) -> WorkspaceEntry:
    """Resolve the active workspace based on cwd or index selection."""
    current_path = start_path or Path.cwd()
    devman_dir = find_devman_dir(current_path)
    if devman_dir:
        return build_entry(devman_dir.parent, devman_dir)

    index_manager = manager or IndexManager()
    index = index_manager.refresh(resolve_roots(roots))
    if not index.entries:
        raise ValueError("No workspaces found.")

    if selector:
        return selector(index.entries)

    return index.entries[0]


def run(root: Path | None = None) -> WorkspaceConfig:
    """Ensure workspace dependencies are configured."""
    config = _resolve_workspace_config(root)
    _ensure_claude(config)
    session_name = _ensure_tmux(config)
    _record_state(config, session_name)
    _load_nvim_session(config)
    return config


def _resolve_workspace_config(root: Path | None = None) -> WorkspaceConfig:
    workspace_root = root or Path.cwd()
    devman_dir = find_devman_dir(workspace_root)
    if not devman_dir:
        raise ValueError("No workspace found.")
    return load_workspace_config(devman_dir)


def _ensure_claude(config: WorkspaceConfig) -> None:
    if not CLAUDE_WORKSPACE.is_available():
        raise typer.Exit(CLAUDE_INSTALL_MESSAGE)

    CLAUDE.setup(
        config.root,
        config.claude_interaction,
        config.claude_emit_project_config,
    )


def _ensure_tmux(config: WorkspaceConfig) -> str | None:
    session_name = config.tmuxp_session_name or config.name
    if config.tmuxp_workspace and config.tmuxp_workspace.exists():
        TMUXP.setup(config.tmuxp_workspace, config.tmuxp_session_name)
        return session_name

    TMUX.setup(session_name, config.root)
    TMUX.ensure_windows(session_name, config.root)
    return session_name


def _record_state(config: WorkspaceConfig, session_name: str | None) -> None:
    if session_name is None:
        return

    current_state = STATE_MANAGER.read(config)
    updated_state = SessionState(
        tmux_session=session_name,
        nvim_listen=current_state.nvim_listen,
    )
    STATE_MANAGER.write(config, updated_state)


def _load_nvim_session(config: WorkspaceConfig) -> None:
    if not config.nvim_sessions_dir or not config.nvim_listen:
        return

    session_name = config.nvim_default_session or "home.vim"
    session_path = config.nvim_sessions_dir / session_name
    if not session_path.exists():
        return

    if not config.nvim_listen.exists():
        return

    for command in NVIM.build_session_commands(config.root, session_path):
        NVIM.remote_send(config.nvim_listen, command)
