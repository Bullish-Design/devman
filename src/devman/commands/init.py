"""Command to initialize a workspace."""

from __future__ import annotations

import typer

from devman.loaders import load_workspace_config
from devman.onboarding import wizard


def run(root: str | None = None, force: bool = False) -> None:
    """Initialize a .devman workspace layout."""
    target_devman = wizard.run(root=root, force=force)
    config_data = load_workspace_config(target_devman)
    typer.echo(f"Initialized workspace: {config_data.name}")


def init(root: str | None = None, force: bool = False) -> None:
    """Backward-compatible alias for run."""
    run(root=root, force=force)
