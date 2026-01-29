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


@app.command()
def hello(name: str = typer.Argument("world")) -> None:
    """Say hello."""
    typer.echo(f"Hello, {name}!")


@app.command()
def version() -> None:
    """Show the devman version."""
    typer.echo("devman 0.1.0")
