# tests/test_validation.py
from __future__ import annotations
import pytest
from pathlib import Path

from devman.validation import TemplateValidator, ProjectValidator
from devman.exceptions import TemplateValidationError, InvalidProjectNameError, ProjectExistsError


class TestTemplateValidator:
    """Test template validation functionality."""

    def test_validate_valid_template(self, tmp_path):
        """Test validating a valid template."""
        template_dir = tmp_path / "valid-template"
        template_dir.mkdir()

        # Create required copier.yml
        (template_dir / "copier.yml").write_text("""
project_name:
  type: str
  help: Project name
""")

        # Create some template files
        (template_dir / "README.md.j2").write_text("# {{ project_name }}")

        # Should not raise any exceptions
        TemplateValidator.validate_template(template_dir)

    def test_validate_template_missing_config(self, tmp_path):
        """Test validation fails when copier.yml is missing."""
        template_dir = tmp_path / "invalid-template"
        template_dir.mkdir()

        # Create some files but no copier.yml
        (template_dir / "README.md").write_text("# Project")

        with pytest.raises(TemplateValidationError, match="missing copier.yml"):
            TemplateValidator.validate_template(template_dir)

    def test_validate_template_nonexistent(self, tmp_path):
        """Test validation fails for nonexistent path."""
        nonexistent = tmp_path / "does-not-exist"

        with pytest.raises(TemplateValidationError, match="does not exist"):
            TemplateValidator.validate_template(nonexistent)

    def test_validate_template_file_not_dir(self, tmp_path):
        """Test validation fails when path is a file, not directory."""
        template_file = tmp_path / "template.txt"
        template_file.write_text("not a directory")

        with pytest.raises(TemplateValidationError, match="not a directory"):
            TemplateValidator.validate_template(template_file)

    def test_validate_template_path_absolute(self, tmp_path):
        """Test template path validation with absolute path."""
        template_dir = tmp_path / "template"
        template_dir.mkdir()
        (template_dir / "copier.yml").write_text("project_name: {type: str}")
        (template_dir / "file.j2").write_text("content")

        result = TemplateValidator.validate_template_path(template_dir)
        assert result == template_dir

    def test_validate_template_path_relative(self, tmp_path, monkeypatch):
        """Test template path validation with relative path."""
        # Change to tmp_path directory
        monkeypatch.chdir(tmp_path)

        template_dir = tmp_path / "template"
        template_dir.mkdir()
        (template_dir / "copier.yml").write_text("project_name: {type: str}")
        (template_dir / "file.j2").write_text("content")

        # Use relative path
        result = TemplateValidator.validate_template_path("template")
        assert result.is_absolute()
        assert result.name == "template"


class TestProjectValidator:
    """Test project validation functionality."""

    def test_validate_valid_project_name(self):
        """Test validation of valid project names."""
        valid_names = [
            "my-project",
            "awesome_lib",
            "Project123",
            "a1",
            "_private",
            "very-long-project-name-that-is-still-valid",
        ]

        for name in valid_names:
            # Should not raise any exceptions
            ProjectValidator.validate_project_name(name)

    def test_validate_invalid_project_names(self):
        """Test validation rejects invalid project names."""
        invalid_names = [
            "",  # Empty
            " ",  # Whitespace only
            "123project",  # Starts with number
            "-project",  # Starts with hyphen
            "project-",  # Ends with hyphen
            "project_",  # Ends with underscore
            "project with spaces",  # Contains spaces
            "project@special",  # Contains special characters
            "a" * 101,  # Too long
            "a",  # Too short
        ]

        for name in invalid_names:
            with pytest.raises(InvalidProjectNameError):
                ProjectValidator.validate_project_name(name)

    def test_validate_reserved_names(self):
        """Test that reserved names are rejected."""
        reserved_names = ["python", "pip", "con", "prn"]

        for name in reserved_names:
            with pytest.raises(InvalidProjectNameError, match="reserved"):
                ProjectValidator.validate_project_name(name)

    def test_validate_valid_package_names(self):
        """Test validation of valid package names."""
        valid_names = [
            "",  # Empty is OK (will be auto-generated)
            "mypackage",
            "my_package",
            "_private",
            "package123",
        ]

        for name in valid_names:
            # Should not raise any exceptions
            ProjectValidator.validate_package_name(name)

    def test_validate_invalid_package_names(self):
        """Test validation rejects invalid package names."""
        invalid_names = [
            "123package",  # Starts with number
            "my-package",  # Contains hyphen
            "package.name",  # Contains dot
            "package name",  # Contains space
        ]

        for name in invalid_names:
            with pytest.raises(InvalidProjectNameError):
                ProjectValidator.validate_package_name(name)

    def test_validate_python_keyword_package_name(self):
        """Test that Python keywords are rejected as package names."""
        keywords = ["def", "class", "import", "if", "else"]

        for keyword in keywords:
            with pytest.raises(InvalidProjectNameError, match="Python keyword"):
                ProjectValidator.validate_package_name(keyword)

    def test_validate_python_version(self):
        """Test Python version validation."""
        valid_versions = ["3.9", "3.10", "3.11", "3.12", "3.13"]

        for version in valid_versions:
            # Should not raise any exceptions
            ProjectValidator.validate_python_version(version)

    def test_validate_invalid_python_versions(self):
        """Test invalid Python version rejection."""
        invalid_versions = ["2.7", "3.8", "3.14", "3", "python3.11", "latest"]

        for version in invalid_versions:
            with pytest.raises(InvalidProjectNameError, match="Python version must be"):
                ProjectValidator.validate_python_version(version)

    def test_validate_destination_new_directory(self, tmp_path):
        """Test validation of new destination directory."""
        destination = tmp_path / "new-project"

        # Should not raise any exceptions
        ProjectValidator.validate_destination(destination, force=False)

    def test_validate_destination_existing_empty(self, tmp_path):
        """Test validation of existing empty directory."""
        destination = tmp_path / "empty-project"
        destination.mkdir()

        # Should not raise any exceptions
        ProjectValidator.validate_destination(destination, force=False)

    def test_validate_destination_existing_nonempty(self, tmp_path):
        """Test validation fails for existing non-empty directory."""
        destination = tmp_path / "existing-project"
        destination.mkdir()
        (destination / "existing-file.txt").write_text("content")

        with pytest.raises(ProjectExistsError):
            ProjectValidator.validate_destination(destination, force=False)

    def test_validate_destination_existing_nonempty_force(self, tmp_path):
        """Test validation passes with force for existing non-empty directory."""
        destination = tmp_path / "existing-project"
        destination.mkdir()
        (destination / "existing-file.txt").write_text("content")

        # Should not raise any exceptions with force=True
        ProjectValidator.validate_destination(destination, force=True)

    def test_validate_destination_is_file(self, tmp_path):
        """Test validation fails when destination is a file."""
        destination = tmp_path / "not-a-directory.txt"
        destination.write_text("content")

        with pytest.raises(InvalidProjectNameError, match="is a file"):
            ProjectValidator.validate_destination(destination, force=False)

    def test_validate_destination_parent_missing(self, tmp_path):
        """Test validation creates parent directories."""
        destination = tmp_path / "deep" / "nested" / "project"

        # Should create parent directories and not raise exceptions
        ProjectValidator.validate_destination(destination, force=False)

        # Check that parent was created
        assert destination.parent.exists()
        assert destination.parent.is_dir()

