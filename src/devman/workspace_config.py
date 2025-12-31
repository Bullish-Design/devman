"""Workspace configuration for llm-core."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class WorkspaceConfig:
    """Configuration data for an llm-core workspace."""

    root: Path
    devman_dir: Path
    name: str
    tags: list[str]
    group: str | None
    tmuxp_workspace: Path | None
    tmuxp_session_name: str | None
    claude_code_interaction: Path | None
    claude_code_emit_project_config: bool
    nvim_init: Path | None
    nvim_listen: Path | None
    nvim_sessions_dir: Path | None
    nvim_default_session: str | None


def find_devman_dir(start: Path) -> Path | None:
    """Find the nearest .devman directory at or above the given path."""
    candidate = start.resolve()
    if candidate.name == ".devman" and candidate.is_dir():
        return candidate
    for parent in [candidate, *candidate.parents]:
        devman_dir = parent / ".devman"
        if devman_dir.is_dir():
            return devman_dir
    return None


def _parse_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw in path.read_text().splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def _resolve_optional_devman_path(devman_dir: Path, value: str | None) -> Path | None:
    if not value:
        return None
    return devman_dir / value


def _resolve_optional_root_path(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    return root / value


def load_workspace_config(devman_dir: Path) -> WorkspaceConfig:
    """Load workspace configuration from a .devman directory."""
    devman_dir = devman_dir.resolve()
    root = devman_dir.parent
    config_path = devman_dir / "devman.toml"
    data: dict[str, object] = {}
    if config_path.exists():
        data = tomllib.loads(config_path.read_text())

    env = _parse_env(devman_dir / ".env")

    workspace = data.get("workspace", {}) if isinstance(data.get("workspace"), dict) else {}
    tmuxp = data.get("tmuxp", {}) if isinstance(data.get("tmuxp"), dict) else {}
    claude = data.get("claude_code", {}) if isinstance(data.get("claude_code"), dict) else {}
    if not claude:
        claude = data.get("opencode", {}) if isinstance(data.get("opencode"), dict) else {}
    nvim = data.get("nvim", {}) if isinstance(data.get("nvim"), dict) else {}

    name = workspace.get("name") if isinstance(workspace.get("name"), str) else root.name
    tags = workspace.get("tags") if isinstance(workspace.get("tags"), list) else []
    group = workspace.get("group") if isinstance(workspace.get("group"), str) else None

    tmuxp_workspace_value = tmuxp.get("workspace")
    tmuxp_session_value = tmuxp.get("session_name")

    if not tmuxp_workspace_value and "LLM_CORE_TMUXP_WORKSPACE" in env:
        tmuxp_workspace_value = env.get("LLM_CORE_TMUXP_WORKSPACE")
    if not tmuxp_session_value and "LLM_CORE_SESSION_NAME" in env:
        tmuxp_session_value = env.get("LLM_CORE_SESSION_NAME")

    tmuxp_workspace = _resolve_optional_devman_path(
        devman_dir, tmuxp_workspace_value if isinstance(tmuxp_workspace_value, str) else None
    )
    tmuxp_session_name = tmuxp_session_value if isinstance(tmuxp_session_value, str) else None

    claude_interaction = claude.get("interaction") if isinstance(claude.get("interaction"), str) else None
    claude_emit = claude.get("emit_project_config")
    claude_emit_project_config = bool(claude_emit) if claude_emit is not None else False

    nvim_init = nvim.get("init") if isinstance(nvim.get("init"), str) else None
    nvim_listen = nvim.get("listen") if isinstance(nvim.get("listen"), str) else None
    nvim_sessions = nvim.get("sessions_dir") if isinstance(nvim.get("sessions_dir"), str) else None
    nvim_default = nvim.get("default_session") if isinstance(nvim.get("default_session"), str) else None

    return WorkspaceConfig(
        root=root,
        devman_dir=devman_dir,
        name=name,
        tags=list(tags),
        group=group,
        tmuxp_workspace=tmuxp_workspace,
        tmuxp_session_name=tmuxp_session_name,
        claude_code_interaction=_resolve_optional_devman_path(devman_dir, claude_interaction),
        claude_code_emit_project_config=claude_emit_project_config,
        nvim_init=_resolve_optional_devman_path(devman_dir, nvim_init),
        nvim_listen=_resolve_optional_root_path(root, nvim_listen),
        nvim_sessions_dir=_resolve_optional_devman_path(devman_dir, nvim_sessions),
        nvim_default_session=nvim_default,
    )
