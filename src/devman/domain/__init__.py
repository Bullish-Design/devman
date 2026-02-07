# src/devman/domain/__init__.py
"""Domain layer: pure business logic with no framework dependencies."""

from devman.domain.errors import DomainError, PathNotDirectoryError, PathNotFoundError, WatchError

__all__ = [
    "DomainError",
    "PathNotFoundError",
    "PathNotDirectoryError",
    "WatchError",
]

