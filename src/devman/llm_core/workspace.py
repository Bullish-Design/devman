"""Workspace discovery and configuration loading."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Iterable

from .models import WorkspaceConfig

ENV_TMUXP_WORKSPACE = "LLM_CORE_TMUXP_WORKSPACE"
ENV_TMUX_SESSION = "LLM_CORE_SESSION_NAME"
ENV_ROOTS = "LLM_CORE_ROOTS"


def find_devman_dir(start: Path) -> Path | None:
    current = start.resolve()
    while True:
        candidate = current / ".devman"
        if candidate.exists():
            return candidate
        if current.parent == current:
            return None
        current = current.parent


def resolve_roots(cli_roots: Iterable[str]) -> list[Path]:
    roots = [Path(root).expanduser() for root in cli_roots if root]
    if not roots:
        env_roots = os.environ.get(ENV_ROOTS, "")
        if env_roots:
            roots = [Path(root).expanduser() for root in env_roots.split(":") if root]
    if not roots:
        roots = [Path.cwd()]
    unique_roots: list[Path] = []
    for root in roots:
        resolved = root.resolve()
        if resolved not in unique_roots:
            unique_roots.append(resolved)
    return unique_roots


def _parse_env_overrides(devman_dir: Path) -> dict[str, str]:
    env_path = devman_dir / ".env"
    if not env_path.exists():
        return {}
    overrides: dict[str, str] = {}
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        overrides[key.strip()] = value.strip().strip('"')
    return overrides


def _resolve_path(base: Path, value: str | None) -> Path | None:
    if not value:
        return None
    candidate = Path(value).expanduser()
    return candidate if candidate.is_absolute() else base / candidate


def load_workspace_config(devman_dir: Path) -> WorkspaceConfig:
    toml_path = devman_dir / "devman.toml"
    payload: dict[str, object] = {}
    if toml_path.exists():
        payload = tomllib.loads(toml_path.read_text())

    env_overrides = _parse_env_overrides(devman_dir)
    workspace = payload.get("workspace", {}) if isinstance(payload, dict) else {}
    tmuxp = payload.get("tmuxp", {}) if isinstance(payload, dict) else {}
    claude = payload.get("claude_code", {}) if isinstance(payload, dict) else {}
    nvim = payload.get("nvim", {}) if isinstance(payload, dict) else {}

    root = devman_dir.parent
    name = workspace.get("name") if isinstance(workspace, dict) else None
    tags = workspace.get("tags") if isinstance(workspace, dict) else None
    group = workspace.get("group") if isinstance(workspace, dict) else None

    tmuxp_workspace = tmuxp.get("workspace") if isinstance(tmuxp, dict) else None
    tmuxp_session = tmuxp.get("session_name") if isinstance(tmuxp, dict) else None

    if env_overrides.get(ENV_TMUXP_WORKSPACE):
        tmuxp_workspace = env_overrides[ENV_TMUXP_WORKSPACE]
    if env_overrides.get(ENV_TMUX_SESSION):
        tmuxp_session = env_overrides[ENV_TMUX_SESSION]

    claude_interaction = claude.get("interaction") if isinstance(claude, dict) else None
    claude_emit = (
        claude.get("emit_project_config") if isinstance(claude, dict) else False
    )

    nvim_init = nvim.get("init") if isinstance(nvim, dict) else None
    nvim_listen = nvim.get("listen") if isinstance(nvim, dict) else None
    nvim_sessions = nvim.get("sessions_dir") if isinstance(nvim, dict) else None
    nvim_default_session = nvim.get("default_session") if isinstance(nvim, dict) else None

    return WorkspaceConfig(
        root=root,
        devman_dir=devman_dir,
        name=name or root.name,
        tags=list(tags) if isinstance(tags, list) else [],
        group=group if isinstance(group, str) else None,
        tmuxp_workspace=_resolve_path(devman_dir, tmuxp_workspace),
        tmuxp_session_name=tmuxp_session if isinstance(tmuxp_session, str) else None,
        claude_interaction=_resolve_path(devman_dir, claude_interaction),
        claude_emit_project_config=bool(claude_emit),
        nvim_init=_resolve_path(devman_dir, nvim_init),
        nvim_listen=_resolve_path(root, nvim_listen),
        nvim_sessions_dir=_resolve_path(devman_dir, nvim_sessions),
        nvim_default_session=(
            nvim_default_session if isinstance(nvim_default_session, str) else None
        ),
    )
