# src/devman/validation.py
from __future__ import annotations
import re
from pathlib import Path
from typing import List

from .exceptions import TemplateValidationError, InvalidProjectNameError


class TemplateValidator:
    """Validates template structure and content."""

    REQUIRED_FILES = ["copier.yml", "copier.yaml"]

    @classmethod
    def validate_template(cls, template_path: Path) -> None:
        """Validate template has required structure."""
        if not template_path.exists():
            raise TemplateValidationError(f"Template path does not exist: {template_path}")

        if not template_path.is_dir():
            raise TemplateValidationError(f"Template path is not a directory: {template_path}")

        # Check for copier config
        config_files = [template_path / f for f in cls.REQUIRED_FILES]
        if not any(f.exists() for f in config_files):
            raise TemplateValidationError(f"Template missing copier.yml or copier.yaml in {template_path}")

        # Validate that at least one template file exists
        template_files = list(template_path.rglob("*.j2")) + list(template_path.rglob("*.jinja"))
        if not template_files:
            # Check if there are any files that could be templates
            all_files = [f for f in template_path.rglob("*") if f.is_file()]
            config_file_names = {f.name for f in config_files if f.exists()}
            non_config_files = [f for f in all_files if f.name not in config_file_names]

            if not non_config_files:
                raise TemplateValidationError(f"Template contains no files to copy: {template_path}")

    @classmethod
    def validate_template_path(cls, template_path: str | Path) -> Path:
        """Validate and normalize template path."""
        path = Path(template_path)

        # Handle relative paths
        if not path.is_absolute():
            path = Path.cwd() / path

        cls.validate_template(path)
        return path


class ProjectValidator:
    """Validates project configuration and names."""

    # Reserved names that shouldn't be used as project names
    RESERVED_NAMES = {
        "con",
        "prn",
        "aux",
        "nul",  # Windows reserved
        "python",
        "pip",
        "setuptools",  # Python reserved
        "src",
        "lib",  # Common conflicts
    }

    @classmethod
    def validate_project_name(cls, name: str) -> None:
        """Validate project name follows conventions."""
        if not name:
            raise InvalidProjectNameError("Project name cannot be empty")

        if not name.strip():
            raise InvalidProjectNameError("Project name cannot be only whitespace")

        # Check length
        if len(name) > 100:
            raise InvalidProjectNameError("Project name too long (max 100 characters)")

        if len(name) < 2:
            raise InvalidProjectNameError("Project name too short (min 2 characters)")

        # Check format - must start with letter or underscore, contain only alphanumeric, hyphens, underscores
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_-]*$", name):
            raise InvalidProjectNameError(
                "Project name must start with letter or underscore and contain only "
                "letters, numbers, hyphens, and underscores"
            )

        # Check for reserved names
        if name.lower() in cls.RESERVED_NAMES:
            raise InvalidProjectNameError(f"Project name '{name}' is reserved")

        # Check for leading/trailing hyphens or underscores (bad practice)
        if name.startswith(("-", "_")) and len(name) > 1:
            if name.startswith("-"):
                raise InvalidProjectNameError("Project name should not start with hyphen")

        if name.endswith(("-", "_")):
            raise InvalidProjectNameError("Project name should not end with hyphen or underscore")

    @classmethod
    def validate_package_name(cls, name: str) -> None:
        """Validate Python package name."""
        if not name:
            return  # Empty is OK, will be auto-generated

        # Python package names are more restrictive
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
            raise InvalidProjectNameError(
                "Package name must start with letter or underscore and contain only "
                "letters, numbers, and underscores (no hyphens)"
            )

        # Check for Python keywords
        import keyword

        if keyword.iskeyword(name):
            raise InvalidProjectNameError(f"Package name '{name}' is a Python keyword")

    @classmethod
    def validate_python_version(cls, version: str) -> None:
        """Validate Python version format."""
        if not re.match(r"^3\.(9|10|11|12|13)$", version):
            raise InvalidProjectNameError("Python version must be 3.9, 3.10, 3.11, 3.12, or 3.13")

    @classmethod
    def validate_destination(cls, destination: Path, force: bool = False) -> None:
        """Validate destination path."""
        if destination.exists():
            if destination.is_file():
                raise InvalidProjectNameError(f"Destination exists and is a file: {destination}")

            if not force and any(destination.iterdir()):
                from .exceptions import ProjectExistsError

                raise ProjectExistsError(destination)

        # Check if parent directory is writable
        parent = destination.parent
        if not parent.exists():
            try:
                parent.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                raise InvalidProjectNameError(f"Cannot create parent directory: {parent}")

        if not parent.is_dir():
            raise InvalidProjectNameError(f"Parent path is not a directory: {parent}")

        # Test write permissions
        try:
            test_file = parent / f".devman_test_{destination.name}"
            test_file.touch()
            test_file.unlink()
        except PermissionError:
            raise InvalidProjectNameError(f"No write permission in: {parent}")

