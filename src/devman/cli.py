"""The devman command line. One typed function per command (Typer)."""

from __future__ import annotations

from typing import Annotated

import typer

from devman import __version__

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


def main() -> None:
    """Console entry point. Typer exits with the command's exit code."""
    app(prog_name="devman")
