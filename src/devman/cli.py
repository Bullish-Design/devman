"""Command-line interface for devman."""

import subprocess
from pathlib import Path

import typer

from devman.config import DevmanConfig, load_config


class DevmanFinder:
    """Locate the nearest devman configuration directory."""

    def __init__(self, projects_root: Path | None = None) -> None:
        self.projects_root = projects_root

    @classmethod
    def from_config(cls, config: DevmanConfig | None = None) -> "DevmanFinder":
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
def version() -> None:
    """Show the devman version."""
    typer.echo("devman 0.1.0")
