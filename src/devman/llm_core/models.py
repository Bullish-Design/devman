"""Data models for llm-core."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


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


class WorkspaceEntry(BaseModel):
    """Cached index entry for a workspace."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    root: Path
    tags: list[str] = Field(default_factory=list)
    group: str | None = None
