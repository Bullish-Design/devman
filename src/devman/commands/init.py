"""Command to initialize a workspace."""

from __future__ import annotations

import shutil
from pathlib import Path

import typer

from devman.loaders import load_workspace_config


def _template_root() -> Path:
    return Path(__file__).resolve().parents[3] / "templates" / "workspace-min" / ".devman"


def run(root: str | None = None, force: bool = False) -> None:
    """Initialize a .devman workspace layout."""
    target_root = Path(root).expanduser() if root else Path.cwd()
    target_devman = target_root / ".devman"
    template_dir = _template_root()

    if not template_dir.exists():
        raise typer.Exit(f"Template not found: {template_dir}")

    if target_devman.exists() and any(target_devman.iterdir()) and not force:
        raise typer.Exit(".devman already exists. Use --force to overwrite.")

    if target_devman.exists() and force:
        shutil.rmtree(target_devman)

    shutil.copytree(template_dir, target_devman)
    config_data = load_workspace_config(target_devman)
    typer.echo(f"Initialized workspace: {config_data.name}")


def init(root: str | None = None, force: bool = False) -> None:
    """Backward-compatible alias for run."""
    run(root=root, force=force)
