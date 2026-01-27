# tests/test_cli.py
"""Test CLI entry points and command structure."""

from __future__ import annotations

from typer.testing import CliRunner

from devman.cli import app

runner = CliRunner()


def test_cli_help():
    """Test that CLI shows help message."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "DevMan CLI" in result.output
    assert "init" in result.output
    assert "validate" in result.output
    assert "test" in result.output
    assert "clean" in result.output


def test_cli_version():
    """Test version display."""
    from devman import __version__

    assert __version__ == "0.1.0"


def test_init_help():
    """Test init command help."""
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0
    assert "--devman-dir" in result.output
    assert "--template" in result.output
    assert "--python-version" in result.output


def test_validate_help():
    """Test validate command help."""
    result = runner.invoke(app, ["validate", "--help"])
    assert result.exit_code == 0
    assert "--devman-dir" in result.output


def test_test_help():
    """Test test command help."""
    result = runner.invoke(app, ["test", "--help"])
    assert result.exit_code == 0
    assert "--devman-dir" in result.output
    assert "--keep-container" in result.output


def test_clean_help():
    """Test clean command help."""
    result = runner.invoke(app, ["clean", "--help"])
    assert result.exit_code == 0
    assert "--devman-dir" in result.output
    assert "--all" in result.output
