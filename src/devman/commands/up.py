# src/devman/commands/up.py
"""Workspace selection helpers for the up command."""
"""Workspace bootstrap command."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Callable, Iterable

from devman.discovery import IndexManager, build_entry, find_devman_dir, resolve_roots
from devman.integrations import claude_code, nvim, tmux, tmuxp
from devman.models import WorkspaceEntry


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

    config = load_workspace_config(devman_dir)
    claude_code.ensure_workspace_settings(
        config.root,
        config.claude_interaction,
        config.claude_emit_project_config,
    )

    if config.tmuxp_workspace and config.tmuxp_workspace.exists():
        tmuxp.load_workspace(config.tmuxp_workspace, config.tmuxp_session_name)
    else:
        session_name = config.tmuxp_session_name or config.name
        tmux.ensure_session(session_name, config.root)

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
        "LLM_CORE_TMUXP_WORKSPACE"
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
        "LLM_CORE_SESSION_NAME"
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
        nvim_listen = workspace_root / ".devman" / ".state" / "nvim.sock"

    nvim_sessions_dir = _resolve_optional_path(nvim_data.get("sessions_dir"), devman_dir)
    if nvim_sessions_dir is None:
        default_sessions_dir = devman_dir / "sessions"
        if default_sessions_dir.exists():
            nvim_sessions_dir = default_sessions_dir

    nvim_default_session = nvim_data.get("default_session")
    if nvim_default_session is None and nvim_sessions_dir is not None:
        default_session_path = nvim_sessions_dir / "home.vim"
        if default_session_path.exists():
            nvim_default_session = "home.vim"

    return WorkspaceConfig(
        root=workspace_root,
        devman_dir=devman_dir,
        name=name,
        tmuxp_workspace=tmuxp_workspace,
        tmuxp_session_name=tmuxp_session_name,
        claude_interaction=claude_interaction,
        claude_emit_project_config=claude_emit_project_config,
        nvim_init=nvim_init,
        nvim_listen=nvim_listen,
        nvim_sessions_dir=nvim_sessions_dir,
        nvim_default_session=nvim_default_session,
    )


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _load_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key.replace("export ", "", 1).strip()
        data[key] = value.strip().strip("\"").strip("'")
    return data


def _resolve_optional_path(value: Optional[str], base: Path) -> Optional[Path]:
    if not value:
        return None
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return (base / candidate).resolve()


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
