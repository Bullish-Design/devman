# src/devman/cli.py
from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .models import ProjectConfig, TemplateEngine
from .config import UserConfig, ConfigManager
from .remote import TemplateRegistry
from .security import SecurityConfig, SecurityManager
from .exceptions import (
    DevmanError,
    TemplateNotFoundError,
    InvalidProjectNameError,
    ProjectExistsError,
    ConfigurationError,
)

app = typer.Typer(name="devman", help="UV-powered Python project generator")
console = Console()

BUILTIN_TEMPLATES = {
    "python-lib": "Python library with UV",
    "python-cli": "Typer CLI application",
    "fastapi-api": "FastAPI web service",
}


def handle_errors(func):
    """Decorator to handle common errors gracefully."""

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except DevmanError as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)
        except KeyboardInterrupt:
            console.print("\n[yellow]Operation cancelled by user[/yellow]")
            sys.exit(1)
        except Exception as e:
            console.print(f"[red]Unexpected error: {e}[/red]")
            console.print("[dim]Run with --verbose for more details[/dim]")
            sys.exit(1)

    return wrapper


@app.command("list")
# @handle_errors
def list_templates(remote: bool = typer.Option(False, "--remote", help="List remote templates")) -> None:
    """List available templates."""
    if remote:
        registry = TemplateRegistry.load()
        if registry.templates:
            console.print(registry.list_templates())
        else:
            console.print("[yellow]No remote templates registered[/yellow]")
            console.print("[dim]Add templates with: devman template add NAME URL[/dim]")
    else:
        table = Table(title="Built-in Templates")
        table.add_column("Template", style="bold")
        table.add_column("Description")

        for slug, desc in BUILTIN_TEMPLATES.items():
            table.add_row(slug, desc)
        console.print(table)


