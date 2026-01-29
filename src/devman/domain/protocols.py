# src/devman/domain/protocols.py
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from result import Result

from devman.domain.errors import DomainError

if TYPE_CHECKING:
    from devman.config import DevmanConfig


class TemplateSource(Protocol):
    """Protocol for template sources (file, git, http)."""

    def resolve(self) -> Result[Path, DomainError]:
        """Resolve template to local filesystem path."""
        ...

    def validate(self) -> Result[None, DomainError]:
        """Validate template structure and schema."""
        ...


class ConfigRepository(Protocol):
    """Protocol for configuration persistence."""

    def load(self) -> Result[DevmanConfig, DomainError]:
        """Load configuration from storage."""
        ...

    def save(self, config: DevmanConfig) -> Result[None, DomainError]:
        """Persist configuration to storage."""
        ...
