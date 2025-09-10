# tests/test_integration.py
from __future__ import annotations
import pytest
from pathlib import Path

from devman.models import ProjectConfig, TemplateEngine
from devman.config import UserConfig
from devman.exceptions import (
    TemplateNotFoundError,
    InvalidProjectNameError,
    ProjectExistsError,
    CopierExecutionError,
)


class TestExceptions:
    """Test custom exception handling."""

    def test_template_not_found_error(self):
        """Test TemplateNotFoundError."""
        path = Path("/nonexistent/template")
        error = TemplateNotFoundError(path)

        assert str(error) == f"Template not found: {path}"
        assert error.template_path == path

    def test_invalid_project_name_error(self):
        """Test InvalidProjectNameError."""
        error = InvalidProjectNameError("Invalid name format")
        assert str(error) == "Invalid name format"

    def test_project_exists_error(self):
        """Test ProjectExistsError."""
        path = Path("/existing/project")
        error = ProjectExistsError(path)

        assert str(error) == f"Project directory already exists: {path}"
        assert error.path == path

    def test_copier_execution_error(self):
        """Test CopierExecutionError."""
        original = ValueError("Original error")
        error = CopierExecutionError("Copier failed", original_error=original)

        assert str(error) == "Copier failed"
        assert error.original_error == original


