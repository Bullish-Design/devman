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

    def test_init_command_basic(self) -> None:
        """Test basic init command."""
        with TemporaryDirectory() as temp_dir:
            with patch("pathlib.Path.cwd", return_value=Path(temp_dir)):
                result = self.runner.invoke(app, ["init", "test-project"])

                assert result.exit_code == 0
                assert "Configuration created" in result.stdout

                config_path = Path(temp_dir) / ".devman" / "devman.toml"
                assert config_path.exists()

    def test_init_command_with_options(self) -> None:
        """Test init command with various options."""
        with TemporaryDirectory() as temp_dir:
            with patch("pathlib.Path.cwd", return_value=Path(temp_dir)):
                result = self.runner.invoke(
                    app,
                    [
                        "init",
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
                    ],
                )

                assert result.exit_code == 0

                config_path = Path(temp_dir) / ".devman" / "devman.toml"
                config_content = config_path.read_text()

                assert "api-project" in config_content
                assert "3.12" in config_content
                assert "docker" in config_content
                assert "requests" in config_content

    def test_init_command_invalid_project_type(self) -> None:
        """Test init command with invalid project type."""
        with TemporaryDirectory() as temp_dir:
            with patch("pathlib.Path.cwd", return_value=Path(temp_dir)):
                result = self.runner.invoke(
                    app, ["init", "test-project", "--type", "invalid"]
                )

                assert result.exit_code == 1
                assert "Invalid project type" in result.stdout

    def test_init_command_existing_config(self) -> None:
        """Test init command with existing config file."""
        with TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / ".devman" / "devman.toml"
            config_path.parent.mkdir()
            config_path.write_text("existing config")

            with patch("pathlib.Path.cwd", return_value=Path(temp_dir)):
                result = self.runner.invoke(app, ["init", "test-project"])

                assert result.exit_code == 1
                assert "already exists" in result.stdout

    def test_init_command_force_overwrite(self) -> None:
        """Test init command with force overwrite."""
        with TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / ".devman" / "devman.toml"
            config_path.parent.mkdir()
            config_path.write_text("existing config")

            with patch("pathlib.Path.cwd", return_value=Path(temp_dir)):
                result = self.runner.invoke(app, ["init", "test-project", "--force"])

                assert result.exit_code == 0
                assert "Configuration created" in result.stdout

    def test_generate_command_no_config(self) -> None:
        """Test generate command without config file."""
        with TemporaryDirectory() as temp_dir:
            with patch("pathlib.Path.cwd", return_value=Path(temp_dir)):
                result = self.runner.invoke(app, ["generate"])

                assert result.exit_code == 1
                assert "No devman.toml found" in result.stdout

    def test_generate_command_success(self) -> None:
        """Test successful generate command."""
        with TemporaryDirectory() as temp_dir:
            # Create config file first
            config_path = Path(temp_dir) / ".devman" / "devman.toml"
            config_path.parent.mkdir()
            config_content = """[devman]
version = "0.2.0"
created_at = "2025-01-15T10:30:00"
updated_at = "2025-01-15T10:30:00"

[project]
name = "test-project"
python_version = "3.11"
project_type = "api"
container_type = "devenv"
dependencies = []
dev_dependencies = []
local_dependencies = []
use_database = false
database_type = "postgresql"
use_redis = false
use_celery = false

[templates]
files = ["devenv.nix.j2", "justfile.j2"]

[generation]
generated_files = []
"""
            config_path.write_text(config_content)

            with patch("pathlib.Path.cwd", return_value=Path(temp_dir)):
                with patch("devman.cli.DevEnvTemplater") as mock_templater:
                    mock_instance = Mock()
                    mock_instance.generate_from_config.return_value = [
                        "devenv.nix",
                        "justfile",
                    ]
                    mock_templater.return_value = mock_instance

                    result = self.runner.invoke(app, ["generate"])

                    assert result.exit_code == 0
                    assert "Project generated successfully" in result.stdout
                    mock_instance.generate_from_config.assert_called_once()

    def test_generate_command_existing_files(self) -> None:
        """Test generate command with existing files."""
        with TemporaryDirectory() as temp_dir:
            # Create config and existing file
            config_path = Path(temp_dir) / ".devman" / "devman.toml"
            config_path.parent.mkdir()
            config_content = """[devman]
version = "0.2.0"
created_at = "2025-01-15T10:30:00"
updated_at = "2025-01-15T10:30:00"

[project]
name = "test-project"
python_version = "3.11"
project_type = "api"
container_type = "devenv"
dependencies = []
dev_dependencies = []
local_dependencies = []
use_database = false
database_type = "postgresql"
use_redis = false
use_celery = false

[templates]
files = ["devenv.nix.j2"]

[generation]
generated_files = []
"""
            config_path.write_text(config_content)

            # Create existing file
            (Path(temp_dir) / "devenv.nix").write_text("existing")

            with patch("pathlib.Path.cwd", return_value=Path(temp_dir)):
                with patch("devman.cli.DevEnvTemplater") as mock_templater:
                    mock_instance = Mock()
                    mock_instance.generate_from_config.return_value = [
                        "devenv.nix",
                        "justfile",
                    ]
                    mock_templater.return_value = mock_instance

                    result = self.runner.invoke(app, ["generate", "--no-format"])
                    print(f"Result output: {result.stdout}")

                    assert result.exit_code == 0
                    assert "Project generated successfully" in result.stdout
                    mock_instance.generate_from_config.assert_called_once()

    def test_update_command_no_config(self) -> None:
        """Test update command without config file."""
        with TemporaryDirectory() as temp_dir:
            with patch("pathlib.Path.cwd", return_value=Path(temp_dir)):
                result = self.runner.invoke(app, ["update", "--type", "cli"])

                assert result.exit_code == 1
                assert "No devman.toml found" in result.stdout

    def test_update_command_success(self) -> None:
        """Test successful update command."""
        with TemporaryDirectory() as temp_dir:
            # Create initial config
            config_path = Path(temp_dir) / ".devman" / "devman.toml"
            config_path.parent.mkdir()
            config_content = """[devman]
version = "0.2.0"
created_at = "2025-01-15T10:30:00"
updated_at = "2025-01-15T10:30:00"

[project]
name = "test-project"
python_version = "3.11"
project_type = "api"
container_type = "devenv"
dependencies = []
dev_dependencies = []
local_dependencies = []
use_database = false
database_type = "postgresql"
use_redis = false
use_celery = false

[templates]
files = []

[generation]
generated_files = []
"""
            config_path.write_text(config_content)

            with patch("pathlib.Path.cwd", return_value=Path(temp_dir)):
                with patch("typer.confirm", return_value=True):
                    result = self.runner.invoke(
                        app, ["update", "--type", "cli", "--force"]
                    )

                    assert result.exit_code == 0
                    assert "Configuration updated" in result.stdout

    def test_status_command(self) -> None:
        """Test status command."""
        with TemporaryDirectory() as temp_dir:
            # Create config file
            config_path = Path(temp_dir) / ".devman" / "devman.toml"
            config_path.parent.mkdir()
            config_content = """[devman]
version = "0.2.0"
created_at = "2025-01-15T10:30:00"
updated_at = "2025-01-15T10:30:00"

[project]
name = "status-test"
python_version = "3.11"
project_type = "api"
container_type = "devenv"
dependencies = []
dev_dependencies = []
local_dependencies = []
use_database = false
database_type = "postgresql"
use_redis = false
use_celery = false

[templates]
files = []

[generation]
generated_files = []
"""
            config_path.write_text(config_content)

            with patch("pathlib.Path.cwd", return_value=Path(temp_dir)):
                result = self.runner.invoke(app, ["status"])

                assert result.exit_code == 0
                assert "Project Status" in result.stdout
                assert "status-test" in result.stdout
                assert "0.2.0" in result.stdout

    def test_status_command_no_config(self) -> None:
        """Test status command without config."""
        with TemporaryDirectory() as temp_dir:
            with patch("pathlib.Path.cwd", return_value=Path(temp_dir)):
                result = self.runner.invoke(app, ["status"])

                assert result.exit_code == 1
                assert "No devman.toml found" in result.stdout

    def test_list_templates_command(self) -> None:
        """Test list templates command."""
        result = self.runner.invoke(app, ["list-templates"])

        assert result.exit_code == 0
        assert "Available Templates" in result.stdout
        assert "api" in result.stdout
        assert "web" in result.stdout
        assert "cli" in result.stdout
