"""The devman command line. One typed function per command (Typer)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated, NoReturn

import typer

from devman import __version__
from devman.paths import Paths

if TYPE_CHECKING:
    from devman.router import Outcome

ProjectOption = Annotated[
    str | None, typer.Option("--project", help="Default: from the directory.")
]
Fields = Annotated[
    list[str] | None, typer.Argument(help="Extra KEY=VALUE fields passed to the run.")
]

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


def _finish(outcome: Outcome) -> NoReturn:
    for line in outcome.lines:
        typer.echo(line, err=outcome.code == 2)
    raise typer.Exit(outcome.code)


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
    fields: Fields = None,
    project: ProjectOption = None,
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
    _finish(outcome)


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


@app.command("run")
def run_cmd(
    workflow: Annotated[str, typer.Argument(help="Workflow name, such as check.")],
    fields: Fields = None,
    project: ProjectOption = None,
) -> None:
    """Run one workflow now. This is a manual event with an implicit match."""
    from devman import router

    parsed, error = router.parse_fields(fields or [])
    if error:
        typer.echo(f"devman: {error}", err=True)
        raise typer.Exit(2)
    outcome = router.emit(
        Paths.from_env(),
        router.Event("manual", project, (workflow,), "manual", parsed, implicit=True),
    )
    if outcome.record["stale"]:
        typer.echo("devman: warning: the project is stale; the old file runs", err=True)
    _finish(outcome)


@app.command("status")
def status_cmd(
    project: Annotated[
        str | None, typer.Argument(help="Default: the project of this directory.")
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Print JSON.")] = False,
) -> None:
    """Show what runs in a project, and the last result of each workflow."""
    from devman import status

    code, text = status.status(Paths.from_env(), project, as_json, Path.cwd())
    typer.echo(text, err=code == 2)
    raise typer.Exit(code)


@app.command("show")
def show_cmd(
    workflow: Annotated[str, typer.Argument(help="Workflow name.")],
    project: ProjectOption = None,
) -> None:
    """Print the compiled file of a workflow, with its source path."""
    from devman import status

    code, text = status.show(Paths.from_env(), workflow, project, Path.cwd())
    typer.echo(text, err=code != 0)
    raise typer.Exit(code)


@app.command("doctor")
def doctor_cmd() -> None:
    """Check the services, the Dagu version, `dags/` and the library."""
    from devman import doctor

    code, lines = doctor.doctor(Paths.from_env())
    typer.echo("\n".join(lines))
    raise typer.Exit(code)


def main() -> None:
    """Console entry point. Typer exits with the command's exit code."""
    app(prog_name="devman")
