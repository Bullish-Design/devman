"""The devman command line. One typed function per command (Typer)."""

from __future__ import annotations

from typing import Annotated

import typer

from devman import __version__
from devman.paths import Paths

app = typer.Typer(
    name="devman",
    help="Compile, route and show Dagu workflows across repositories.",
    add_completion=False,
    no_args_is_help=True,
)


def _show_version(value: bool) -> None:
    if value:
        typer.echo(f"devman {__version__}")
        raise typer.Exit(0)


@app.callback()
def root(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_show_version,
            is_eager=True,
            help="Print the version and exit.",
        ),
    ] = False,
) -> None:
    """Compile, route and show Dagu workflows across repositories."""


@app.command("compile")
def compile_cmd(
    projects: Annotated[
        list[str] | None,
        typer.Argument(help="Projects to compile. Default: all of them."),
    ] = None,
    validate_all: Annotated[
        bool,
        typer.Option("--all", help="Validate every file, changed or not."),
    ] = False,
) -> None:
    """Resolve, render, validate and publish each project's workflows."""
    from devman.compile import compile as run_compile

    raise typer.Exit(run_compile(Paths.from_env(), projects or None, validate_all))


def main() -> None:
    """Console entry point. Typer exits with the command's exit code."""
    app(prog_name="devman")
