from __future__ import annotations

import logging
from pathlib import Path

import typer
from pydantic import ValidationError
from rich.console import Console

from devman.constants import WATCH_CONFIG_NAME

app = typer.Typer(
    name="devman",
    help=(
        "Self-bootstrapping file-oriented learning system "
        "(includes init/bootstrap/project/update/watch workflows)"
    ),
    add_completion=False,
)
console = Console()


def _configure_watch_logging(level_name: str) -> None:
    """Configure watcher logging level and stream handler exactly once."""
    logger = logging.getLogger("devman.watcher")
    logger.setLevel(level_name.upper())

    readable_formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    stream_handlers = [
        handler
        for handler in logger.handlers
        if isinstance(handler, logging.StreamHandler)
    ]

    if not stream_handlers:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(readable_formatter)
        logger.addHandler(stream_handler)
        return

    for handler in stream_handlers:
        if handler.formatter is None:
            handler.setFormatter(readable_formatter)


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


@app.command()
def watch(
    config: Path = typer.Option(
        Path(WATCH_CONFIG_NAME),
        "--config",
        "-c",
        help="Path to watch TOML config file",
    ),
):
    """Run devman watcher loop using TOML configuration."""
    from devman.watcher.config import DevmanWatchConfig
    from devman.watcher.engine import DevmanWatcher

    config_path = config.resolve()

    try:
        watcher_config = DevmanWatchConfig.from_toml_file(config_path)
        _configure_watch_logging(watcher_config.settings.log_level)
        watcher = DevmanWatcher(config=watcher_config, repo_root=Path.cwd())

        console.print(f"Starting watcher with config: [cyan]{config_path}[/cyan]")
        watcher.run()
    except KeyboardInterrupt:
        console.print("[yellow]Info[/yellow] Watcher stopped by user")
    except FileNotFoundError:
        console.print(f"[red]Error[/red] Watch config not found: {config_path}")
        raise typer.Exit(1)
    except ValidationError as e:
        console.print(f"[red]Error[/red] Invalid watch config: {config_path}")
        for error in e.errors():
            location = ".".join(str(part) for part in error["loc"])
            console.print(f"  - {location}: {error['msg']}")
        raise typer.Exit(1)
    except RuntimeError as e:
        console.print(f"[red]Error[/red] {e}")
        raise typer.Exit(1)


@app.command("watch-init")
def watch_init(
    output: Path = typer.Option(
        Path(WATCH_CONFIG_NAME),
        "--output",
        "-o",
        help="Path where starter watch config will be created",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite the output file if it already exists",
    ),
):
    """Generate a starter devman-watch.toml configuration."""
    from devman.watcher.toml_gen import generate_starter_config

    output_path = output.resolve()

    try:
        generate_starter_config(output_path, overwrite=force)
        console.print(f"[green]OK[/green] Created starter config: {output_path}")
    except FileExistsError:
        console.print(
            f"[red]Error[/red] Refusing to overwrite existing file: {output_path}"
        )
        raise typer.Exit(1)


@app.command("watch-check")
def watch_check(
    config: Path = typer.Option(
        Path(WATCH_CONFIG_NAME),
        "--config",
        "-c",
        help="Path to watch TOML config file",
    ),
):
    """Validate watch configuration and print diagnostics."""
    from devman.watcher.config import DevmanWatchConfig

    config_path = config.resolve()

    try:
        validated = DevmanWatchConfig.from_toml_file(config_path)
        console.print(f"[green]OK[/green] Watch config is valid: {config_path}")
        console.print(
            f"  Patterns: {len(validated.patterns)} | "
            f"Debounce: {validated.settings.debounce_ms}ms | "
            f"Log level: {validated.settings.log_level}"
        )
    except FileNotFoundError:
        console.print(f"[red]Error[/red] Watch config not found: {config_path}")
        raise typer.Exit(1)
    except ValidationError as e:
        console.print(f"[red]Error[/red] Invalid watch config: {config_path}")
        for error in e.errors():
            location = ".".join(str(part) for part in error["loc"])
            console.print(f"  - {location}: {error['msg']}")
        raise typer.Exit(1)


@app.command("instantiate")
def instantiate(
    template: str = typer.Argument(..., help="Template name under template_store"),
    target: Path = typer.Argument(..., help="Directory where template should be generated"),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing target"),
    config: Path = typer.Option(
        Path(WATCH_CONFIG_NAME),
        "--config",
        "-c",
        help="Path to watch TOML config file",
    ),
):
    """Generate files/folders from a template without running the watch loop."""
    from devman.watcher.config import DevmanWatchConfig
    from devman.domain.errors import WatchError
    from devman.watcher.handlers import resolve_template_path, run_copier_instantiation

    config_path = config.resolve()
    target_path = target.resolve()

    try:
        watcher_config = DevmanWatchConfig.from_toml_file(config_path)
        template_path = resolve_template_path(template, watcher_config)
        run_copier_instantiation(template_path, target_path, force=force)
        console.print(
            f"[green]OK[/green] Generated template [cyan]{template}[/cyan] at {target_path}"
        )
    except FileNotFoundError:
        console.print(f"[red]Error[/red] Watch config not found: {config_path}")
        raise typer.Exit(1)
    except ValidationError as e:
        console.print(f"[red]Error[/red] Invalid watch config: {config_path}")
        for error in e.errors():
            location = ".".join(str(part) for part in error["loc"])
            console.print(f"  - {location}: {error['msg']}")
        raise typer.Exit(1)
    except WatchError as e:
        console.print(f"[red]Error[/red] {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
