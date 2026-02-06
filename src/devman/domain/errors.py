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
