"""Persisted workspace state."""

from __future__ import annotations

import json
from pathlib import Path

from .models import WorkspaceConfig


def state_path(config: WorkspaceConfig) -> Path:
    return config.devman_dir / ".state" / "llm-core.json"


def read_state(config: WorkspaceConfig) -> dict[str, object]:
    path = state_path(config)
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def write_state(config: WorkspaceConfig, payload: dict[str, object]) -> None:
    path = state_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
