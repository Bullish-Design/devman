# src/devman/commands/validate.py
"""Validate command implementation."""

from __future__ import annotations

from pathlib import Path

import typer
import yaml

from devman.validation import validate_nix_syntax


def validate_command(
    devman_dir: Path = typer.Option(
        Path(".devman"),
        "--devman-dir",
        help="Path to .devman directory.",
    ),
) -> None:
    """Validate the current DevMan project configuration."""
    if not devman_dir.exists():
        typer.echo(f"Error: {devman_dir} does not exist.", err=True)
        raise typer.Exit(1)

    checks = []

    # Check devenv.nix
    devenv_file = devman_dir / "devenv.nix"
    if not devenv_file.exists():
        checks.append("devenv.nix not found")
    else:
        try:
            validate_nix_syntax(devenv_file)
            checks.append("devenv.nix valid")
        except ValueError as exc:
            checks.append(f"devenv.nix invalid: {exc}")

    # Check justfile
    justfile = devman_dir / "justfile"
    if not justfile.exists():
        checks.append("justfile not found")
    else:
        checks.append("justfile exists")

    # Check state.yaml
    state_file = devman_dir / "state.yaml"
    if not state_file.exists():
        checks.append("state.yaml not found")
    else:
        try:
            with open(state_file) as f:
                state = yaml.safe_load(f)
            if "template" not in state or "variables" not in state:
                checks.append("state.yaml invalid schema")
            else:
                checks.append("state.yaml valid")
        except Exception as exc:
            checks.append(f"state.yaml error: {exc}")

    # Print results
    typer.echo("\nValidation Results:")
    has_errors = False
    for check in checks:
        if "not found" in check or "invalid" in check or "error" in check:
            typer.echo(f"  {check}")
            has_errors = True
        else:
            typer.echo(f"  {check}")

    # Exit with error if any checks failed
    if has_errors:
        raise typer.Exit(1)
