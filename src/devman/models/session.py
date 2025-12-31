# src/devman/models/session.py
"""Runtime session state models for devman."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class SessionState(BaseModel):
    """Runtime session state persisted by devman."""

    model_config = ConfigDict(extra="ignore")

    tmux_session: str | None = None
    nvim_listen: Path | None = None
