"""Command-line interface for devman."""

from __future__ import annotations

import subprocess
from pathlib import Path

import typer
from copier import run_copy

from devman.config import DevmanConfig, load_config
from devman.templates import TemplateReference, TemplateValidator


class DevmanFinder:
    """Locate the nearest devman configuration directory."""

    def __init__(self, projects_root: Path | None = None) -> None:
        self.projects_root = projects_root

    @classmethod
    def from_config(cls, config: DevmanConfig | None = None) -> DevmanFinder:
        resolved_config = config or load_config()
        return cls(projects_root=resolved_config.projects_root)

    def find(self, start_path: Path | None = None) -> Path | None:
        current = (start_path or Path.cwd()).resolve()
        projects_root = self.projects_root.resolve() if self.projects_root else None

        while True:
            candidate = current / ".devman"
            if candidate.is_dir():
                return candidate
            if projects_root is not None and current == projects_root:
                break
            if current.parent == current:
                break
            current = current.parent

        return None


app = typer.Typer()


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def run(
    ctx: typer.Context,
    projects_root: Path | None = typer.Option(None, "--projects-root"),
) -> None:
    """Run a command within the nearest devman project."""
    if projects_root is None:
        finder = DevmanFinder.from_config()
    else:
        finder = DevmanFinder(projects_root=projects_root)

    devman_dir = finder.find()
    if devman_dir is None:
        typer.echo("No .devman directory found.", err=True)
        raise typer.Exit(1)

    result = subprocess.run(["devenv", *ctx.args], cwd=devman_dir)
    raise typer.Exit(result.returncode)


@app.command()
def new(
    template_source: str = typer.Argument(..., help="Template path or git URL"),
    destination: Path = typer.Argument(..., help="Destination directory"),
    validate: bool = typer.Option(True, "--validate/--no-validate", help="Validate template before use"),
    data: list[str] = typer.Option([], "--data", "-d", help="Override template data (key=value)"),
) -> None:
    """Create a new project from a copier template."""

    # Parse template reference
    try:
        template_ref = TemplateReference.from_string(template_source)
    except ValueError as e:
        typer.echo(f"Invalid template source: {e}", err=True)
        raise typer.Exit(1)

    # Validate template if requested
    if validate:
        typer.echo("Validating template...")
        issues = TemplateValidator.validate(template_ref)

        if issues["errors"]:
            typer.echo("Template validation errors:", err=True)
            for error in issues["errors"]:
                typer.echo(f"  - {error}", err=True)
            raise typer.Exit(1)

        if issues["warnings"]:
            typer.echo("Template warnings:")
            for warning in issues["warnings"]:
                typer.echo(f"  - {warning}")

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
            unsafe=True,  # Allow running tasks
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
    typer.echo("devman 0.1.0")


@app.command()
def hello(name: str) -> None:
    """Say hello to the provided name."""
    typer.echo(f"Hello, {name}!")
