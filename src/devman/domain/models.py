# src/devman/domain/models.py
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, field_validator
from result import Err, Ok, Result

from devman.constants import DEVMAN_DIR_NAME
from devman.domain.errors import PathNotDirectoryError, PathNotFoundError


class ValidationIssue(BaseModel):
    """Individual validation issue with metadata."""

    severity: str = Field(description="error or warning")
    message: str = Field(description="Human-readable issue description")
    location: str | None = Field(
        None, description="Question name, file path, or field name"
    )
    code: str | None = Field(None, description="Machine-readable error code")


class ValidationResult(BaseModel):
    """Structured validation result."""

    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Check if validation passed (no errors)."""
        return len(self.errors) == 0

    def add_error(
        self, message: str, location: str | None = None, code: str | None = None
    ) -> None:
        """Add validation error."""
        self.errors.append(
            ValidationIssue(
                severity="error",
                message=message,
                location=location,
                code=code,
            )
        )

    def add_warning(
        self, message: str, location: str | None = None, code: str | None = None
    ) -> None:
        """Add validation warning."""
        self.warnings.append(
            ValidationIssue(
                severity="warning",
                message=message,
                location=location,
                code=code,
            )
        )


class ProjectRoot(BaseModel):
    """Value object representing validated project root directory."""

    path: Path = Field(description="Absolute path to project root")

    @field_validator("path")
    @classmethod
    def must_be_absolute_directory(cls, v: Path) -> Path:
        """Ensure path is absolute and points to existing directory."""
        resolved = v.expanduser().resolve()

        if not resolved.exists():
            raise ValueError(f"Path does not exist: {resolved}")

        if not resolved.is_dir():
            raise ValueError(f"Path is not a directory: {resolved}")

        return resolved

    @classmethod
    def create(
        cls, path: Path
    ) -> Result[ProjectRoot, PathNotFoundError | PathNotDirectoryError]:
        """Factory method using Result type for error handling."""
        try:
            return Ok(cls(path=path))
        except ValueError as e:
            error_msg = str(e)
            if "does not exist" in error_msg:
                return Err(PathNotFoundError(message=error_msg, path=path))
            else:
                return Err(PathNotDirectoryError(message=error_msg, path=path))


class DevmanDirectory(BaseModel):
    """Value object representing .devman configuration directory."""

    path: Path = Field(description="Absolute path to .devman directory")

    @field_validator("path")
    @classmethod
    def must_be_devman_directory(cls, v: Path) -> Path:
        """Ensure path ends with .devman and exists."""
        resolved = v.resolve()

        if not resolved.exists():
            raise ValueError(f"{DEVMAN_DIR_NAME} directory does not exist: {resolved}")

        if resolved.name != DEVMAN_DIR_NAME:
            raise ValueError(f"Path must end with {DEVMAN_DIR_NAME}: {resolved}")

        return resolved

    @classmethod
    def create(cls, path: Path) -> Result[DevmanDirectory, PathNotFoundError]:
        """Factory method using Result type."""
        try:
            return Ok(cls(path=path))
        except ValueError as e:
            return Err(PathNotFoundError(message=str(e), path=path))
