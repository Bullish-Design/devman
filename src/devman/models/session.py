# src/devman/models/session.py
"""Runtime session state models for llm-core."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class SessionConfig(BaseModel):
    """Runtime session state persisted by llm-core."""

    model_config = ConfigDict(extra="ignore")

    tmux_session: str | None = None
    nvim_listen: Path | None = None
