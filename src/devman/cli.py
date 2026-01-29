# src/devman/cli.py
"""Command-line interface for devman."""

from __future__ import annotations

from pathlib import Path

import typer
from copier import run_copy

from devman import __version__
from devman.application.use_cases import (
    FindDevmanCommand,
    FindDevmanUseCase,
    RunDevenvCommand,
    RunDevenvUseCase,
    ValidateTemplateCommand,
    ValidateTemplateUseCase,
)
from devman.config import load_config
from devman.domain.models import ProjectRoot
from devman.templates import TemplateReference


# Re-export domain DevmanFinder for backward compatibility
from devman.domain.finder import DevmanFinder as _DomainFinder  # noqa: F401


class DevmanFinder:
    """Locate the nearest devman configuration directory.

    Legacy wrapper for backward compatibility.
    Prefer using devman.domain.finder.DevmanFinder directly.
    """

    def __init__(self, projects_root: Path | None = None) -> None:
        self.projects_root = projects_root

    @classmethod
    def from_config(cls) -> DevmanFinder:
        config = load_config()
        return cls(projects_root=config.projects_root)

    def find(self, start_path: Path | None = None) -> Path | None:
        """Find .devman directory, returning Path or None for backward compat."""
        root = None
        if self.projects_root is not None:
            root_result = ProjectRoot.create(self.projects_root)
            if root_result.is_ok():
                root = root_result.unwrap()

        domain_finder = _DomainFinder(projects_root=root)
        result = domain_finder.find(start_path=start_path)

        if result.is_ok():
            return result.unwrap().path
        return None


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
    find_command = FindDevmanCommand(projects_root=root)
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
    # Parse template reference
    try:
        template_ref = TemplateReference.from_string(template_source)
    except ValueError as e:
        typer.echo(f"Invalid template source: {e}", err=True)
        raise typer.Exit(1)

    # Validate if requested
    if validate:
        typer.echo("Validating template...")

        validate_use_case = ValidateTemplateUseCase()
        validate_command = ValidateTemplateCommand(template_reference=template_ref)
        validate_result = validate_use_case.execute(validate_command)

        vr = validate_result.validation_result

        if not vr.is_valid:
            typer.echo("Template validation errors:", err=True)
            for error in vr.errors:
                loc = f" ({error.location})" if error.location else ""
                typer.echo(f"  - {error.message}{loc}", err=True)
            raise typer.Exit(1)

        if vr.warnings:
            typer.echo("Template warnings:")
            for warning in vr.warnings:
                loc = f" ({warning.location})" if warning.location else ""
                typer.echo(f"  - {warning.message}{loc}")

    # Parse data overrides
    data_dict = {}
    for item in data:
        if "=" not in item:
            typer.echo(f"Invalid data format: {item} (expected key=value)", err=True)
            raise typer.Exit(1)
        key, value = item.split("=", 1)
        data_dict[key] = value

    # Run copier
    try:
        typer.echo(f"Creating project at {destination}...")

        source = template_ref.location
        if template_ref.source_type == "file":
            source = str(template_ref.resolve_path())

        run_copy(
            src_path=source,
            dst_path=str(destination),
            data=data_dict if data_dict else None,
            unsafe=True,
        )

        typer.echo(f"Project created successfully at {destination}")

    except Exception as e:
        typer.echo(f"Failed to create project: {e}", err=True)
        raise typer.Exit(1)


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

    if show:
        current_config = load_config()
        typer.echo("Current configuration:")
        if current_config.projects_root is None:
            typer.echo("  projects_root: (not set)")
        else:
            typer.echo(f"  projects_root: {current_config.projects_root}")

    if projects_root is not None:
        config_path = Path("~/.config/devman/config.env").expanduser()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_root = projects_root.expanduser().resolve()
        config_path.write_text(
            f"DEVMAN_PROJECTS_ROOT={resolved_root}\n",
            encoding="utf-8",
        )
        typer.echo(f"Updated projects root to {resolved_root}.")


@app.command()
def version() -> None:
    """Show the devman version."""
    typer.echo(f"devman {__version__}")


@app.command()
def hello(name: str) -> None:
    """Say hello to the provided name."""
    typer.echo(f"Hello, {name}!")
