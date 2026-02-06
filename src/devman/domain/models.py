# src/devman/domain/models.py
from __future__ import annotations

from pydantic import BaseModel, Field


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
