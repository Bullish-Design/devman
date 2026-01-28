from typer.testing import CliRunner

from devman.cli import app


def test_hello_command() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["hello", "dev"])
    assert result.exit_code == 0
    assert "Hello, dev!" in result.stdout
