"""Persisted workspace state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from devman.models import SessionConfig, WorkspaceConfig


def state_path(config: WorkspaceConfig) -> Path:
    """Return the path to the workspace state file."""
    return config.devman_dir / ".state" / "devman.json"


def read_state(config: WorkspaceConfig) -> SessionConfig:
    """Read persisted state for a workspace."""
    path = state_path(config)
    if not path.exists():
        return SessionConfig()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return SessionConfig()
    return SessionConfig.model_validate(payload)


def write_state(config: WorkspaceConfig, payload: SessionConfig | dict[str, Any]) -> None:
    """Persist state for a workspace."""
    session = (
        payload if isinstance(payload, SessionConfig) else SessionConfig.model_validate(payload)
    )
    path = state_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        session.model_dump_json(indent=2, exclude_none=True) + "\n",
        encoding="utf-8",
    )
