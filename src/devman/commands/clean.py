# src/devman/commands/clean.py
"""Clean command implementation."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

import typer

from devman.container import cleanup_container, list_devman_containers
from devman.jj_info import get_jj_info


def clean_command(
    devman_dir: Path = typer.Option(
        Path(".devman"),
        "--devman-dir",
        help="Path to .devman directory.",
    ),
    all: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Remove all generated artifacts, including caches.",
    ),
    container_name: Optional[str] = typer.Option(
        None,
        "--container-name",
        help="Specific container to clean.",
    ),
    all_containers: bool = typer.Option(
        False,
        "--all-containers",
        help="Remove all DevMan containers.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be removed without removing.",
    ),
) -> None:
    """Remove DevMan-generated artifacts from the working tree."""
    removed_items = []

    # Container cleanup
    if all_containers:
        try:
            containers = list_devman_containers()
        except subprocess.CalledProcessError:
            containers = []
        for container in containers:
            if not dry_run:
                try:
                    cleanup_container(container)
                    removed_items.append(f"Container: {container}")
                except subprocess.CalledProcessError as exc:
                    typer.echo(f"Warning: Failed to remove {container}: {exc}", err=True)
            else:
                removed_items.append(f"[DRY RUN] Container: {container}")
    elif container_name:
        if not dry_run:
            try:
                cleanup_container(container_name)
                removed_items.append(f"Container: {container_name}")
            except subprocess.CalledProcessError as exc:
                typer.echo(f"Error removing container: {exc}", err=True)
                raise typer.Exit(1)
        else:
            removed_items.append(f"[DRY RUN] Container: {container_name}")
    else:
        # Clean current branch container
        jj_info = get_jj_info()
        bookmark = jj_info.get("bookmark")
        if bookmark:
            try:
                containers = list_devman_containers()
            except subprocess.CalledProcessError:
                containers = []
            for container in containers:
                if container.startswith(f"devman-{bookmark}-"):
                    if not dry_run:
                        try:
                            cleanup_container(container)
                            removed_items.append(f"Container: {container}")
                        except subprocess.CalledProcessError as exc:
                            typer.echo(
                                f"Warning: Failed to remove {container}: {exc}",
                                err=True,
                            )
                    else:
                        removed_items.append(f"[DRY RUN] Container: {container}")

    # File cleanup
    if devman_dir.exists():
        test_results = devman_dir / "test-results"
        if test_results.exists():
            if not dry_run:
                shutil.rmtree(test_results)
                removed_items.append(f"Directory: {test_results}")
            else:
                removed_items.append(f"[DRY RUN] Directory: {test_results}")

        if all:
            for dirname in [".devenv", ".direnv"]:
                dirpath = devman_dir / dirname
                if dirpath.exists():
                    if not dry_run:
                        shutil.rmtree(dirpath)
                        removed_items.append(f"Directory: {dirpath}")
                    else:
                        removed_items.append(f"[DRY RUN] Directory: {dirpath}")

    if removed_items:
        typer.echo("Cleaned:")
        for item in removed_items:
            typer.echo(f"  {item}")
    else:
        typer.echo("Nothing to clean")
