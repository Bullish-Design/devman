"""Workspace configuration loaders."""

from __future__ import annotations

from pathlib import Path

from devman.discovery import find_devman_dir
from devman.models import WorkspaceConfig


def load_workspace_config(devman_dir: Path) -> WorkspaceConfig:
    """Load the workspace configuration from the .devman directory."""
    return WorkspaceConfig.load(devman_dir)


def find_workspace_config(start: Path) -> WorkspaceConfig | None:
    """Find the nearest workspace and load its configuration."""
    devman_dir = find_devman_dir(start)
    if not devman_dir:
        return None
    return load_workspace_config(devman_dir)
