"""State persistence manager for devman."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from devman.models import SessionState, WorkspaceConfig


DEFAULT_CACHE_DIRNAME = "devman"


def cache_dir() -> Path:
    """Return the base cache directory for devman."""
    base = os.environ.get("XDG_CACHE_HOME")
    if base:
        return Path(base).expanduser() / DEFAULT_CACHE_DIRNAME
    return Path.home() / ".cache" / DEFAULT_CACHE_DIRNAME


class StateManager:
    """Manage persisted runtime state for workspaces."""

    def __init__(self, cache_root: Path | None = None) -> None:
        self.cache_root = cache_root or cache_dir()

    def state_path(self, config: WorkspaceConfig) -> Path:
        """Return the cache path for a workspace's state."""
        workspace_key = _workspace_key(config)
        return self.cache_root / "state" / f"{workspace_key}.json"

    def read(self, config: WorkspaceConfig) -> SessionState:
        """Read persisted state for a workspace."""
        path = self.state_path(config)
        if not path.exists():
            return SessionState()
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return SessionState()
        return SessionState.model_validate(payload)

    def write(self, config: WorkspaceConfig, payload: SessionState | dict[str, Any]) -> None:
        """Persist state for a workspace."""
        session = payload if isinstance(payload, SessionState) else SessionState.model_validate(
            payload
        )
        path = self.state_path(config)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            session.model_dump_json(indent=2, exclude_none=True) + "\n",
            encoding="utf-8",
        )


def _workspace_key(config: WorkspaceConfig) -> str:
    root = config.root.resolve()
    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:12]
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", config.name or root.name).strip("-")
    slug = slug or "workspace"
    return f"{slug}-{digest}"
