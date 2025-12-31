"""Onboarding wizard for first-time workspace setup."""

from __future__ import annotations

from pathlib import Path
import shutil

import typer

from devman.claude_code import CLAUDE_INSTALL_MESSAGE
from devman.commands.doctor import render_report, run as doctor_run
from devman.onboarding.templates import (
    DEFAULT_INTERACTION_MD,
    DEFAULT_NVIM_INIT_LUA,
    render_workspace_toml,
)


def run(root: str | None = None, force: bool = False) -> Path:
    """Run onboarding for a workspace and return the .devman path."""
    _report_dependencies()
    target_root = Path(root).expanduser() if root else Path.cwd()
    target_devman = target_root / ".devman"

    if target_devman.exists() and any(target_devman.iterdir()) and not force:
        raise typer.Exit(".devman already exists. Use --force to overwrite.")

    if target_devman.exists() and force:
        shutil.rmtree(target_devman)

    (target_devman / "nvim").mkdir(parents=True, exist_ok=True)
    (target_devman / "devman.toml").write_text(
        render_workspace_toml(target_root.name)
    )
    (target_devman / "interaction.md").write_text(DEFAULT_INTERACTION_MD)
    (target_devman / "nvim" / "init.lua").write_text(DEFAULT_NVIM_INIT_LUA)

    return target_devman


def _report_dependencies() -> None:
    status = doctor_run()
    missing = [tool for tool, available in status.items() if not available]
    if not missing:
        return

    typer.echo("Missing dependencies detected:", err=True)
    for line in render_report(status):
        typer.echo(line, err=True)
    if "claude" in missing:
        typer.echo(CLAUDE_INSTALL_MESSAGE, err=True)
