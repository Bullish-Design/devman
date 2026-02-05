from __future__ import annotations

import typer
from pathlib import Path
from rich.console import Console

app = typer.Typer(
    name="devman",
    help="Self-bootstrapping file-oriented learning system",
    add_completion=False,
)
console = Console()


@app.command()
def init():
    """Initialize devman store with git-backed templates."""
    from devman.bootstrap import init_devman_store

    try:
        store_path = init_devman_store()
        console.print(f"[green]OK[/green] Devman store initialized: {store_path}")
        console.print("  Git repository created with tag v0.1.0")
    except ValueError as e:
        console.print(f"[red]Error[/red] {e}")
        raise typer.Exit(1)


@app.command()
def bootstrap(
    file_type: str = typer.Argument(..., help="File type name (e.g., pyproject.toml)"),
    answers: Path = typer.Option(None, "--answers", "-a", help="Copier answers file"),
    version: str = typer.Option(None, "--version", "-v", help="Pin to specific version"),
):
    """Bootstrap a new file type configuration."""
    from devman.bootstrap import bootstrap_file_type, get_current_devman_version

    console.print(f"Bootstrapping file type: [cyan]{file_type}[/cyan]")

    try:
        type_path = bootstrap_file_type(
            file_type=file_type,
            answers_file=answers,
            template_version=version,
        )
        console.print(f"[green]OK[/green] File type created: {type_path}")

        ver = version or get_current_devman_version()
        console.print(f"  Template version: {ver}")

    except (ValueError, RuntimeError) as e:
        console.print(f"[red]Error[/red] {e}")
        raise typer.Exit(1)


@app.command()
def project(
    template: str = typer.Argument(..., help="Project template (e.g., pyproj)"),
    target: Path = typer.Argument(..., help="Target directory for project"),
    answers: Path = typer.Option(None, "--answers", "-a", help="Copier answers file"),
    version: str = typer.Option(None, "--version", "-v", help="Pin to specific version"),
):
    """Create a new project from a meta-template."""
    from devman.bootstrap_project import bootstrap_project

    console.print(f"Creating project from template: [cyan]{template}[/cyan]")

    try:
        result = bootstrap_project(
            project_template=template,
            target_dir=target,
            answers_file=answers,
            template_version=version,
        )

        console.print(f"[green]OK[/green] Project created: {result['project_path']}")
        console.print(f"  Template: {result['template']}@{result['version']}")

        if result["file_types"]:
            console.print("\n  File types used:")
            for ft in result["file_types"]:
                console.print(f"    - {ft}")

    except (ValueError, RuntimeError) as e:
        console.print(f"[red]Error[/red] {e}")
        raise typer.Exit(1)


@app.command()
def update(
    target: Path = typer.Argument(..., help="File type or project to update"),
    version: str = typer.Option(None, "--version", "-v", help="Target version"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show changes without applying"),
):
    """Update a file type or project to a new template version."""
    from devman.update import update_file_type, update_project

    target = Path(target).resolve()

    # Determine if it's a project (has .devman-project.toml) or a file type
    if (target / ".devman-project.toml").exists():
        console.print(f"Updating project: [cyan]{target.name}[/cyan]")

        try:
            result = update_project(
                project_path=target,
                target_version=version,
                dry_run=dry_run,
            )

            if result["success"]:
                action = "Would update" if dry_run else "Updated"
                console.print(
                    f"[green]OK[/green] {action}: "
                    f"{result['current_version']} -> {result['target_version']}"
                )

                if result.get("changes"):
                    console.print("\n  Changes:")
                    for change in result["changes"][:10]:
                        console.print(f"    {change}")
                    if len(result["changes"]) > 10:
                        console.print(
                            f"    ... and {len(result['changes']) - 10} more"
                        )
            else:
                console.print(
                    f"[yellow]Info[/yellow] "
                    f"{result.get('message', 'No changes needed')}"
                )

        except (ValueError, RuntimeError) as e:
            console.print(f"[red]Error[/red] {e}")
            raise typer.Exit(1)

    else:
        file_type = target.name
        console.print(f"Updating file type: [cyan]{file_type}[/cyan]")

        try:
            result = update_file_type(
                file_type=file_type,
                target_version=version,
                dry_run=dry_run,
            )

            if result["success"]:
                action = "Would update" if dry_run else "Updated"
                console.print(
                    f"[green]OK[/green] {action}: "
                    f"{result['current_version']} -> {result['target_version']}"
                )

                if result.get("changes"):
                    console.print("\n  Changes:")
                    for change in result["changes"][:10]:
                        console.print(f"    {change}")
                    if len(result["changes"]) > 10:
                        console.print(
                            f"    ... and {len(result['changes']) - 10} more"
                        )
            else:
                console.print(
                    f"[yellow]Info[/yellow] "
                    f"{result.get('message', 'No changes needed')}"
                )

        except (ValueError, RuntimeError) as e:
            console.print(f"[red]Error[/red] {e}")
            raise typer.Exit(1)


if __name__ == "__main__":
    app()
