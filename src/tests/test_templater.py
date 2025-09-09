# tests/test_templater.py
"""Test templater functionality."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import pytest

from devman.config import ProjectConfig
from devman.templater import DevEnvTemplater, ProjectGenerator, ProjectStructure
from devman.templates import TemplateRegistry


class TestProjectStructure:
    """Test ProjectStructure functionality."""

    def test_create_directories(self) -> None:
        """Test directory structure creation."""
        with TemporaryDirectory() as temp_dir:
            target_path = Path(temp_dir)
            config = ProjectConfig(name="test-project")

            structure = ProjectStructure(target_path=target_path, config=config)
            structure.create_directories()

            # Check directories exist
            assert (target_path / "src" / "test-project").exists()
            assert (target_path / "tests").exists()

            # Check __init__.py files
            assert (target_path / "src" / "test-project" / "__init__.py").exists()
            assert (target_path / "tests" / "__init__.py").exists()

    def test_create_starter_files_api(self) -> None:
        """Test API starter file creation."""
        with TemporaryDirectory() as temp_dir:
            target_path = Path(temp_dir)
            config = ProjectConfig(name="api-project", project_type="api")

            structure = ProjectStructure(target_path=target_path, config=config)
            structure.create_directories()
            structure.create_starter_files()

            main_py = target_path / "src" / "api-project" / "main.py"
            assert main_py.exists()

            content = main_py.read_text()
            assert "FastAPI" in content
            assert "api-project" in content
            assert "@app.get" in content

    def test_create_starter_files_cli(self) -> None:
        """Test CLI starter file creation."""
        with TemporaryDirectory() as temp_dir:
            target_path = Path(temp_dir)
            config = ProjectConfig(name="cli-project", project_type="cli")

            structure = ProjectStructure(target_path=target_path, config=config)
            structure.create_directories()
            structure.create_starter_files()

            cli_py = target_path / "src" / "cli-project" / "cli.py"
            assert cli_py.exists()

            content = cli_py.read_text()
            assert "typer" in content
            assert "@app.command" in content

    def test_create_test_file(self) -> None:
        """Test test file creation."""
        with TemporaryDirectory() as temp_dir:
            target_path = Path(temp_dir)
            config = ProjectConfig(name="test-project")

            structure = ProjectStructure(target_path=target_path, config=config)
            structure.create_directories()
            structure.create_starter_files()

            test_file = target_path / "tests" / "test_main.py"
            assert test_file.exists()

            content = test_file.read_text()
            assert "test_placeholder" in content
            assert "assert True" in content


class TestProjectGenerator:
    """Test ProjectGenerator functionality."""

    def test_get_files_to_generate_basic(self) -> None:
        """Test basic files to generate."""
        config = ProjectConfig(name="test", container_type="none")
        generator = ProjectGenerator(
            config=config, target_path=Path("/tmp"), registry=Mock()
        )

        files = generator.get_files_to_generate()
        expected = ["devenv.nix", "justfile", "pyproject.toml", ".envrc"]
        assert files == expected

    def test_get_files_to_generate_docker(self) -> None:
        """Test files for Docker container."""
        config = ProjectConfig(name="test", container_type="docker")
        generator = ProjectGenerator(
            config=config, target_path=Path("/tmp"), registry=Mock()
        )

        files = generator.get_files_to_generate()
        assert "Dockerfile" in files
        assert "docker-compose.yml" in files

    def test_get_files_to_generate_nixos(self) -> None:
        """Test files for NixOS container."""
        config = ProjectConfig(name="test", container_type="nixos")
        generator = ProjectGenerator(
            config=config, target_path=Path("/tmp"), registry=Mock()
        )

        files = generator.get_files_to_generate()
        assert "container.nix" in files

    def test_generate_files(self) -> None:
        """Test file generation from templates."""
        with TemporaryDirectory() as temp_dir:
            target_path = Path(temp_dir)
            config = ProjectConfig(name="test-project")

            # Mock registry
            registry = Mock()
            registry.has_template.return_value = True
            registry.render_template.return_value = "# Generated content"

            generator = ProjectGenerator(
                config=config, target_path=target_path, registry=registry
            )

            generator.generate_files()

            # Check that files were created
            assert (target_path / "devenv.nix").exists()
            assert (target_path / "justfile").exists()
            assert (target_path / "pyproject.toml").exists()
            assert (target_path / ".envrc").exists()

            # Check content
            content = (target_path / "devenv.nix").read_text()
            assert content == "# Generated content"

    @patch("subprocess.run")
    def test_initialize_python_project_success(self, mock_run: Mock) -> None:
        """Test successful Python project initialization."""
        with TemporaryDirectory() as temp_dir:
            target_path = Path(temp_dir)
            config = ProjectConfig(name="test")

            generator = ProjectGenerator(
                config=config, target_path=target_path, registry=Mock()
            )

            mock_run.return_value = Mock()
            generator.initialize_python_project()

            mock_run.assert_called_once_with(
                ["uv", "init", "--python", "3.11"],
                cwd=target_path,
                check=True,
                capture_output=True,
            )

    @patch("subprocess.run")
    def test_initialize_python_project_failure(self, mock_run: Mock) -> None:
        """Test Python project initialization failure handling."""
        with TemporaryDirectory() as temp_dir:
            target_path = Path(temp_dir)
            config = ProjectConfig(name="test")

            generator = ProjectGenerator(
                config=config, target_path=target_path, registry=Mock()
            )

            # Simulate subprocess failure
            mock_run.side_effect = FileNotFoundError()

            # Should not raise exception
            generator.initialize_python_project()


class TestDevEnvTemplater:
    """Test DevEnvTemplater functionality."""

    def test_init_default_registry(self) -> None:
        """Test templater initialization with default registry."""
        templater = DevEnvTemplater()
        assert templater.registry is not None
        assert isinstance(templater.registry, TemplateRegistry)

    def test_ensure_templates_exist(self) -> None:
        """Test template directory and file creation."""
        with TemporaryDirectory() as temp_dir:
            templates_dir = Path(temp_dir) / "templates"
            registry = TemplateRegistry()
            registry.add_template("test.j2", "test content")

            templater = DevEnvTemplater(templates_dir=templates_dir, registry=registry)

            templater.ensure_templates_exist()

            assert templates_dir.exists()
            assert (templates_dir / "test.j2").exists()
            assert (templates_dir / "test.j2").read_text() == "test content"

    @patch("devman.templater.ProjectGenerator")
    @patch("devman.templater.ProjectStructure")
    def test_generate_project(self, mock_structure: Mock, mock_generator: Mock) -> None:
        """Test complete project generation."""
        with TemporaryDirectory() as temp_dir:
            target_path = Path(temp_dir)
            config = ProjectConfig(name="test-project")

            templater = DevEnvTemplater()
            templater.generate_project(config, target_path)

            # Check that directory was created
            assert target_path.exists()

            # Check that components were called
            mock_structure.assert_called_once()
            mock_generator.assert_called_once()

    def test_render_template(self) -> None:
        """Test template rendering delegation."""
        registry = Mock()
        registry.render_template.return_value = "rendered content"

        templater = DevEnvTemplater(registry=registry)
        result = templater.render_template("test.j2", {"key": "value"})

        assert result == "rendered content"
        registry.render_template.assert_called_once_with("test.j2", {"key": "value"})

