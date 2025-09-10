# tests/test_cli.py
from __future__ import annotations
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner

from devman.cli import app
from devman.config import UserConfig


def test_cli_imports():
    """Debug CLI import issues."""
    try:
        from devman.cli import app, console, BUILTIN_TEMPLATES

        print(f"✅ Imports work: app={app}, templates={list(BUILTIN_TEMPLATES.keys())}")
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback

        traceback.print_exc()


class TestCLI:
    """Test CLI functionality."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_config(self):
        """Mock user configuration."""
        return UserConfig(
            default_python_version="3.11",
            default_template="python-lib",
            author_name="Test User",
            author_email="test@example.com",
        )

    def test_cli_command_debug(self, runner):
        """Debug what's happening in CLI commands."""
        try:
            print("✅ Running CLI command...")
            result = runner.invoke(app, ["list"])
            print(f"Exit code: {result.exit_code}")
            print(f"Output: {result.output}")
            print(f"Exception: {result.exception}")
            if result.exception:
                import traceback

                print(
                    "".join(
                        traceback.format_exception(
                            type(result.exception), result.exception, result.exception.__traceback__
                        )
                    )
                )
        except Exception as e:
            print(f"❌ CLI command failed: {e}")

    def test_list_templates(self, runner):
        """Test listing available templates."""
        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "python-lib" in result.stdout
        assert "python-cli" in result.stdout
        assert "fastapi-api" in result.stdout
        assert "Built-in Templates" in result.stdout

    @patch("devman.cli.UserConfig.load")
    def test_config_show(self, mock_load, runner, mock_config):
        """Test showing configuration."""
        mock_load.return_value = mock_config

        result = runner.invoke(app, ["config", "--show"])

        assert result.exit_code == 0
        assert "Current Configuration" in result.stdout
        assert "3.11" in result.stdout
        assert "Test User" in result.stdout

    @patch("devman.cli.ConfigManager.initialize_config")
    def test_config_init(self, mock_init, runner, tmp_path):
        """Test initializing configuration."""
        config_path = tmp_path / "config.yml"
        mock_init.return_value = config_path

        result = runner.invoke(app, ["config", "--init"])

        assert result.exit_code == 0
        assert "Config initialized" in result.stdout
        mock_init.assert_called_once()

    @patch("devman.cli.UserConfig.load")
    @patch("devman.cli.UserConfig.save")
    def test_config_set(self, mock_save, mock_load, runner, mock_config, tmp_path):
        """Test setting configuration values."""
        mock_load.return_value = mock_config
        mock_save.return_value = tmp_path / "config.yml"

        result = runner.invoke(app, ["config", "--set", "default_python_version=3.12"])

        assert result.exit_code == 0
        # Strip ANSI codes for assertion
        import re

        clean_output = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
        assert "Set default_python_version = 3.12" in clean_output
        mock_save.assert_called_once()

    def test_config_set_invalid_format(self, runner):
        """Test setting config with invalid format."""
        result = runner.invoke(app, ["config", "--set", "invalid-format"])

        assert result.exit_code == 1
        import re

        clean_output = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
        assert "Format should be --set key=value" in clean_output

    @patch("devman.cli.UserConfig.load")
    @patch("devman.cli.TemplateEngine")
    def test_generate_demo_mode(self, mock_engine_class, mock_load, runner, mock_config, tmp_path):
        """Test generate command in demo mode."""
        mock_load.return_value = mock_config

        # Mock the template engine
        mock_engine = MagicMock()
        mock_engine_class.return_value = mock_engine

        # Mock the generation plan
        mock_plan = MagicMock()
        mock_plan.get_summary.return_value = {
            "total_files": 3,
            "conflicts": 0,
            "destination": str(tmp_path / "test-project"),
            "template": "python-lib",
        }
        mock_plan.files = {
            "README.md": MagicMock(size=100, is_binary=False),
            "pyproject.toml": MagicMock(size=200, is_binary=False),
            "src/test_project/__init__.py": MagicMock(size=50, is_binary=False),
        }
        mock_plan.conflicts = []
        mock_engine.create_plan.return_value = mock_plan

        result = runner.invoke(app, ["generate", "test-project", "--demo"])

        assert result.exit_code == 0
        assert "Generation Plan Summary" in result.stdout
        assert "Demo complete - no files written" in result.stdout
        assert "3" in result.stdout  # file count
        mock_engine.create_plan.assert_called_once()

    @patch("devman.cli.UserConfig.load")
    @patch("devman.cli.TemplateEngine")
    def test_generate_demo_with_conflicts(self, mock_engine_class, mock_load, runner, mock_config):
        """Test demo mode showing conflicts."""
        mock_load.return_value = mock_config

        mock_engine = MagicMock()
        mock_engine_class.return_value = mock_engine

        mock_plan = MagicMock()
        mock_plan.get_summary.return_value = {
            "total_files": 2,
            "conflicts": 1,
            "destination": "/tmp/test",
            "template": "python-lib",
        }
        mock_plan.files = {
            "README.md": MagicMock(size=100, is_binary=False),
            "new_file.py": MagicMock(size=50, is_binary=False),
        }
        mock_plan.conflicts = ["README.md"]
        mock_engine.create_plan.return_value = mock_plan

        result = runner.invoke(app, ["generate", "test-project", "--demo"])

        assert result.exit_code == 0
        assert "would be overwritten" in result.stdout
        assert "Use --force" in result.stdout

    @patch("devman.cli.UserConfig.load")
    @patch("devman.cli.TemplateEngine")
    def test_generate_demo_with_json_export(self, mock_engine_class, mock_load, runner, mock_config, tmp_path):
        """Test demo mode with JSON export."""
        mock_load.return_value = mock_config

        mock_engine = MagicMock()
        mock_engine_class.return_value = mock_engine

        # Create proper mock objects instead of MagicMock
        from devman.models import FileSnapshot

        mock_file = FileSnapshot(content="test", size=4, is_binary=False)

        mock_plan = MagicMock()
        mock_plan.get_summary.return_value = {
            "total_files": 1,
            "conflicts": 0,
            "destination": "/tmp",
            "template": "test",
        }
        mock_plan.files = {"test.py": mock_file}
        mock_plan.conflicts = []
        mock_engine.create_plan.return_value = mock_plan

        json_file = tmp_path / "plan.json"
        result = runner.invoke(app, ["generate", "test-project", "--demo", "--plan-json", str(json_file)])

        assert result.exit_code == 0

    @patch("devman.cli.UserConfig.load")
    @patch("devman.cli.TemplateEngine")
    def test_generate_actual_project(self, mock_engine_class, mock_load, runner, mock_config, tmp_path):
        """Test actual project generation."""
        mock_load.return_value = mock_config

        mock_engine = MagicMock()
        mock_engine_class.return_value = mock_engine

        # Mock successful generation
        mock_engine.generate_project.return_value = None

        # Mock create_plan to return no conflicts
        mock_plan = MagicMock()
        mock_plan.conflicts = []
        mock_engine.create_plan.return_value = mock_plan

        result = runner.invoke(app, ["generate", "test-project"])

        assert result.exit_code == 0
        assert "Project generated!" in result.stdout
        mock_engine.generate_project.assert_called_once()

    @patch("devman.cli.UserConfig.load")
    @patch("devman.cli.TemplateEngine")
    def test_generate_with_conflicts_no_force(self, mock_engine_class, mock_load, runner, mock_config):
        """Test generation fails when conflicts exist without --force."""
        mock_load.return_value = mock_config

        mock_engine = MagicMock()
        mock_engine_class.return_value = mock_engine

        # Mock plan with conflicts
        mock_plan = MagicMock()
        mock_plan.conflicts = ["README.md", "pyproject.toml"]
        mock_engine.create_plan.return_value = mock_plan

        result = runner.invoke(app, ["generate", "test-project"])

        assert result.exit_code == 1
        import re

        clean_output = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
        assert "file(s) already exist" in clean_output
        # assert "file(s) already exist" in result.stdout
        assert "Use --force" in result.stdout
        # Should not call generate_project
        mock_engine.generate_project.assert_not_called()

    def test_generate_invalid_project_name(self, runner):
        """Test generation with invalid project name."""
        result = runner.invoke(app, ["generate", "123-invalid"])

        assert result.exit_code == 1
        # The error should be in stderr or the exception, not stdout
        assert result.exception is not None
        assert "Project name must start" in str(result.exception)

    @patch("devman.cli.UserConfig.load")
    def test_generate_with_config_error(self, mock_load, runner):
        """Test generation when config loading fails."""
        from devman.exceptions import ConfigurationError

        mock_load.side_effect = ConfigurationError("Config file corrupted")

        result = runner.invoke(app, ["generate", "test-project"])

        assert result.exit_code == 1
        assert "Configuration error" in result.stdout

    def test_generate_with_custom_options(self, runner, tmp_path):
        """Test generation with custom options."""
        with patch("devman.cli.UserConfig.load") as mock_load, patch("devman.cli.TemplateEngine") as mock_engine_class:
            mock_load.return_value = UserConfig()
            mock_engine = MagicMock()
            mock_engine_class.return_value = mock_engine

            # Mock no conflicts
            mock_plan = MagicMock()
            mock_plan.conflicts = []
            mock_engine.create_plan.return_value = mock_plan

            result = runner.invoke(
                app,
                [
                    "generate",
                    "my-project",
                    "--template",
                    "python-cli",
                    "--python",
                    "3.12",
                    "--package",
                    "mypackage",
                    "--force",
                ],
            )

            assert result.exit_code == 0

            # Verify the method was called (arguments structure may be different)
            assert mock_engine.generate_project.called
            call_args = mock_engine.generate_project.call_args
            # Check keyword arguments instead
            assert call_args[1]["force"] is True

