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


@app.command("emit")
def emit_cmd(
    event: Annotated[str, typer.Argument(help="Event name, such as save or land.")],
    fields: Annotated[
        list[str] | None,
        typer.Argument(help="Extra KEY=VALUE fields passed to the run."),
    ] = None,
    project: Annotated[
        str | None, typer.Option("--project", help="Default: from the directory.")
    ] = None,
    subject: Annotated[
        list[str] | None,
        typer.Option("--subject", help="A path or ref name. Repeat for many."),
    ] = None,
    source: Annotated[
        str, typer.Option("--source", help="Who sent the event.")
    ] = "cli",
) -> None:
    """Route one event to the workflows that match it."""
    from devman import router

    parsed, error = router.parse_fields(fields or [])
    error = router.check_event(event) or error
    if error:
        typer.echo(f"devman: {error}", err=True)
        raise typer.Exit(2)
    outcome = router.emit(
        Paths.from_env(),
        router.Event(event, project, tuple(subject or ()), source, parsed),
    )
    for line in outcome.lines:
        typer.echo(line, err=outcome.code == 2)
    raise typer.Exit(outcome.code)


@app.command("watch")
def watch_cmd(
    debounce: Annotated[
        str, typer.Option("--debounce", help="Quiet time, such as 300ms or 2s.")
    ] = "300ms",
) -> None:
    """Watch saves and overlay changes. The user service runs this."""
    from devman import watch

    try:
        watch.seconds(debounce)
    except ValueError as exc:
        typer.echo(f"devman: {exc}", err=True)
        raise typer.Exit(2) from exc
    raise typer.Exit(watch.watch(Paths.from_env(), debounce))


def main() -> None:
    """Console entry point. Typer exits with the command's exit code."""
    app(prog_name="devman")
