# tests/test_cli.py
"""Test CLI functionality."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from devman.cli import app


class TestCLI:
    """Test CLI commands."""

    def setup_method(self) -> None:
        """Setup test runner."""
        self.runner = CliRunner()

    def test_new_command_basic(self) -> None:
        """Test basic new project command."""
        with TemporaryDirectory() as temp_dir:
            target_dir = Path(temp_dir) / "test-project"

            with patch("devman.cli.DevEnvTemplater") as mock_templater:
                mock_instance = Mock()
                mock_templater.return_value = mock_instance

                result = self.runner.invoke(
                    app, ["new", "test-project", "--dir", str(target_dir)]
                )

                assert result.exit_code == 0
                assert "created successfully" in result.stdout
                mock_instance.generate_project.assert_called_once()

    def test_new_command_invalid_project_type(self) -> None:
        """Test new command with invalid project type."""
        result = self.runner.invoke(app, ["new", "test-project", "--type", "invalid"])

        assert result.exit_code == 1
        assert "Invalid project type" in result.stdout

    def test_new_command_invalid_container_type(self) -> None:
        """Test new command with invalid container type."""
        result = self.runner.invoke(
            app, ["new", "test-project", "--containers", "invalid"]
        )

        assert result.exit_code == 1
        assert "Invalid container type" in result.stdout

    def test_new_command_existing_directory(self) -> None:
        """Test new command with existing non-empty directory."""
        with TemporaryDirectory() as temp_dir:
            target_dir = Path(temp_dir) / "existing"
            target_dir.mkdir()
            (target_dir / "existing_file.txt").write_text("content")

            result = self.runner.invoke(
                app, ["new", "test-project", "--dir", str(target_dir)]
            )

            assert result.exit_code == 1
            assert "already exists" in result.stdout

    def test_new_command_force_overwrite(self) -> None:
        """Test new command with force overwrite."""
        with TemporaryDirectory() as temp_dir:
            target_dir = Path(temp_dir) / "existing"
            target_dir.mkdir()
            (target_dir / "existing_file.txt").write_text("content")

            with patch("devman.cli.DevEnvTemplater") as mock_templater:
                mock_instance = Mock()
                mock_templater.return_value = mock_instance

                result = self.runner.invoke(
                    app, ["new", "test-project", "--dir", str(target_dir), "--force"]
                )

                assert result.exit_code == 0
                mock_instance.generate_project.assert_called_once()

    def test_new_command_with_options(self) -> None:
        """Test new command with various options."""
        with TemporaryDirectory() as temp_dir:
            target_dir = Path(temp_dir) / "api-project"

            with patch("devman.cli.DevEnvTemplater") as mock_templater:
                mock_instance = Mock()
                mock_templater.return_value = mock_instance

                result = self.runner.invoke(
                    app,
                    [
                        "new",
                        "api-project",
                        "--type",
                        "api",
                        "--python",
                        "3.12",
                        "--containers",
                        "docker",
                        "--database",
                        "postgresql",
                        "--deps",
                        "requests",
                        "--dev-deps",
                        "black",
                        "--local-deps",
                        "my-lib",
                        "--dir",
                        str(target_dir),
                    ],
                )

                assert result.exit_code == 0

                # Check config was passed correctly
                call_args = mock_instance.generate_project.call_args
                config = call_args[0][0]

                assert config.name == "api-project"
                assert config.project_type == "api"
                assert config.python_version == "3.12"
                assert config.container_type == "docker"
                assert config.use_database is True
                assert config.database_type == "postgresql"
                assert "requests" in config.dependencies
                assert "black" in config.dev_dependencies
                assert "my-lib" in config.local_dependencies

    def test_update_command_no_pyproject(self) -> None:
        """Test update command when not in project directory."""
        with TemporaryDirectory() as temp_dir:
            with patch("pathlib.Path.cwd", return_value=Path(temp_dir)):
                result = self.runner.invoke(
                    app, ["update", "test-project", "--no-format"]
                )
                assert result.exit_code == 1
                assert "No pyproject.toml found" in result.stdout

    def test_update_command_success(self) -> None:
        """Test successful update command."""
        with TemporaryDirectory() as temp_dir:
            # Create pyproject.toml
            pyproject_path = Path(temp_dir) / "pyproject.toml"
            pyproject_path.write_text("[project]\nname = 'test'\n")

            with patch("pathlib.Path.cwd", return_value=Path(temp_dir)):
                with patch("devman.cli.DevEnvTemplater") as mock_templater:
                    mock_instance = Mock()
                    mock_templater.return_value = mock_instance

                    # Mock confirmation
                    with patch("typer.confirm", return_value=True):
                        result = self.runner.invoke(app, ["update", "test-project"])

                    assert result.exit_code == 0
                    assert "updated" in result.stdout
                    mock_instance.generate_project.assert_called_once()

    def test_list_templates_command(self) -> None:
        """Test list templates command."""
        result = self.runner.invoke(app, ["list-templates"])

        assert result.exit_code == 0
        assert "Available Templates" in result.stdout
        assert "api" in result.stdout
        assert "web" in result.stdout
        assert "cli" in result.stdout

    def test_config_command(self) -> None:
        """Test config command."""
        with patch("devman.cli.DevEnvTemplater") as mock_templater:
            mock_instance = Mock()
            mock_instance.templates_dir = Path("/test/templates")
            mock_instance.registry = Mock()
            mock_instance.registry.templates = {"test.j2": "content"}
            mock_templater.return_value = mock_instance

            result = self.runner.invoke(app, ["config"])

            assert result.exit_code == 0
            assert "Configuration" in result.stdout
            assert "/test/templates" in result.stdout

    def test_init_templates_command(self) -> None:
        """Test init templates command."""
        with patch("devman.cli.DevEnvTemplater") as mock_templater:
            mock_instance = Mock()
            mock_instance.templates_dir = Path("/test/templates")
            mock_templater.return_value = mock_instance

            result = self.runner.invoke(app, ["init-templates", "--force"])

            assert result.exit_code == 0
            assert "initialized" in result.stdout
            mock_instance.ensure_templates_exist.assert_called_once()

    def test_init_templates_confirm_overwrite(self) -> None:
        """Test init templates with confirmation."""
        with patch("devman.cli.DevEnvTemplater") as mock_templater:
            mock_instance = Mock()
            mock_instance.templates_dir.exists.return_value = True
            mock_templater.return_value = mock_instance

            # Test declining confirmation
            with patch("typer.confirm", return_value=False):
                result = self.runner.invoke(app, ["init-templates"])

                assert result.exit_code == 0
                mock_instance.ensure_templates_exist.assert_not_called()

