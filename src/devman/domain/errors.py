# src/devman/domain/errors.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DomainError:
    """Base class for all domain errors."""

    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class PathNotFoundError(DomainError):
    """Path does not exist on filesystem."""

    path: Path

    def __str__(self) -> str:
        return f"Path does not exist: {self.path}"


@dataclass(frozen=True)
class PathNotDirectoryError(DomainError):
    """Path exists but is not a directory."""

    path: Path

    def __str__(self) -> str:
        return f"Path is not a directory: {self.path}"


@dataclass(frozen=True)
class InvalidGitUrlError(DomainError):
    """Git URL format is invalid."""

    url: str

    def __str__(self) -> str:
        return f"Invalid git URL format: {self.url}"


@dataclass(frozen=True)
class ValidationError(DomainError):
    """Template validation failed."""

    errors: list[str]
    warnings: list[str]

    def __str__(self) -> str:
        parts = []
        if self.errors:
            parts.append(f"Errors: {', '.join(self.errors)}")
        if self.warnings:
            parts.append(f"Warnings: {', '.join(self.warnings)}")
        return "; ".join(parts)


@dataclass(frozen=True)
class DevmanNotFoundError(DomainError):
    """No .devman directory found in search path."""

    search_root: Path

    def __str__(self) -> str:
        return f"No .devman directory found starting from {self.search_root}"


@dataclass(frozen=True)
class QuestionValidationError(DomainError):
    """Question schema validation failed."""

    question_name: str
    reason: str

    def __str__(self) -> str:
        return f"Question '{self.question_name}': {self.reason}"
