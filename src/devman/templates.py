# src/devman/templates.py
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, model_validator
from result import Err, Ok, Result

from devman.domain.errors import (
    InvalidGitUrlError,
    PathNotDirectoryError,
    PathNotFoundError,
)
from devman.domain.models import ValidationResult
from devman.schemas import CopierConfig


TemplateSource = Literal["file", "git"]


class TemplateReference(BaseModel):
    """Represents a reference to a copier template."""

    source_type: TemplateSource
    location: str

    @model_validator(mode="after")
    def validate_reference(self) -> TemplateReference:
        """Validate template reference after construction."""
        if self.source_type == "file":
            path = Path(self.location).expanduser()
            if not path.exists():
                raise ValueError(f"Template path does not exist: {self.location}")
            if not path.is_dir():
                raise ValueError(f"Template path is not a directory: {self.location}")

        elif self.source_type == "git":
            # Basic git URL validation
            git_patterns = [
                r"^https?://",
                r"^git@",
                r"^git://",
                r"^gh:",
                r"^gl:",
            ]
            if not any(re.match(p, self.location) for p in git_patterns):
                raise ValueError(f"Invalid git URL format: {self.location}")

        return self

    @classmethod
    def create(
        cls, source_type: TemplateSource, location: str
    ) -> Result[
        TemplateReference,
        PathNotFoundError | PathNotDirectoryError | InvalidGitUrlError,
    ]:
        """
        Factory method using Result type for error handling.

        Replaces exception-based validation with Railway-Oriented Programming.
        """
        try:
            return Ok(cls(source_type=source_type, location=location))
        except ValueError as e:
            error_msg = str(e)

            if source_type == "file":
                if "does not exist" in error_msg:
                    return Err(
                        PathNotFoundError(message=error_msg, path=Path(location))
                    )
                else:
                    return Err(
                        PathNotDirectoryError(message=error_msg, path=Path(location))
                    )
            else:  # git
                return Err(InvalidGitUrlError(message=error_msg, url=location))

    @classmethod
    def from_string(cls, source: str) -> TemplateReference:
        """
        Parse a template source string into a TemplateReference.

        Note: This is kept for backward compatibility but raises on error.
        Prefer using create() for Result-based error handling.
        """
        source = source.strip()

        # Check for git-like URLs
        if any(
            source.startswith(prefix)
            for prefix in ["http://", "https://", "git@", "git://", "gh:", "gl:"]
        ):
            return cls(source_type="git", location=source)

        # Default to file path
        return cls(source_type="file", location=source)

    def resolve_path(self) -> Path:
        """Resolve the template to a local filesystem path."""
        if self.source_type == "file":
            return Path(self.location).expanduser().resolve()

        # For git sources, copier handles cloning
        raise NotImplementedError("Git resolution handled by copier directly")


class TemplateValidator:
    """Validates copier templates."""

    @staticmethod
    def validate_structure_typed(template_path: Path) -> ValidationResult:
        """
        Check template directory structure for common issues.

        Returns structured ValidationResult.
        """
        result = ValidationResult()

        # Check for copier.yaml or copier.yml
        yaml_files = list(template_path.glob("copier.y*ml"))
        if not yaml_files:
            result.add_error("No copier.yaml or copier.yml found")
            return result

        if len(yaml_files) > 1:
            result.add_warning("Multiple copier.yaml files found")

        # Try to parse the config
        try:
            config = CopierConfig.from_yaml_file(yaml_files[0])
            validation_result = config.validate_questions_structured()

            # Merge validation results
            result.errors.extend(validation_result.errors)
            result.warnings.extend(validation_result.warnings)

        except Exception as e:
            result.add_error(f"Failed to parse copier.yaml: {e}")

        return result

    @staticmethod
    def validate_structure(template_path: Path) -> dict[str, list[str]]:
        """
        Check template directory structure for common issues.

        Legacy method for backward compatibility.
        Deprecated: Use validate_structure_typed() instead.
        """
        typed_result = TemplateValidator.validate_structure_typed(template_path)

        return {
            "errors": [issue.message for issue in typed_result.errors],
            "warnings": [issue.message for issue in typed_result.warnings],
        }

    @staticmethod
    def validate_typed(reference: TemplateReference) -> ValidationResult:
        """Validate a template reference, returning structured result."""
        if reference.source_type == "file":
            return TemplateValidator.validate_structure_typed(reference.resolve_path())

        # Git sources can't be validated without cloning
        result = ValidationResult()
        result.add_warning("Git sources not validated until use")
        return result

    @staticmethod
    def validate(reference: TemplateReference) -> dict[str, list[str]]:
        """
        Validate a template reference.

        Legacy method for backward compatibility.
        Deprecated: Use validate_typed() instead.
        """
        if reference.source_type == "file":
            return TemplateValidator.validate_structure(reference.resolve_path())

        # Git sources can't be validated without cloning
        return {"errors": [], "warnings": ["Git sources not validated until use"]}
