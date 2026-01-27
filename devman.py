#!/usr/bin/env python3
"""DevMan CLI for managing local development environments."""

from __future__ import annotations

import datetime
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(help="DevMan CLI for managing local development environments.")


def get_jj_info() -> dict[str, Optional[str]]:
    """Return current jj bookmark and change id info."""
    def run_jj(args: list[str]) -> subprocess.CompletedProcess[str] | None:
        try:
            return subprocess.run(
                ["jj", *args],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return None

    bookmark = None
    bookmark_result = run_jj(["bookmark", "list", "-r", "@", "--color=never"])
    if bookmark_result and bookmark_result.returncode == 0:
        lines = [line.strip() for line in bookmark_result.stdout.splitlines() if line.strip()]
        if lines:
            bookmark = lines[0].split(":", maxsplit=1)[0].strip() or None

    change_id = None
    change_result = run_jj(["log", "-r", "@", "-T", "change_id.short()"])
    if change_result and change_result.returncode == 0:
        change_id = change_result.stdout.strip() or None

    return {"bookmark": bookmark, "change_id": change_id}


def resolve_template_path(template: str, script_dir: Path) -> Path:
    """Resolve the copier template path from a name or filesystem path."""
    if "/" in template or template.startswith("."):
        template_path = Path(template).expanduser()
        if template_path.exists():
            return template_path.resolve()
        raise ValueError(f"Template path '{template}' does not exist.")

    bundled_template = script_dir / "templates" / template
    if bundled_template.exists():
        return bundled_template.resolve()

    raise ValueError(
        "Unknown template. Provide a filesystem path like "
        f"./templates/{template}."
    )


@app.command()
def init(
    devman_dir: Path = typer.Option(
        Path("devman"),
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
        sys.exit(1)

    script_dir = Path(__file__).resolve().parent
    try:
        template_path = resolve_template_path(template, script_dir)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        sys.exit(1)

    if not project_name:
        project_name = Path.cwd().name

    data = {
        "project_name": project_name,
        "python_version": python_version,
        "include_postgres": False,
        "include_redis": False,
    }

    devman_dir.mkdir(parents=True, exist_ok=True)

    def format_value(value: object) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    data_payload = "\n".join(f"{key}={format_value(value)}" for key, value in data.items())

    result = subprocess.run(
        [
            "copier",
            str(template_path),
            str(devman_dir),
            "--data-file",
            "-",
            "--defaults",
        ],
        input=data_payload,
        text=True,
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        typer.echo(result.stderr or "Copier failed.", err=True)
        shutil.rmtree(devman_dir, ignore_errors=True)
        sys.exit(result.returncode or 1)

    typer.echo("DevMan project initialized.")
    typer.echo(f"Template: {template_path}")
    typer.echo(f"Project: {project_name}")
    typer.echo(f"Python: {python_version}")


@app.command()
def validate(
    config: str = typer.Option(
        "devman.yaml",
        "--config",
        "-c",
        help="Path to the DevMan config file.",
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        "-s",
        help="Enable strict validation checks.",
    ),
) -> None:
    """Validate the current DevMan project configuration."""
    typer.echo("Validate command (skeleton)")
    typer.echo(f"Config: {config}")
    typer.echo(f"Strict: {strict}")


@app.command()
def test(
    container_prefix: str = typer.Option(
        "devman-test",
        "--container-prefix",
        "-p",
        help="Prefix to use when naming the test container.",
    ),
    reuse: bool = typer.Option(
        False,
        "--reuse",
        "-r",
        help="Reuse an existing test container if available.",
    ),
) -> None:
    """Run the DevMan test container for the current repository."""
    jj_info = get_jj_info()
    suffix = jj_info.get("bookmark") or jj_info.get("change_id") or "unknown"
    container_name = f"{container_prefix}-{suffix}"
    typer.echo("Test command (skeleton)")
    typer.echo(f"Container: {container_name}")
    typer.echo(f"Reuse: {reuse}")


@app.command()
def clean(
    all: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Remove all generated artifacts, including caches.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be removed without deleting anything.",
    ),
) -> None:
    """Remove DevMan-generated artifacts from the working tree."""
    typer.echo("Clean command (skeleton)")
    typer.echo(f"All: {all}")
    typer.echo(f"Dry run: {dry_run}")


if __name__ == "__main__":
    app()
