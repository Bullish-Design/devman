# src/devman/commands/up.py
"""Workspace selection helpers for the up command."""
"""Workspace bootstrap command."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

import typer

from devman.claude_code import CLAUDE_INSTALL_MESSAGE, ClaudeCodeWorkspace
from devman.integrations import (
    ClaudeIntegration,
    NvimIntegration,
    TmuxIntegration,
    TmuxpIntegration,
)
from devman.core.index import IndexManager, WorkspaceEntry
from devman.core.paths import find_devman_dir, index_cache_path, resolve_roots


CLAUDE = ClaudeIntegration()
CLAUDE_WORKSPACE = ClaudeCodeWorkspace()
NVIM = NvimIntegration()
TMUX = TmuxIntegration()
TMUXP = TmuxpIntegration()

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


@dataclass(frozen=True)
class WorkspaceConfig:
    """Resolved workspace configuration."""

    root: Path
    devman_dir: Path
    name: str
    tmuxp_workspace: Optional[Path]
    tmuxp_session_name: Optional[str]
    claude_interaction: Optional[Path]
    claude_emit_project_config: bool
    nvim_init: Optional[Path]
    nvim_listen: Optional[Path]
    nvim_sessions_dir: Optional[Path]
    nvim_default_session: Optional[str]


def run(root: Optional[Path] = None) -> WorkspaceConfig:
    """Ensure workspace dependencies are configured."""
    workspace_root = root or Path.cwd()
    devman_dir = find_devman_dir(workspace_root)
    if not devman_dir:
        raise ValueError("No workspace found.")

    if not CLAUDE_WORKSPACE.is_available():
        raise typer.Exit(CLAUDE_INSTALL_MESSAGE)

    config = load_workspace_config(devman_dir)
    CLAUDE.setup(
        config.root,
        config.claude_interaction,
        config.claude_emit_project_config,
    )

    if config.tmuxp_workspace and config.tmuxp_workspace.exists():
        TMUXP.setup(config.tmuxp_workspace, config.tmuxp_session_name)
    else:
        session_name = config.tmuxp_session_name or config.name
        TMUX.setup(session_name, config.root)

    _load_nvim_session(config)

    return config


def load_workspace_config(devman_dir: Path) -> WorkspaceConfig:
    """Load workspace configuration from devman.toml and .env."""
    workspace_root = devman_dir.parent
    data = _load_toml(devman_dir / "devman.toml")
    env = _load_env(devman_dir / ".env")

    workspace_data = data.get("workspace", {})
    tmuxp_data = data.get("tmuxp", {})
    claude_data = data.get("claude_code", {})
    nvim_data = data.get("nvim", {})

    name = str(workspace_data.get("name") or workspace_root.name)

    tmuxp_workspace_value = tmuxp_data.get("workspace") or env.get(
        "DEVMAN_TMUXP_WORKSPACE"
    )
    tmuxp_workspace = _resolve_optional_path(
        tmuxp_workspace_value,
        devman_dir,
    )
    if tmuxp_workspace is None:
        default_tmuxp = devman_dir / "workspace.tmuxp.yaml"
        if default_tmuxp.exists():
            tmuxp_workspace = default_tmuxp

    tmuxp_session_name = tmuxp_data.get("session_name") or env.get(
        "DEVMAN_SESSION_NAME"
    )
    claude_interaction = _resolve_optional_path(
        claude_data.get("interaction"),
        devman_dir,
    )
    if claude_interaction is None:
        default_interaction = devman_dir / "interaction.md"
        if default_interaction.exists():
            claude_interaction = default_interaction

    claude_emit_project_config = bool(claude_data.get("emit_project_config", False))

    nvim_init = _resolve_optional_path(nvim_data.get("init"), devman_dir)
    if nvim_init is None:
        default_init = devman_dir / "nvim" / "init.lua"
        if default_init.exists():
            nvim_init = default_init

    nvim_listen_value = nvim_data.get("listen")
    if nvim_listen_value:
        listen_path = Path(nvim_listen_value)
        nvim_listen = listen_path if listen_path.is_absolute() else workspace_root / listen_path
    else:
        session_name = config.tmuxp_session_name or config.name
        tmux.ensure_session(session_name, config.root)


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
