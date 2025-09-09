# src/devman/cli.py
"""Command line interface for devman."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import ProjectConfig
from .devman_config import DevmanConfig
from .templater import DevEnvTemplater

console = Console()
app = typer.Typer(
    name="devman",
    help="🚀 Generate NixOS devenv projects from templates",
    rich_markup_mode="rich",
    no_args_is_help=True,
)


@app.command(no_args_is_help=True)
def init(
    name: Annotated[str, typer.Argument(help="Project name")],
    project_type: Annotated[str, typer.Option("--type", "-t", help="Project type")] = "api",
    python_version: Annotated[str, typer.Option("--python", "-p", help="Python version")] = "3.11",
    container_type: Annotated[Optional[str], typer.Option("--containers", "-c", help="Container type")] = "devenv",
    database: Annotated[Optional[str], typer.Option("--database", "-d", help="Database type")] = None,
    dependencies: Annotated[Optional[list[str]], typer.Option("--deps", help="Additional dependencies")] = None,
    dev_dependencies: Annotated[Optional[list[str]], typer.Option("--dev-deps", help="Development dependencies")] = None,
    local_dependencies: Annotated[
        Optional[list[str]],
        typer.Option("--local-deps", help="Local path dependencies"),
    ] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Overwrite existing config")] = False,
    no_format: Annotated[bool, typer.Option("--no-format", help="Disable rich formatting")] = False,
) -> None:
    """Initialize devman.toml configuration file."""
    if no_format:
        os.environ["NO_COLOR"] = "1"

    config_path = Path.cwd() / ".devman" / "devman.toml"

    if config_path.exists() and not force:
        console.print(
            f"⚠️ Configuration already exists at {config_path}. Use --force to overwrite.",
            style="red",
        )
        raise typer.Exit(1)

    # Validate project type
    valid_types = ["api", "web", "cli", "ml", "lib"]
    if project_type not in valid_types:
        console.print(
            f"❌ Invalid project type. Choose from: {', '.join(valid_types)}",
            style="red",
        )
        raise typer.Exit(1)

    # Validate container type
    valid_containers = ["devenv", "docker", "nixos", "none"]
    if container_type and container_type not in valid_containers:
        console.print(
            f"❌ Invalid container type. Choose from: {', '.join(valid_containers)}",
            style="red",
        )
        raise typer.Exit(1)

    try:
        project_config = ProjectConfig(
            name=name,
            python_version=python_version,
            project_type=project_type,
            container_type=container_type or "none",
            dependencies=dependencies or [],
            dev_dependencies=dev_dependencies or [],
            local_dependencies=local_dependencies or [],
            use_database=bool(database),
            database_type=database or "postgresql",
        )

        devman_config = DevmanConfig.create_from_project_config(project_config)

        with console.status(f"[bold blue]Creating configuration..."):
            devman_config.save()

        console.print(
            Panel.fit(
                f"[bold green]✅ Configuration created![/bold green]\n\n"
                f"[bold]Configuration saved to:[/bold] {config_path}\n\n"
                f"[bold]Next steps:[/bold]\n"
                f"1. [cyan]devman generate[/cyan] (generate project files)\n"
                f"2. [cyan]just shell[/cyan] (enter development environment)\n\n"
                f"[dim]Edit {config_path} to customize before generating[/dim]",
                title="🚀 Ready to generate!",
                border_style="green",
            )
        )

    except Exception as e:
        console.print(f"❌ Configuration error: {e}", style="red")
        raise typer.Exit(1)


@app.command()
def generate(
    force: Annotated[bool, typer.Option("--force", "-f", help="Overwrite existing files")] = False,
    no_format: Annotated[bool, typer.Option("--no-format", help="Disable rich formatting")] = False,
) -> None:
    """Generate project files from devman.toml configuration."""
    if no_format:
        os.environ["NO_COLOR"] = "1"

    config_path = Path.cwd() / ".devman" / "devman.toml"

    if not config_path.exists():
        console.print(
            "❌ No devman.toml found. Run 'devman init' first.",
            style="red",
        )
        raise typer.Exit(1)

    try:
        devman_config = DevmanConfig.from_file(config_path)

        # Check for existing files if not forcing
        if not force:
            existing_files = []
            for template_file in devman_config.templates.files:
                output_file = template_file.replace(".j2", "")
                if (Path.cwd() / output_file).exists():
                    existing_files.append(output_file)

            if existing_files:
                console.print(
                    f"⚠️ Files already exist: {', '.join(existing_files)}. Use --force to overwrite.",
                    style="yellow",
                )
                if not typer.confirm("Continue?"):
                    raise typer.Exit(0)

        templater = DevEnvTemplater()

        with console.status(f"[bold blue]Generating project files..."):
            generated_files = templater.generate_from_config(devman_config, Path.cwd())

        # Update config with generation metadata
        devman_config.mark_generated(generated_files)
        devman_config.save()

        console.print(
            Panel.fit(
                f"[bold green]✅ Project generated successfully![/bold green]\n\n"
                f"[bold]Generated files:[/bold]\n" + "\n".join(f"• {file}" for file in generated_files) + "\n\n"
                f"[bold]Next steps:[/bold]\n"
                f"1. [cyan]just shell[/cyan] (enter development environment)\n"
                f"2. [cyan]just dev[/cyan] (start development server)\n\n"
                f"[dim]View all commands: [cyan]just --list[/cyan][/dim]",
                title="🚀 Ready to develop!",
                border_style="green",
            )
        )

    except Exception as e:
        console.print(f"❌ Generation error: {e}", style="red")
        raise typer.Exit(1)


@app.command(no_args_is_help=True)
def update(
    project_type: Annotated[Optional[str], typer.Option("--type", "-t", help="Project type")] = None,
    python_version: Annotated[Optional[str], typer.Option("--python", "-p", help="Python version")] = None,
    container_type: Annotated[Optional[str], typer.Option("--containers", "-c", help="Container type")] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Overwrite existing files")] = False,
    no_format: Annotated[bool, typer.Option("--no-format", help="Disable rich formatting")] = False,
) -> None:
    """Update existing devman.toml configuration."""
    if no_format:
        os.environ["NO_COLOR"] = "1"

    config_path = Path.cwd() / ".devman" / "devman.toml"

    if not config_path.exists():
        console.print(
            "❌ No devman.toml found. Run 'devman init' first.",
            style="red",
        )
        raise typer.Exit(1)

    try:
        devman_config = DevmanConfig.from_file(config_path)

        # Update fields if provided
        updated = False
        if project_type is not None:
            devman_config.project.project_type = project_type
            updated = True
        if python_version is not None:
            devman_config.project.python_version = python_version
            updated = True
        if container_type is not None:
            devman_config.project.container_type = container_type
            updated = True

        if updated:
            devman_config.ensure_templates_list()
            devman_config.update_metadata()

            if not force:
                console.print("⚠️ This will update your configuration. Continue?", style="yellow")
                if not typer.confirm(""):
                    console.print("❌ Update cancelled.")
                    raise typer.Exit(0)

            devman_config.save()
            console.print("✅ Configuration updated!", style="green")
        else:
            console.print("ℹ️ No changes specified.", style="blue")

    except Exception as e:
        console.print(f"❌ Update error: {e}", style="red")
        raise typer.Exit(1)


@app.command()
def status() -> None:
    """Show project status and configuration."""
    config_path = Path.cwd() / ".devman" / "devman.toml"

    if not config_path.exists():
        console.print("❌ No devman.toml found. Run 'devman init' first.", style="red")
        raise typer.Exit(1)

    try:
        devman_config = DevmanConfig.from_file(config_path)

        table = Table(title="📋 Project Status")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Project Name", devman_config.project.name)
        table.add_row("Project Type", devman_config.project.project_type)
        table.add_row("Python Version", devman_config.project.python_version)
        table.add_row("Container Type", devman_config.project.container_type)
        table.add_row("Devman Version", devman_config.devman.version)
        table.add_row("Created", devman_config.devman.created_at.strftime("%Y-%m-%d %H:%M"))
        table.add_row("Updated", devman_config.devman.updated_at.strftime("%Y-%m-%d %H:%M"))

        if devman_config.generation.last_generated:
            table.add_row(
                "Last Generated",
                devman_config.generation.last_generated.strftime("%Y-%m-%d %H:%M"),
            )
            table.add_row("Generated Files", str(len(devman_config.generation.generated_files)))

        console.print(table)

    except Exception as e:
        console.print(f"❌ Status error: {e}", style="red")
        raise typer.Exit(1)


@app.command()
def list_templates() -> None:
    """List available project templates."""
    table = Table(title="📋 Available Templates")
    table.add_column("Type", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Features", style="dim")

    templates = [
        ("api", "FastAPI REST API", "FastAPI, uvicorn, async"),
        ("web", "Flask web application", "Flask, templates, static files"),
        ("cli", "Command line interface", "Click/Typer, entry points"),
        ("ml", "Machine learning project", "scikit-learn, jupyter, data tools"),
        ("lib", "Python library", "Publishing ready, minimal deps"),
    ]

    for template_type, desc, features in templates:
        table.add_row(template_type, desc, features)

    console.print(table)


if __name__ == "__main__":
    app()