@app.command()
# @handle_errors
def generate(
    name: str = typer.Argument(..., help="Project name/directory"),
    template: Optional[str] = typer.Option(
        None, "-t", "--template", help="Template to use (local, remote, or gh:org/repo)"
    ),
    python: Optional[str] = typer.Option(None, "-p", "--python", help="Python version"),
    package: Optional[str] = typer.Option(None, "-k", "--package", help="Package name override"),
    force: bool = typer.Option(False, "-f", "--force", help="Overwrite existing files"),
    demo: bool = typer.Option(False, "--demo", help="Preview only, don't write files"),
    plan_json: Optional[Path] = typer.Option(None, "--plan-json", help="Export plan as JSON"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Show detailed output"),
    # Security options
    enable_security: bool = typer.Option(True, "--security/--no-security", help="Enable security features"),
    pre_commit: bool = typer.Option(True, "--pre-commit/--no-pre-commit", help="Setup pre-commit hooks"),
    security_scan: bool = typer.Option(True, "--security-scan/--no-security-scan", help="Enable security scanning"),
    secret_detection: bool = typer.Option(
        True, "--secret-detection/--no-secret-detection", help="Enable secret detection"
    ),
) -> None:
    """Generate a new Python project."""

    # Load user configuration for defaults
    try:
        user_config = UserConfig.load()
    except ConfigurationError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        console.print("[dim]Fix your config file or run 'devman config --init'[/dim]")
        sys.exit(1)

    # Apply defaults from config
    template = template or user_config.default_template
    python = python or user_config.default_python_version

    # Setup paths
    destination = Path.cwd() / name

    # Create security configuration
    security_config = SecurityConfig(
        enable_pre_commit=pre_commit and enable_security,
        enable_dependency_scan=security_scan and enable_security,
        enable_secret_detection=secret_detection and enable_security,
        enable_security_linting=security_scan and enable_security,
        enable_vulnerability_scan=security_scan and enable_security,
        bandit_enabled=security_scan and enable_security,
        safety_enabled=security_scan and enable_security,
    )

    # Create and validate config
    try:
        config = ProjectConfig(
            project_name=name,
            package_name=package or "",
            python_version=python,
            use_nix=user_config.use_nix,
            use_docker=user_config.use_docker,
            use_just=user_config.use_just,
            security=security_config,
        )
    except ValueError as e:
        raise InvalidProjectNameError(str(e))

    # Initialize engine with template registry
    engine = TemplateEngine()

    if demo:
        # Create and display plan
        if verbose:
            console.print(f"[dim]Creating plan for template: {template}[/dim]")

        plan = engine.create_plan(template, destination, config)

        # Show summary
        summary = plan.get_summary()
        console.print(
            Panel(
                f"[bold]Files to create:[/bold] {summary['total_files']}\n"
                f"[bold]Conflicts:[/bold] {summary['conflicts']}\n"
                f"[bold]Template:[/bold] {summary['template']}\n"
                f"[bold]Destination:[/bold] {summary['destination']}\n"
                f"[bold]Security:[/bold] {'Enabled' if enable_security else 'Disabled'}",
                title="Generation Plan Summary",
                border_style="blue",
            )
        )

        # Show detailed file list
        table = Table(title="Files")
        table.add_column("File", style="cyan")
        table.add_column("Size", justify="right")
        table.add_column("Status")

        for rel_path, snapshot in plan.files.items():
            status = "[red]conflict[/red]" if rel_path in plan.conflicts else "[green]create[/green]"
            size_str = f"{snapshot.size:,} bytes" if not snapshot.is_binary else f"{snapshot.size:,} bytes (binary)"
            table.add_row(rel_path, size_str, status)

        console.print(table)

        if plan.conflicts:
            console.print(
                f"\n[yellow]Warning: {len(plan.conflicts)} file(s) would be overwritten. Use --force to proceed.[/yellow]"
            )

        # Export plan if requested
        if plan_json:
            plan_data = {
                "summary": summary,
                "files": {k: v.model_dump() for k, v in plan.files.items()},
                "conflicts": plan.conflicts,
            }
            plan_json.write_text(json.dumps(plan_data, indent=2), encoding="utf-8")
            console.print(f"[green]Plan exported to {plan_json}[/green]")

        console.print("[yellow]Demo complete - no files written[/yellow]")
        return

    # Check for conflicts before generation
    if not force:
        try:
            plan = engine.create_plan(template, destination, config)
            if plan.conflicts:
                console.print(f"[red]Error: {len(plan.conflicts)} file(s) already exist:[/red]")
                for conflict in plan.conflicts[:5]:  # Show first 5
                    console.print(f"  - {conflict}")
                if len(plan.conflicts) > 5:
                    console.print(f"  ... and {len(plan.conflicts) - 5} more")
                console.print("[dim]Use --force to overwrite existing files[/dim]")
                sys.exit(1)
        except Exception:
            # If planning fails, we'll catch it during generation
            pass

    # Generate project
    status_msg = f"Generating {name} from {template}..."
    if verbose:
        console.print(f"[dim]{status_msg}[/dim]")

    with console.status(f"[blue]{status_msg}"):
        engine.generate_project(
            template_path=template,
            destination=destination,
            config=config,
            force=force,
            quiet=not verbose,
        )

    console.print(
        Panel.fit(
            f"[green]✅ Project generated![/green]\n"
            f"[bold]Location:[/bold] {destination}\n"
            f"[bold]Template:[/bold] {template}\n"
            f"[bold]Python:[/bold] {config.python_version}\n"
            f"[bold]Security:[/bold] {'Enabled' if enable_security else 'Disabled'}",
            title="🚀 Ready",
            border_style="green",
        )
    )

    if enable_security:
        console.print("\n[bold]Security setup complete:[/bold]")
        if pre_commit:
            console.print("  ✓ Pre-commit hooks configured")
        if security_scan:
            console.print("  ✓ Security scanning tools added")
        if secret_detection:
            console.print("  ✓ Secret detection enabled")
        console.print("\n[dim]Run 'just security/install-hooks' to activate pre-commit[/dim]")


# Template management commands
template_app = typer.Typer(name="template", help="Manage remote templates")
app.add_typer(template_app)


@template_app.command("add")
# @handle_errors
def add_template(
    name: str = typer.Argument(..., help="Template name"),
    url: str = typer.Argument(..., help="Git URL"),
    ref: Optional[str] = typer.Option(None, "--ref", help="Git branch/tag"),
    description: str = typer.Option("", "--description", help="Template description"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing template"),
) -> None:
    """Add a remote template."""
    registry = TemplateRegistry.load()

    try:
        registry.add_template(name, url, ref, description, force)
        console.print(f"[green]✅ Template '{name}' added successfully[/green]")
    except ConfigurationError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@template_app.command("remove")
# @handle_errors
def remove_template(name: str = typer.Argument(..., help="Template name")) -> None:
    """Remove a remote template."""
    registry = TemplateRegistry.load()

    try:
        registry.remove_template(name)
        console.print(f"[green]✅ Template '{name}' removed[/green]")
    except ConfigurationError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@template_app.command("list")
# @handle_errors
def list_remote_templates() -> None:
    """List all registered remote templates."""
    registry = TemplateRegistry.load()

    if registry.templates:
        console.print(registry.list_templates())
    else:
        console.print("[yellow]No remote templates registered[/yellow]")
        console.print("[dim]Add templates with: devman template add NAME URL[/dim]")


@template_app.command("update")
# @handle_errors
def update_template(
    name: Optional[str] = typer.Argument(None, help="Template name (all if not specified)"),
) -> None:
    """Update cached templates."""
    registry = TemplateRegistry.load()

    if name:
        try:
            registry.update_template(name)
            console.print(f"[green]✅ Template '{name}' updated[/green]")
        except ConfigurationError as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)
    else:
        updated = registry.update_all_templates()
        if updated:
            console.print(f"[green]✅ Updated {len(updated)} templates: {', '.join(updated)}[/green]")
        else:
            console.print("[yellow]No templates to update[/yellow]")


# Security commands
security_app = typer.Typer(name="security", help="Security scanning and analysis")
app.add_typer(security_app)


@security_app.command("scan")
# @handle_errors
def security_scan(
    path: Path = typer.Option(Path.cwd(), help="Project path to scan"),
    output: Optional[Path] = typer.Option(None, "--output", help="Output report file"),
) -> None:
    """Run comprehensive security scan on project."""
    security_config = SecurityConfig()
    security_manager = SecurityManager(security_config)

    console.print(f"[blue]Running security scan on {path}...[/blue]")

    results = security_manager.run_security_scan(path)

    # Display results
    table = Table(title="Security Scan Results")
    table.add_column("Check", style="bold")
    table.add_column("Status")

    for check, passed in results.items():
        status = "[green]✓ Passed[/green]" if passed else "[red]✗ Failed[/red]"
        table.add_row(check.replace("_", " ").title(), status)

    console.print(table)

    # Save report if requested
    if output:
        report = {
            "project_path": str(path),
            "results": results,
            "summary": {
                "total_checks": len(results),
                "passed": sum(results.values()),
                "failed": len(results) - sum(results.values()),
            },
        }
        output.write_text(json.dumps(report, indent=2))
        console.print(f"[green]Report saved to {output}[/green]")


@app.command()
# @handle_errors
def config(
    show: bool = typer.Option(False, "--show", help="Show current config"),
    init: bool = typer.Option(False, "--init", help="Initialize config file"),
    set_key: Optional[str] = typer.Option(None, "--set", help="Set config key=value"),
    path: Optional[Path] = typer.Option(None, "--path", help="Config file path"),
) -> None:
    """Manage devman configuration."""

    if init:
        try:
            config_path = ConfigManager.initialize_config(path, overwrite=False)
            console.print(f"[green]✅ Config initialized at {config_path}[/green]")
            console.print("[dim]Edit the file to customize your defaults[/dim]")
        except ConfigurationError as e:
            if "already exists" in str(e):
                console.print(f"[yellow]Config file already exists: {e}[/yellow]")
                console.print("[dim]Use --force to overwrite[/dim]")
            else:
                raise
        return

    if show:
        info = ConfigManager.show_config_info()

        console.print(
            Panel(
                f"[bold]Config file:[/bold] {info['config_file']}\n\n" + json.dumps(info["config"], indent=2),
                title="Current Configuration",
                border_style="blue",
            )
        )

        console.print("\n[dim]Search paths:[/dim]")
        for i, search_path in enumerate(info["search_paths"], 1):
            console.print(f"  {i}. {search_path}")

        return

    if set_key:
        if "=" not in set_key:
            console.print("[red]Error: Format should be --set key=value[/red]")
            sys.exit(1)

        key, value = set_key.split("=", 1)

        try:
            user_config = UserConfig.load()
            user_config.update_setting(key, value)
            config_path = user_config.save(path)
            console.print(f"[green]✅ Set {key} = {value}[/green]")
            console.print(f"[dim]Saved to {config_path}[/dim]")
        except ConfigurationError as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)
        return

    # Default: show help
    console.print("Use --show to view config, --init to create, or --set key=value to modify")


if __name__ == "__main__":
    app()
