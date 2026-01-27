# src/devman/cli.py
"""DevMan CLI for managing local development environments."""

from __future__ import annotations

import typer

from devman.commands import clean, init, test, validate

app = typer.Typer(
    name="devman",
    help="DevMan CLI for managing local development environments.",
    no_args_is_help=True,
)

# Register commands
app.command(name="init")(init.init_command)
app.command(name="validate")(validate.validate_command)
app.command(name="test")(test.test_command)
app.command(name="clean")(clean.clean_command)


def main() -> None:
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
