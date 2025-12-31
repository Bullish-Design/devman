# src/devman/commands/up.py
"""Workspace selection helpers for the up command."""
"""Workspace bootstrap command."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Iterable

from devman.core.index import IndexManager, WorkspaceEntry
from devman.core.paths import find_devman_dir, index_cache_path, resolve_roots
from devman.integrations import claude_code, nvim, tmux, tmuxp
from devman.models.workspace import WorkspaceConfig, validate_required_files


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
        return WorkspaceEntry.from_workspace(devman_dir.parent, devman_dir)

    index_manager = manager or IndexManager(index_cache_path())
    index = index_manager.refresh(resolve_roots(roots))
    if not index.entries:
        raise ValueError("No workspaces found.")

    if selector:
        return selector(index.entries)

    return index.entries[0]

def run(root: Path | None = None) -> WorkspaceConfig:
    """Ensure workspace dependencies are configured."""
    workspace_root = root or Path.cwd()
    devman_dir = find_devman_dir(workspace_root)
    if not devman_dir:
        raise ValueError("No workspace found.")

    missing_files = validate_required_files(devman_dir)
    if missing_files:
        for missing in missing_files:
            print(f"Missing required file: {missing}", file=sys.stderr)

    config = WorkspaceConfig.load(devman_dir)
    claude_code.ensure_workspace_settings(
        config.root,
        config.claude_interaction,
        config.claude_emit_project_config,
    )

    _ensure_tmux(config)

    _load_nvim_session(config)

    return config


def _ensure_tmux(config: WorkspaceConfig) -> None:
    if config.tmuxp_workspace and config.tmuxp_workspace.exists():
        tmuxp.load_workspace(config.tmuxp_workspace, config.tmuxp_session_name)
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

    for command in nvim.build_session_commands(session_path):
        nvim.remote_send(config.nvim_listen, command)
