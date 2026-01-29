# src/devman/domain/protocols.py
"""Domain protocols for dependency injection."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from result import Err, Ok, Result

from devman.domain.errors import DomainError


@dataclass(frozen=True)
class CommandResult:
    """Result of executing an external command."""

    exit_code: int
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True)
class CommandError(DomainError):
    """Error from external command execution."""

    exit_code: int
    stderr: str | None = None


class CommandExecutor(Protocol):
    """Protocol for executing external commands."""

    def execute(
        self, args: list[str], cwd: Path | None = None
    ) -> Result[CommandResult, CommandError]:
        """Execute a command and return the result."""
        ...


class FileReader(Protocol):
    """Protocol for reading file contents."""

    def read_text(self, path: Path) -> Result[str, DomainError]:
        """Read text content from a file."""
        ...

    def read_yaml(self, path: Path) -> Result[dict[str, Any], DomainError]:
        """Read and parse YAML content from a file."""
        ...


class SubprocessExecutor:
    """Infrastructure implementation of CommandExecutor using subprocess."""

    def execute(
        self, args: list[str], cwd: Path | None = None
    ) -> Result[CommandResult, CommandError]:
        """Execute a command via subprocess."""
        try:
            result = subprocess.run(
                args,
                cwd=cwd,
                check=True,
                capture_output=True,
                text=True,
            )
            return Ok(
                CommandResult(
                    exit_code=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                )
            )
        except subprocess.CalledProcessError as e:
            return Err(
                CommandError(
                    message=f"Command failed with exit code {e.returncode}",
                    exit_code=e.returncode,
                    stderr=e.stderr if e.stderr else None,
                )
            )
        except FileNotFoundError:
            return Err(
                CommandError(
                    message=f"Command not found: {args[0]}",
                    exit_code=127,
                )
            )
