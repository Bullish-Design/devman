# src/devman/cli.py
"""Command-line interface for devman."""

from __future__ import annotations

import os
import subprocess

from pathlib import Path

import typer

from devman import __version__
from devman.application.use_cases import (
    CreateProjectCommand,
    CreateProjectUseCase,
    FindDevmanCommand,
    FindDevmanUseCase,
    RunDevenvCommand,
    RunDevenvUseCase,
)
from devman.config import ConfigRepository, load_config
from devman.domain.models import ProjectRoot


app = typer.Typer()


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def run(
    ctx: typer.Context,
    projects_root: Path | None = typer.Option(None, "--projects-root"),
) -> None:
    """Run a command within the nearest devman project."""
    # Build projects root if provided
    root: ProjectRoot | None = None
    if projects_root:
        root_result = ProjectRoot.create(projects_root)
        if root_result.is_err():
            typer.echo(f"Invalid projects root: {root_result.unwrap_err()}", err=True)
            raise typer.Exit(1)
        root = root_result.unwrap()
    else:
        # Try to load from config
        config = load_config()
        if config.projects_root:
            root_result = ProjectRoot.create(config.projects_root)
            if root_result.is_ok():
                root = root_result.unwrap()

    # Execute find use case
    find_use_case = FindDevmanUseCase()
    find_command = FindDevmanCommand(start_path=Path.cwd(), projects_root=root)
    find_result = find_use_case.execute(find_command)

    if find_result.is_err():
        typer.echo(str(find_result.unwrap_err()), err=True)
        raise typer.Exit(1)

    devman_dir = find_result.unwrap().devman_directory

    # Execute run use case
    run_use_case = RunDevenvUseCase()
    run_cmd = RunDevenvCommand(
        devenv_args=ctx.args,
        devman_directory=devman_dir,
    )
    run_result = run_use_case.execute(run_cmd)

    if run_result.is_err():
        error = run_result.unwrap_err()
        typer.echo(str(error), err=True)
        if error.stderr:
            typer.echo(error.stderr, err=True)
        raise typer.Exit(error.exit_code)

    raise typer.Exit(run_result.unwrap().exit_code)


@app.command()
def launch(
    projects_root: Path | None = typer.Option(None, "--projects-root"),
    shell: str = typer.Option("zsh", "--shell", "-s", help="Shell to launch"),
) -> None:
    """Launch devenv services and enter interactive shell."""
    import os
    import subprocess

    # Build projects root if provided
    root: ProjectRoot | None = None
    if projects_root:
        root_result = ProjectRoot.create(projects_root)
        if root_result.is_err():
            typer.echo(f"Invalid projects root: {root_result.unwrap_err()}", err=True)
            raise typer.Exit(1)
        root = root_result.unwrap()
    else:
        config = load_config()
        if config.projects_root:
            root_result = ProjectRoot.create(config.projects_root)
            if root_result.is_ok():
                root = root_result.unwrap()

    # Find .devman directory
    find_use_case = FindDevmanUseCase()
    find_command = FindDevmanCommand(start_path=Path.cwd(), projects_root=root)
    find_result = find_use_case.execute(find_command)

    if find_result.is_err():
        typer.echo(str(find_result.unwrap_err()), err=True)
        raise typer.Exit(1)

    devman_dir = find_result.unwrap().devman_directory

    # Start services in detached mode (allow failure if no processes defined)
    result = subprocess.run(
        ["devenv", "up", "-d"],
        cwd=devman_dir.path,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        if (
            "No processes defined" in result.stderr
            or "No 'processes' option" in result.stderr
        ):
            typer.echo("No processes defined, skipping service startup.")
        else:
            typer.echo(f"Warning: Failed to start services: {result.stderr.strip()}")

    typer.echo()  # Blank line

    # Replace current process with interactive shell, starting in project root
    os.chdir(devman_dir.path)
    os.execvp(
        "devenv", ["devenv", "shell", shell]
    )  # , "-c", f"cd .. && exec {shell}"])


@app.command()
def new(
    template_source: str = typer.Argument(..., help="Template path or git URL"),
    destination: Path = typer.Argument(..., help="Destination directory"),
    validate: bool = typer.Option(
        True, "--validate/--no-validate", help="Validate template before use"
    ),
    data: list[str] = typer.Option(
        [], "--data", "-d", help="Override template data (key=value)"
    ),
) -> None:
    """Create a new project from a copier template."""
    # Parse data overrides
    data_dict: dict[str, str] = {}
    for item in data:
        if "=" not in item:
            typer.echo(f"Invalid data format: {item} (expected key=value)", err=True)
            raise typer.Exit(1)
        key, value = item.split("=", 1)
        data_dict[key] = value

    # Execute use case
    use_case = CreateProjectUseCase()
    command = CreateProjectCommand(
        template_source=template_source,
        destination=destination,
        data=data_dict,
        validate=validate,
    )

    typer.echo(f"Creating project at {destination}...")
    result = use_case.execute(command)

    if result.is_err():
        error = result.unwrap_err()

        # Show validation errors if present
        if error.validation_result and not error.validation_result.is_valid:
            typer.echo("Template validation errors:", err=True)
            for issue in error.validation_result.errors:
                loc = f" ({issue.location})" if issue.location else ""
                typer.echo(f"  - {issue.message}{loc}", err=True)
        else:
            typer.echo(error.message, err=True)

        raise typer.Exit(1)

    success = result.unwrap()

    # Show warnings if any
    if success.validation_result and success.validation_result.warnings:
        typer.echo("Template warnings:")
        for warning in success.validation_result.warnings:
            loc = f" ({warning.location})" if warning.location else ""
            typer.echo(f"  - {warning.message}{loc}")

    typer.echo(f"Project created successfully at {destination}")


@app.command()
def config(
    projects_root: Path | None = typer.Option(
        None,
        help="Set projects root directory",
    ),
    show: bool = typer.Option(False, "--show", help="Show current configuration"),
) -> None:
    """Show or update devman configuration."""
    if projects_root is None and not show:
        typer.echo("No configuration changes provided.", err=True)
        raise typer.Exit(1)

    repo = ConfigRepository()

    if show:
        current_config = repo.load()
        typer.echo("Current configuration:")
        if current_config.projects_root is None:
            typer.echo("  projects_root: (not set)")
        else:
            typer.echo(f"  projects_root: {current_config.projects_root}")

    if projects_root is not None:
        repo.save_projects_root(projects_root)
        resolved = projects_root.expanduser().resolve()
        typer.echo(f"Updated projects root to {resolved}.")


@app.command()
def version() -> None:
    """Show the devman version."""
    typer.echo(f"devman {__version__}")


@app.command()
def hello(name: str) -> None:
    """Say hello to the provided name."""
    typer.echo(f"Hello, {name}!")
