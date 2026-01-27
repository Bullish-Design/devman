# src/devman/commands/test.py
"""Test command implementation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional

import typer

from devman.container import (
    cleanup_container,
    create_container,
    run_container_tests,
)
from devman.jj_info import get_jj_info


def test_command(
    devman_dir: Path = typer.Option(
        Path(".devman"),
        "--devman-dir",
        help="Path to .devman directory.",
    ),
    keep_container: bool = typer.Option(
        False,
        "--keep-container",
        help="Don't remove container after test.",
    ),
    container_name: Optional[str] = typer.Option(
        None,
        "--container-name",
        help="Override container name.",
    ),
) -> None:
    """Test devenv.nix in container."""
    if not devman_dir.exists():
        typer.echo(f"Error: {devman_dir} does not exist.", err=True)
        raise typer.Exit(1)

    # Get container name
    if container_name:
        name = container_name
    else:
        jj_info = get_jj_info()
        bookmark = jj_info.get("bookmark") or "unknown"
        change_id = jj_info.get("change_id") or "00000000"
        name = f"devman-{bookmark}-{change_id[:8]}"

    try:
        typer.echo(f"Creating container: {name}")
        create_container(name, devman_dir)

        typer.echo("Running tests in container...")
        run_container_tests(name, devman_dir)

        # Check for test results
        results_file = devman_dir / "test-results" / "report.json"
        if results_file.exists():
            with open(results_file) as f:
                results = json.load(f)

            typer.echo("\nTest Results:")
            typer.echo(f"  Status: {results.get('status', 'unknown')}")
            typer.echo(f"  Tests run: {results.get('tests_run', 0)}")
            typer.echo(f"  Passed: {results.get('tests_passed', 0)}")
            typer.echo(f"  Failed: {results.get('tests_failed', 0)}")

            if results.get("status") != "pass":
                raise typer.Exit(1)
        else:
            typer.echo("Tests completed (no report generated)")

    except subprocess.CalledProcessError as exc:
        typer.echo(f"Error during container test: {exc}", err=True)
        raise typer.Exit(1)
    finally:
        if not keep_container:
            typer.echo(f"Cleaning up container: {name}")
            cleanup_container(name)
        else:
            typer.echo(f"Container kept: {name}")
