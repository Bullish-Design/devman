# src/devman/application/use_cases.py
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from result import Err, Ok, Result

from devman.domain.errors import DomainError, DevmanNotFoundError
from devman.domain.finder import DevmanFinder
from devman.domain.models import DevmanDirectory, ProjectRoot, ValidationResult
from devman.templates import TemplateReference, TemplateValidator


@dataclass(frozen=True)
class FindDevmanCommand:
    """Command to locate .devman directory."""

    start_path: Path | None = None
    projects_root: ProjectRoot | None = None


@dataclass(frozen=True)
class FindDevmanResult:
    """Result of finding .devman directory."""

    devman_directory: DevmanDirectory


class FindDevmanUseCase:
    """Use case: Find nearest .devman directory."""

    def execute(
        self, command: FindDevmanCommand
    ) -> Result[FindDevmanResult, DevmanNotFoundError]:
        """Execute the find operation."""
        finder = DevmanFinder(projects_root=command.projects_root)
        result = finder.find(start_path=command.start_path)

        return result.map(
            lambda devman_dir: FindDevmanResult(devman_directory=devman_dir)
        )


@dataclass(frozen=True)
class RunDevenvCommand:
    """Command to run devenv with arguments."""

    devenv_args: list[str]
    devman_directory: DevmanDirectory


@dataclass(frozen=True)
class RunDevenvResult:
    """Result of running devenv command."""

    exit_code: int


@dataclass(frozen=True)
class RunDevenvError(DomainError):
    """Error running devenv command."""

    exit_code: int
    stderr: str | None = None


class RunDevenvUseCase:
    """Use case: Execute devenv command in .devman directory."""

    def execute(
        self, command: RunDevenvCommand
    ) -> Result[RunDevenvResult, RunDevenvError]:
        """Execute devenv with provided arguments."""
        try:
            result = subprocess.run(
                ["devenv", *command.devenv_args],
                cwd=command.devman_directory.path,
                check=True,
                capture_output=True,
                text=True,
            )
            return Ok(RunDevenvResult(exit_code=result.returncode))

        except subprocess.CalledProcessError as e:
            return Err(
                RunDevenvError(
                    message=f"devenv failed with exit code {e.returncode}",
                    exit_code=e.returncode,
                    stderr=e.stderr if e.stderr else None,
                )
            )

        except FileNotFoundError:
            return Err(
                RunDevenvError(
                    message="devenv command not found",
                    exit_code=127,
                )
            )


@dataclass(frozen=True)
class ValidateTemplateCommand:
    """Command to validate a template."""

    template_reference: TemplateReference


@dataclass(frozen=True)
class ValidateTemplateResult:
    """Result of template validation."""

    validation_result: ValidationResult

    @property
    def is_valid(self) -> bool:
        return self.validation_result.is_valid


class ValidateTemplateUseCase:
    """Use case: Validate template structure and schema."""

    def execute(self, command: ValidateTemplateCommand) -> ValidateTemplateResult:
        """Execute validation."""
        validation_result = TemplateValidator.validate_typed(command.template_reference)
        return ValidateTemplateResult(validation_result=validation_result)
