"""Data models for llm-core."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceEntry(BaseModel):
    """Cached index entry for a workspace."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    root: Path
    tags: list[str] = Field(default_factory=list)
    group: str | None = None