class TestEndToEndIntegration:
    """Test complete workflows end-to-end."""

    def test_complete_project_generation(self, minimal_copier_template, temp_project_dir):
        """Test complete project generation workflow."""
        # Create configuration
        config = ProjectConfig(
            project_name="my-awesome-project",
            python_version="3.11",
            use_nix=True,
            use_docker=False,
            use_just=True,
        )

        # Initialize template engine
        engine = TemplateEngine()

        # Generate project
        engine.generate_project(
            template_path=minimal_copier_template,
            destination=temp_project_dir,
            config=config,
            force=False,
        )

        # Verify project structure was created
        assert temp_project_dir.exists()
        assert (temp_project_dir / "README.md").exists()
        assert (temp_project_dir / "pyproject.toml").exists()
        assert (temp_project_dir / "src" / "my_awesome_project" / "__init__.py").exists()
        assert (temp_project_dir / "tests" / "test_my_awesome_project.py").exists()

        # Verify conditional files
        assert (temp_project_dir / "justfile").exists()  # use_just=True
        assert not (temp_project_dir / "Dockerfile").exists()  # use_docker=False
        assert (temp_project_dir / "flake.nix").exists()  # use_nix=True

        # Verify content substitution
        readme_content = (temp_project_dir / "README.md").read_text()
        assert "my-awesome-project" in readme_content
        assert "Python 3.11" in readme_content

        pyproject_content = (temp_project_dir / "pyproject.toml").read_text()
        assert 'name = "my-awesome-project"' in pyproject_content
        assert ">=3.11" in pyproject_content

        init_content = (temp_project_dir / "src" / "my_awesome_project" / "__init__.py").read_text()
        assert "my-awesome-project package" in init_content

    def test_plan_creation_and_analysis(self, minimal_copier_template, temp_project_dir):
        """Test plan creation and conflict analysis."""
        config = ProjectConfig(project_name="test-project")
        engine = TemplateEngine()

        # Create initial plan
        plan = engine.create_plan(minimal_copier_template, temp_project_dir, config)

        # Verify plan structure
        assert plan.destination == temp_project_dir
        assert len(plan.files) > 0
        assert len(plan.conflicts) == 0  # No conflicts initially

        # Check that expected files are in plan
        assert "README.md" in plan.files
        assert "pyproject.toml" in plan.files

        # Create a conflicting file
        temp_project_dir.mkdir(parents=True, exist_ok=True)
        (temp_project_dir / "README.md").write_text("Existing content")

        # Re-create plan and check for conflicts
        plan = engine.create_plan(minimal_copier_template, temp_project_dir, config)
        assert "README.md" in plan.conflicts
        assert len(plan.conflicts) == 1

        # Test plan summary
        summary = plan.get_summary()
        assert summary["conflicts"] == 1
        assert summary["total_files"] > 0

    def test_template_validation_workflow(self, tmp_path):
        """Test template validation in realistic scenarios."""
        engine = TemplateEngine()

        # Test with nonexistent template
        with pytest.raises(TemplateNotFoundError):
            engine._validate_template_path(tmp_path / "nonexistent")

        # Test with invalid template (no copier.yml)
        invalid_template = tmp_path / "invalid"
        invalid_template.mkdir()
        (invalid_template / "some_file.txt").write_text("content")

        with pytest.raises(TemplateNotFoundError):
            engine._validate_template_path(invalid_template)

        # Test with valid template
        valid_template = tmp_path / "valid"
        valid_template.mkdir()
        (valid_template / "copier.yml").write_text("project_name: {type: str}")
        (valid_template / "file.j2").write_text("content")

        # Should not raise any exceptions
        validated_path = engine._validate_template_path(valid_template)
        assert validated_path == valid_template

    def test_config_integration_with_generation(self, minimal_copier_template, temp_project_dir, isolated_config):
        """Test configuration integration with project generation."""
        # Create user config
        user_config = UserConfig(
            default_python_version="3.12",
            author_name="Integration Test User",
            use_docker=True,
            use_nix=False,
        )

        config_file = isolated_config / "devman" / "config.yml"
        user_config.save(config_file)

        # Load config and verify it was saved/loaded correctly
        loaded_config = UserConfig.load()
        assert loaded_config.default_python_version == "3.12"
        assert loaded_config.author_name == "Integration Test User"
        assert loaded_config.use_docker is True
        assert loaded_config.use_nix is False

        # Create project config using user defaults
        project_config = ProjectConfig(
            project_name="integration-test",
            python_version=loaded_config.default_python_version,
            use_docker=loaded_config.use_docker,
            use_nix=loaded_config.use_nix,
        )

        # Generate project
        engine = TemplateEngine()
        engine.generate_project(
            template_path=minimal_copier_template,
            destination=temp_project_dir,
            config=project_config,
        )

        # Verify configuration was applied
        pyproject_content = (temp_project_dir / "pyproject.toml").read_text()
        assert ">=3.12" in pyproject_content

        # Check conditional file creation based on config
        assert (temp_project_dir / "Dockerfile").exists()  # use_docker=True
        assert not (temp_project_dir / "flake.nix").exists()  # use_nix=False

    def test_error_handling_during_generation(self, tmp_path):
        """Test error handling during project generation."""
        engine = TemplateEngine()
        config = ProjectConfig(project_name="test")

        # Test with completely invalid template path
        with pytest.raises(TemplateNotFoundError):
            engine.generate_project(
                template_path="/absolutely/nonexistent/path",
                destination=tmp_path / "output",
                config=config,
            )

        # Test with file instead of directory as destination
        file_destination = tmp_path / "not_a_dir.txt"
        file_destination.write_text("content")

        valid_template = tmp_path / "template"
        valid_template.mkdir()
        (valid_template / "copier.yml").write_text("project_name: {type: str}")
        (valid_template / "example.j2").write_text("{{ project_name }}")  # Add template file

        with pytest.raises(InvalidProjectNameError):
            engine.generate_project(
                template_path=valid_template,
                destination=file_destination,
                config=config,
            )

    def test_project_config_validation_edge_cases(self):
        """Test ProjectConfig validation with edge cases."""
        # Test very long project name
        with pytest.raises(InvalidProjectNameError):
            ProjectConfig(project_name="a" * 101)

        # Test project name with only special characters
        with pytest.raises(InvalidProjectNameError):
            ProjectConfig(project_name="@#$%")

        # Test reserved name
        with pytest.raises(InvalidProjectNameError):
            ProjectConfig(project_name="python")

        # Test valid edge cases
        config = ProjectConfig(project_name="a1")  # Minimal valid name
        assert config.project_slug == "a1"

        config = ProjectConfig(project_name="_private")  # Starts with underscore
        assert config.project_slug == "_private"

        # Test package name validation
        with pytest.raises(InvalidProjectNameError):
            ProjectConfig(project_name="test", package_name="123invalid")

        with pytest.raises(InvalidProjectNameError):
            ProjectConfig(project_name="test", package_name="def")  # Python keyword

    def test_file_snapshot_edge_cases(self, tmp_path):
        """Test FileSnapshot creation with various file types."""
        from devman.models import TemplateEngine

        engine = TemplateEngine()

        # Test with text file
        text_file = tmp_path / "text.txt"
        text_content = "Hello, world! 🌍"
        text_file.write_text(text_content, encoding="utf-8")

        snapshot = engine._create_file_snapshot(text_file)
        assert snapshot.content == text_content
        assert snapshot.size == len(text_content)
        assert not snapshot.is_binary

        # Test with binary file
        binary_file = tmp_path / "binary.bin"
        binary_content = b"\x00\x01\x02\xff"
        binary_file.write_bytes(binary_content)

        snapshot = engine._create_file_snapshot(binary_file)
        assert snapshot.is_binary
        assert snapshot.size == len(binary_content)
        assert "binary file" in snapshot.content

        # Test with empty file
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("")

        snapshot = engine._create_file_snapshot(empty_file)
        assert snapshot.content == ""
        assert snapshot.size == 0
        assert not snapshot.is_binary

