# src/devman/models/workspace.py
"""Workspace configuration models for llm-core."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field


class TmuxpConfig(BaseModel):
    """tmuxp configuration."""

    model_config = ConfigDict(extra="ignore")

    workspace: Path | None = None
    session_name: str | None = None


class ClaudeCodeConfig(BaseModel):
    """Claude Code interaction configuration."""

    model_config = ConfigDict(extra="ignore")

    interaction: Path | None = None
    emit_project_config: bool = False


class NvimConfig(BaseModel):
    """Neovim integration configuration."""

    model_config = ConfigDict(extra="ignore")

    init: Path | None = None
    listen: Path | None = None
    sessions_dir: Path | None = None
    default_session: str | None = None


class WorkspaceConfig(BaseModel):
    """Workspace configuration loaded from .devman/devman.toml."""

    model_config = ConfigDict(extra="ignore")

    name: str
    tags: list[str] = Field(default_factory=list)
    group: str | None = None
    tmuxp: TmuxpConfig = Field(default_factory=TmuxpConfig)
    claude_code: ClaudeCodeConfig = Field(default_factory=ClaudeCodeConfig)
    nvim: NvimConfig = Field(default_factory=NvimConfig)
    devman_dir: Path = Field(exclude=True)

    @computed_field
    @property
    def root(self) -> Path:
        """Workspace root directory."""
        return self.devman_dir.parent

    @computed_field
    @property
    def tmuxp_workspace(self) -> Path | None:
        """Absolute path to the tmuxp workspace file."""
        return _resolve_relative_path(self.tmuxp.workspace, self.devman_dir)

    @computed_field
    @property
    def tmuxp_session_name(self) -> str:
        """tmux session name (defaults to workspace name)."""
        return self.tmuxp.session_name or self.name

    @computed_field
    @property
    def claude_interaction(self) -> Path | None:
        """Absolute path to the Claude Code interaction file."""
        return _resolve_relative_path(self.claude_code.interaction, self.devman_dir)

    @computed_field
    @property
    def nvim_init(self) -> Path | None:
        """Absolute path to the Neovim init file."""
        return _resolve_relative_path(self.nvim.init, self.devman_dir)

    @computed_field
    @property
    def nvim_listen(self) -> Path | None:
        """Absolute path to the Neovim listen socket."""
        return _resolve_relative_path(self.nvim.listen, self.root)

    @computed_field
    @property
    def nvim_sessions_dir(self) -> Path | None:
        """Absolute path to the Neovim sessions directory."""
        return _resolve_relative_path(self.nvim.sessions_dir, self.devman_dir)

    @computed_field
    @property
    def nvim_default_session(self) -> str:
        """Default Neovim session name."""
        return self.nvim.default_session or "home.vim"

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
        data = _load_toml(devman_dir / "devman.toml")
        _apply_legacy_tables(data)
        _apply_env_overrides(data, devman_dir)

        workspace_table = data.get("workspace", {})
        name = workspace_table.get("name") or devman_dir.parent.name
        payload = {
            "name": name,
            "tags": workspace_table.get("tags", []),
            "group": workspace_table.get("group"),
            "tmuxp": data.get("tmuxp", {}),
            "claude_code": data.get("claude_code", {}),
            "nvim": data.get("nvim", {}),
            "devman_dir": devman_dir,
        }
        return cls.model_validate(payload)


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


def _apply_env_overrides(data: dict[str, Any], devman_dir: Path) -> None:
    env_path = devman_dir / ".env"
    env = _load_env(env_path)
    tmuxp_table = data.setdefault("tmuxp", {})

    if not tmuxp_table.get("workspace"):
        env_workspace = env.get("LLM_CORE_TMUXP_WORKSPACE")
        if env_workspace:
            tmuxp_table["workspace"] = env_workspace

    if not tmuxp_table.get("session_name"):
        env_session = env.get("LLM_CORE_SESSION_NAME")
        if env_session:
            tmuxp_table["session_name"] = env_session


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
        values[key.strip()] = value.strip()
    return values


def _resolve_relative_path(value: Path | None, base: Path) -> Path | None:
    if value is None:
        return None
    if value.is_absolute():
        return value
    return base / value
