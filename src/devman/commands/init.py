# src/devman/commands/init.py
"""Init command implementation."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

import typer

from devman.state import create_state_file
from devman.template import resolve_template_path, run_copier
from devman.validation import validate_nix_syntax, validate_template_pretend


def init_command(
    devman_dir: Path = typer.Option(
        Path(".devman"),
        "--devman-dir",
        "-d",
        help="Directory where the DevMan project should be created.",
    ),
    template: str = typer.Option(
        "python-devenv",
        "--template",
        "-t",
        help="Copier template name or path.",
    ),
    python_version: str = typer.Option(
        "3.12",
        "--python-version",
        help="Python version to configure in the project.",
    ),
    project_name: Optional[str] = typer.Option(
        None,
        "--project-name",
        help="Project name to use in the generated files.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing files if they already exist.",
    ),
) -> None:
    """Initialize a new DevMan project using a Copier template."""
    if devman_dir.exists() and not force:
        typer.echo(
            f"Error: '{devman_dir}' already exists. Use --force to overwrite.",
            err=True,
        )
        raise typer.Exit(1)

    script_dir = Path(__file__).resolve().parent.parent.parent
    try:
        template_path = resolve_template_path(template, script_dir)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    if not project_name:
        project_name = Path.cwd().name

    data = {
        "project_name": project_name,
        "python_version": python_version,
        "include_postgres": False,
        "include_redis": False,
    }

    devman_dir.mkdir(parents=True, exist_ok=True)

    try:
        typer.echo("Validating template...")
        validate_template_pretend(template_path, devman_dir, data)

        typer.echo("Generating files...")
        run_copier(template_path, devman_dir, data)

        typer.echo("Validating generated devenv.nix...")
        validate_nix_syntax(devman_dir / "devenv.nix")

        typer.echo("Creating state file...")
        create_state_file(devman_dir, template_path, data)

        typer.echo("DevMan project initialized successfully")
        typer.echo(f"  Template: {template_path}")
        typer.echo(f"  Project: {project_name}")
        typer.echo(f"  Python: {python_version}")
    except Exception as exc:
        if devman_dir.exists():
            shutil.rmtree(devman_dir, ignore_errors=True)
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc
