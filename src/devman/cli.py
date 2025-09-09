# src/devenv_templater/cli.py
"""Command line interface for devenv-templater."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import ProjectConfig
from .templater import DevEnvTemplater

console = Console()
app = typer.Typer(
    name="devenv-templater",
    help="🚀 Generate NixOS devenv projects from templates",
    rich_markup_mode="rich"
)

@app.command()
def new(
    name: Annotated[str, typer.Argument(help="Project name")],
    project_type: Annotated[str, typer.Option("--type", "-t", help="Project type")] = "api",
    python_version: Annotated[str, typer.Option("--python", "-p", help="Python version")] = "3.11",
    container_type: Annotated[Optional[str], typer.Option("--containers", "-c", help="Container type")] = "devenv",
    database: Annotated[Optional[str], typer.Option("--database", "-d", help="Database type")] = None,
    dependencies: Annotated[Optional[list[str]], typer.Option("--deps", help="Additional dependencies")] = None,
    dev_dependencies: Annotated[Optional[list[str]], typer.Option("--dev-deps", help="Development dependencies")] = None,
    local_dependencies: Annotated[Optional[list[str]], typer.Option("--local-deps", help="Local path dependencies")] = None,
    directory: Annotated[Optional[str], typer.Option("--dir", "-D", help="Target directory")] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Overwrite existing files")] = False,
) -> None:
    """Create a new devenv project from templates."""
    
    target_dir = Path(directory) if directory else Path(name)
    
    if target_dir.exists() and any(target_dir.iterdir()) and not force:
        console.print(f"❌ Directory {target_dir} already exists and is not empty. Use --force to overwrite.", style="red")
        raise typer.Exit(1)
    
    # Validate project type
    valid_types = ["api", "web", "cli", "ml", "lib"]
    if project_type not in valid_types:
        console.print(f"❌ Invalid project type. Choose from: {', '.join(valid_types)}", style="red")
        raise typer.Exit(1)
    
    # Validate container type
    valid_containers = ["devenv", "docker", "nixos", "none"]
    if container_type and container_type not in valid_containers:
        console.print(f"❌ Invalid container type. Choose from: {', '.join(valid_containers)}", style="red")
        raise typer.Exit(1)
    
    config = ProjectConfig(
        name=name,
        python_version=python_version,
        project_type=project_type,
        container_type=container_type or "none",
        dependencies=dependencies or [],
        dev_dependencies=dev_dependencies or [],
        local_dependencies=local_dependencies or [],
        use_database=bool(database),
        database_type=database or "postgresql"
    )
    
    templater = DevEnvTemplater()
    
    with console.status(f"[bold blue]Creating project {name}..."):
        templater.generate_project(config, target_dir)
    
    # Success output
    console.print(Panel.fit(
        f"[bold green]✅ Project '{name}' created successfully![/bold green]\n\n"
        f"[bold]Next steps:[/bold]\n"
        f"1. [cyan]cd {target_dir}[/cyan]\n"
        f"2. [cyan]just shell[/cyan] (enter development environment)\n"
        f"3. [cyan]just dev[/cyan] (start development server)\n\n"
        f"[dim]View all commands: [cyan]just --list[/cyan][/dim]",
        title="🚀 Ready to develop!",
        border_style="green"
    ))

@app.command()
def update(
    name: Annotated[str, typer.Argument(help="Project name")],
    project_type: Annotated[Optional[str], typer.Option("--type", "-t", help="Project type")] = None,
    python_version: Annotated[Optional[str], typer.Option("--python", "-p", help="Python version")] = None,
    container_type: Annotated[Optional[str], typer.Option("--containers", "-c", help="Container type")] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Overwrite existing files")] = False,
) -> None:
    """Update existing project files from templates."""
    
    if not Path("pyproject.toml").exists():
        console.print("❌ No pyproject.toml found. Are you in a project directory?", style="red")
        raise typer.Exit(1)
    
    # Load existing config or use defaults
    config = ProjectConfig(
        name=name,
        python_version=python_version or "3.11",
        project_type=project_type or "api",
        container_type=container_type or "none"
    )
    
    templater = DevEnvTemplater()
    
    if not force:
        console.print("⚠️ This will overwrite configuration files. Continue?", style="yellow")
        if not typer.confirm(""):
            console.print("❌ Update cancelled.")
            raise typer.Exit(0)
    
    with console.status("[bold blue]Updating project files..."):
        templater.generate_project(config, Path("."))
    
    console.print("✅ Project files updated!", style="green")

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

@app.command()
def config() -> None:
    """Show current configuration and status."""
    
    templater = DevEnvTemplater()
    
    table = Table(title="⚙️ Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")
    
    table.add_row("Templates directory", str(templater.templates_dir))
    table.add_row("Templates exist", "✅ Yes" if templater.templates_dir.exists() else "❌ No")
    
    if templater.templates_dir.exists():
        template_files = list(templater.templates_dir.glob("*.j2"))
        table.add_row("Template count", str(len(template_files)))
    
    console.print(table)

@app.command()
def init_templates(
    force: Annotated[bool, typer.Option("--force", "-f", help="Overwrite existing templates")] = False
) -> None:
    """Initialize or update template files."""
    
    templater = DevEnvTemplater()
    
    if templater.templates_dir.exists() and not force:
        console.print(f"Templates already exist at {templater.templates_dir}")
        if not typer.confirm("Overwrite existing templates?"):
            raise typer.Exit(0)
    
    with console.status("[bold blue]Creating template files..."):
        templater.ensure_templates_exist()
    
    console.print(f"✅ Templates initialized at {templater.templates_dir}", style="green")

if __name__ == "__main__":
    app()