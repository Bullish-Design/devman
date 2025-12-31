# src/devman/core/config.py
"""Configuration helpers for llm-core."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from devman.models import SessionConfig, SystemConfig, WorkspaceConfig

DEFAULT_STATE_FILE = "llm-core.json"


def find_devman_dir(start: Path) -> Path | None:
    """Find the nearest .devman directory from a starting path."""
    candidate = start.resolve()
    if candidate.is_file():
        candidate = candidate.parent
    for current in [candidate, *candidate.parents]:
        devman_dir = current / ".devman"
        if devman_dir.is_dir():
            return devman_dir
    return None


def load_workspace_config(devman_dir: Path) -> WorkspaceConfig:
    """Load workspace configuration from a .devman directory."""
    return WorkspaceConfig.load(devman_dir)


def resolve_roots(cli_roots: Iterable[str]) -> list[Path]:
    """Resolve workspace roots from CLI overrides or system config."""
    if cli_roots:
        return [Path(root).expanduser() for root in cli_roots]
    system_config = SystemConfig.load()
    if system_config.resolved_roots:
        return system_config.resolved_roots
    return [Path.cwd()]


def read_state(config: WorkspaceConfig) -> SessionConfig:
    """Read persisted session state for a workspace."""
    state_path = _state_path(config)
    if not state_path.exists():
        return SessionConfig()
    payload = json.loads(state_path.read_text())
    return SessionConfig.model_validate(payload)


def write_state(config: WorkspaceConfig, payload: dict[str, object]) -> None:
    """Persist session state for a workspace."""
    state_path = _state_path(config)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def _state_path(config: WorkspaceConfig) -> Path:
    return config.devman_dir / ".state" / DEFAULT_STATE_FILE
