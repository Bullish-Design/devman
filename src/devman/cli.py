"""Command-line interface for devman."""

import typer

app = typer.Typer()


@app.command()
def hello(name: str = typer.Argument("world")) -> None:
    """Say hello."""
    typer.echo(f"Hello, {name}!")


@app.command()
def version() -> None:
    """Show the devman version."""
    typer.echo("devman 0.1.0")
