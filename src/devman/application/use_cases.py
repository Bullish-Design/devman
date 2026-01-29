# src/devman/application/use_cases.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from result import Err, Ok, Result

from devman.constants import DEVENV_COMMAND
from devman.domain.errors import DevmanNotFoundError
from devman.domain.finder import DevmanFinder
from devman.domain.models import DevmanDirectory, ProjectRoot, ValidationResult
from devman.domain.protocols import (
    CommandError,
    CommandExecutor,
    SubprocessExecutor,
)
from devman.domain.templates import TemplateReference, TemplateValidator


@dataclass(frozen=True)
class FindDevmanCommand:
    """Command to locate .devman directory."""

    start_path: Path
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


class RunDevenvUseCase:
    """Use case: Execute devenv command in .devman directory."""

    def __init__(self, executor: CommandExecutor | None = None) -> None:
        self._executor = executor or SubprocessExecutor()

    def execute(
        self, command: RunDevenvCommand
    ) -> Result[RunDevenvResult, CommandError]:
        """Execute devenv with provided arguments."""
        result = self._executor.execute(
            args=[DEVENV_COMMAND, *command.devenv_args],
            cwd=command.devman_directory.path,
        )

        return result.map(lambda r: RunDevenvResult(exit_code=r.exit_code))


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
        validation_result = TemplateValidator.validate_reference(
            command.template_reference
        )
        return ValidateTemplateResult(validation_result=validation_result)


@dataclass(frozen=True)
class CreateProjectCommand:
    """Command to create a new project from a template."""

    template_source: str
    destination: Path
    data: dict[str, str] = field(default_factory=dict)
    validate: bool = True


@dataclass(frozen=True)
class CreateProjectResult:
    """Result of project creation."""

    destination: Path
    validation_result: ValidationResult | None = None


@dataclass(frozen=True)
class CreateProjectError:
    """Error during project creation."""

    message: str
    validation_result: ValidationResult | None = None


class CreateProjectUseCase:
    """Use case: Create a new project from a copier template."""

    def execute(
        self, command: CreateProjectCommand
    ) -> Result[CreateProjectResult, CreateProjectError]:
        """Execute project creation."""
        # Parse template reference
        try:
            template_ref = TemplateReference.from_string(command.template_source)
        except ValueError as e:
            return Err(
                CreateProjectError(message=f"Invalid template source: {e}")
            )

        # Validate if requested
        validation_result: ValidationResult | None = None
        if command.validate:
            validation_result = TemplateValidator.validate_reference(template_ref)

            if not validation_result.is_valid:
                return Err(
                    CreateProjectError(
                        message="Template validation failed",
                        validation_result=validation_result,
                    )
                )

        # Resolve source path
        source = template_ref.location
        if template_ref.source_type == "file":
            source = str(template_ref.resolve_path())

        # Run copier
        try:
            from copier import run_copy

            run_copy(
                src_path=source,
                dst_path=str(command.destination),
                data=command.data if command.data else None,
                unsafe=True,
            )
        except Exception as e:
            return Err(
                CreateProjectError(message=f"Failed to create project: {e}")
            )

        return Ok(
            CreateProjectResult(
                destination=command.destination,
                validation_result=validation_result,
            )
        )
