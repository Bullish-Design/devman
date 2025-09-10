# src/devman/exceptions.py
from __future__ import annotations
from pathlib import Path


class DevmanError(Exception):
    """Base exception for devman errors."""
    pass


class TemplateNotFoundError(DevmanError):
    """Template not found or inaccessible."""
    def __init__(self, template_path: str | Path):
        self.template_path = template_path
        super().__init__(f"Template not found: {template_path}")


class TemplateValidationError(DevmanError):
    """Template is invalid or malformed."""
    pass


class ProjectExistsError(DevmanError):
    """Project directory already exists."""
    def __init__(self, path: Path):
        self.path = path
        super().__init__(f"Project directory already exists: {path}")


class InvalidProjectNameError(DevmanError):
    """Project name is invalid."""
    pass


class ConfigurationError(DevmanError):
    """Configuration file is invalid or corrupted."""
    pass


class CopierExecutionError(DevmanError):
    """Error occurred during Copier template execution."""
    def __init__(self, message: str, original_error: Exception | None = None):
        self.original_error = original_error
        super().__init__(message)