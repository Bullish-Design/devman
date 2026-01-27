#!/usr/bin/env python3
"""DevMan CLI for managing local development environments."""

from __future__ import annotations

import subprocess
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


@app.command()
def init(
    template: str = typer.Option(
        "python-devenv",
        "--template",
        "-t",
        help="Copier template name or path.",
    ),
    output: str = typer.Option(
        ".",
        "--output",
        "-o",
        help="Output directory for the generated project.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing files if they already exist.",
    ),
) -> None:
    """Initialize a new DevMan project using a Copier template."""
    typer.echo("Init command (skeleton)")
    typer.echo(f"Template: {template}")
    typer.echo(f"Output: {output}")
    typer.echo(f"Force: {force}")


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
