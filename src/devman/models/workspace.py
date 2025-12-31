# src/devman/models/workspace.py
"""Workspace configuration model for llm-core."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field

ENV_TMUXP_WORKSPACE = "LLM_CORE_TMUXP_WORKSPACE"
ENV_TMUX_SESSION = "LLM_CORE_SESSION_NAME"

REQUIRED_FILES = (
    Path("devman.toml"),
    Path("interaction.md"),
    Path("workspace.tmuxp.yaml"),
    Path("nvim/init.lua"),
    Path("sessions/home.vim"),
)


class WorkspaceConfig(BaseModel):
    """Workspace configuration loaded from .devman/devman.toml."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    root: Path
    devman_dir: Path
    name: str
    tags: list[str] = Field(default_factory=list)
    group: str | None = None
    tmuxp_workspace: Path | None = None
    tmuxp_session_name: str | None = None
    claude_interaction: Path | None = None
    claude_emit_project_config: bool = False
    nvim_init: Path | None = None
    nvim_listen: Path | None = None
    nvim_sessions_dir: Path | None = None
    nvim_default_session: str | None = None

    @classmethod
    def find_and_load(cls, start: Path) -> "WorkspaceConfig | None":
        """Find the nearest .devman directory and load config."""
        devman_dir = _find_devman_dir(start)
        if not devman_dir:
            return None
        return cls.load(devman_dir)

    @classmethod
    def load(cls, devman_dir: Path) -> "WorkspaceConfig":
        """Load workspace configuration from the devman directory."""
        devman_dir = devman_dir.resolve()
        root = devman_dir.parent
        data = _load_toml(devman_dir / "devman.toml")
        _apply_legacy_tables(data)
        env = _load_env(devman_dir / ".env")

        workspace_table = data.get("workspace", {})
        tmuxp_table = data.get("tmuxp", {})
        claude_table = data.get("claude_code", {})
        nvim_table = data.get("nvim", {})

        name = _as_str(workspace_table.get("name")) or root.name
        tags = _as_list(workspace_table.get("tags"))
        group = _as_str(workspace_table.get("group"))

        tmuxp_workspace = _as_str(tmuxp_table.get("workspace"))
        tmuxp_session_name = _as_str(tmuxp_table.get("session_name"))

        if not tmuxp_workspace and env.get(ENV_TMUXP_WORKSPACE):
            tmuxp_workspace = env[ENV_TMUXP_WORKSPACE]
        if not tmuxp_session_name and env.get(ENV_TMUX_SESSION):
            tmuxp_session_name = env[ENV_TMUX_SESSION]

        tmuxp_workspace_path = _resolve_path(devman_dir, tmuxp_workspace)
        if tmuxp_workspace_path is None:
            tmuxp_workspace_path = _default_file(devman_dir, "workspace.tmuxp.yaml")

        claude_interaction = _as_str(claude_table.get("interaction"))
        claude_interaction_path = _resolve_path(devman_dir, claude_interaction)
        if claude_interaction_path is None:
            claude_interaction_path = _default_file(devman_dir, "interaction.md")

        claude_emit = bool(claude_table.get("emit_project_config", False))

        nvim_init = _as_str(nvim_table.get("init"))
        nvim_init_path = _resolve_path(devman_dir, nvim_init)
        if nvim_init_path is None:
            nvim_init_path = _default_file(devman_dir, "nvim/init.lua")

        nvim_listen_value = _as_str(nvim_table.get("listen"))
        if nvim_listen_value:
            nvim_listen_path = _resolve_path(root, nvim_listen_value)
        else:
            nvim_listen_path = root / ".devman" / ".state" / "nvim.sock"

        nvim_sessions = _as_str(nvim_table.get("sessions_dir"))
        nvim_sessions_path = _resolve_path(devman_dir, nvim_sessions)
        if nvim_sessions_path is None:
            nvim_sessions_path = _default_dir(devman_dir, "sessions")

        nvim_default_session = _as_str(nvim_table.get("default_session"))
        if not nvim_default_session and nvim_sessions_path:
            default_session = nvim_sessions_path / "home.vim"
            if default_session.exists():
                nvim_default_session = "home.vim"

        return cls(
            root=root,
            devman_dir=devman_dir,
            name=name,
            tags=tags,
            group=group,
            tmuxp_workspace=tmuxp_workspace_path,
            tmuxp_session_name=tmuxp_session_name,
            claude_interaction=claude_interaction_path,
            claude_emit_project_config=claude_emit,
            nvim_init=nvim_init_path,
            nvim_listen=nvim_listen_path,
            nvim_sessions_dir=nvim_sessions_path,
            nvim_default_session=nvim_default_session,
        )


def validate_required_files(devman_dir: Path) -> list[Path]:
    """Return missing required files for a workspace."""
    if not devman_dir.exists():
        return [devman_dir]
    return [
        devman_dir / relative
        for relative in REQUIRED_FILES
        if not (devman_dir / relative).exists()
    ]


def _find_devman_dir(start: Path) -> Path | None:
    candidate = start.resolve()
    if candidate.is_file():
        candidate = candidate.parent
    for current in [candidate, *candidate.parents]:
        devman_dir = current / ".devman"
        if devman_dir.is_dir():
            return devman_dir
    return None


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    import tomllib

    return tomllib.loads(path.read_text())


def _apply_legacy_tables(data: dict[str, Any]) -> None:
    if "claude_code" not in data and "opencode" in data:
        data["claude_code"] = data["opencode"]


def _load_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _resolve_path(base: Path, value: str | Path | None) -> Path | None:
    if value is None:
        return None
    candidate = value if isinstance(value, Path) else Path(value).expanduser()
    return candidate if candidate.is_absolute() else base / candidate


def _default_file(devman_dir: Path, relative: str) -> Path | None:
    candidate = devman_dir / relative
    return candidate if candidate.exists() else None


def _default_dir(devman_dir: Path, relative: str) -> Path | None:
    candidate = devman_dir / relative
    return candidate if candidate.is_dir() else None


def _as_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _as_list(value: Any) -> list[str]:
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return [str(item) for item in value]
    return []
