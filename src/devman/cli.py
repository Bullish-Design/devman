# src/devman/cli.py
"""Command line interface for devman."""

from __future__ import annotations

import typer

from devman.commands import doctor, down, init, index, switch, up

app = typer.Typer(
    name="devman",
    help="🧰 Manage devman workspaces",
    rich_markup_mode="rich",
)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Run devman commands."""
    if ctx.invoked_subcommand is None:
        up.run()


app.command(name="up")(up.run)
app.command(name="down")(down.run)
app.command(name="switch")(switch.run)
app.command(name="doctor")(doctor.run)
app.command(name="init")(init.run)

app.add_typer(index.app, name="index")

if __name__ == "__main__":
    app()
