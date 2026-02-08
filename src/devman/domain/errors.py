from __future__ import annotations

from pathlib import Path


class DomainError(Exception):
    """Base class for all domain errors."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        return self.message


class PathNotFoundError(DomainError):
    """Path does not exist on filesystem."""

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"Path does not exist: {self.path}")


class PathNotDirectoryError(DomainError):
    """Path exists but is not a directory."""

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"Path is not a directory: {self.path}")


class WatchError(DomainError):
    """Generic error for watcher domain operations."""
