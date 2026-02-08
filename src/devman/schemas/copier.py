# src/devman/schemas/copier.py
from __future__ import annotations

import yaml
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from devman.schemas.questions import (
    BaseQuestion,
    ChoiceQuestion,
    parse_question,
)
from devman.domain.models import ValidationResult


class CopierConfig(BaseModel):
    """Root configuration model for copier.yaml files."""

    # Copier metadata fields (prefixed with _)
    subdirectory: str | None = Field(None, alias="_subdirectory")
    templates_suffix: str | None = Field(None, alias="_templates_suffix")
    skip_if_exists: list[str] = Field(default_factory=list, alias="_skip_if_exists")
    tasks: list[str | dict[str, Any]] = Field(default_factory=list, alias="_tasks")
    migrations: list[dict[str, Any]] = Field(default_factory=list, alias="_migrations")
    jinja_extensions: list[str] = Field(default_factory=list, alias="_jinja_extensions")

    # Question fields - accepts both raw dicts and typed Question objects
    questions: dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "populate_by_name": True,
        "extra": "allow",
    }

    @classmethod
    def from_yaml_file(cls, path: Path) -> CopierConfig:
        """Load and parse a copier.yaml file."""
        content = yaml.safe_load(path.read_text())
        if content is None:
            content = {}
        elif not isinstance(content, dict):
            raise ValueError(
                f"Invalid YAML root in {path}: expected a mapping, got {type(content).__name__}"
            )

        # Separate metadata fields from questions
        questions_raw: dict[str, Any] = {}
        metadata: dict[str, Any] = {}

        for key, value in content.items():
            if key.startswith("_"):
                metadata[key] = value
            else:
                questions_raw[key] = value

        # Parse questions into typed objects where possible
        questions_typed: dict[str, Any] = {}
        for name, spec in questions_raw.items():
            if isinstance(spec, dict):
                try:
                    questions_typed[name] = parse_question(name, spec)
                except Exception:
                    # Keep as raw dict if parsing fails
                    questions_typed[name] = spec
            else:
                questions_typed[name] = spec

        metadata["questions"] = questions_typed
        return cls(**metadata)

    def to_yaml_file(self, path: Path) -> None:
        """Write configuration to copier.yaml format."""
        output: dict[str, Any] = {}

        # Add metadata fields
        if self.subdirectory:
            output["_subdirectory"] = self.subdirectory
        if self.templates_suffix:
            output["_templates_suffix"] = self.templates_suffix
        if self.skip_if_exists:
            output["_skip_if_exists"] = self.skip_if_exists
        if self.tasks:
            output["_tasks"] = self.tasks
        if self.migrations:
            output["_migrations"] = self.migrations
        if self.jinja_extensions:
            output["_jinja_extensions"] = self.jinja_extensions

        # Add questions - convert typed objects back to dict format
        for name, question in self.questions.items():
            if isinstance(question, BaseQuestion):
                output[name] = question.model_dump(
                    exclude_none=True, exclude_unset=True, by_alias=False
                )
            else:
                output[name] = question

        path.write_text(yaml.dump(output, sort_keys=False))

    def validate_questions(self) -> ValidationResult:
        """Validate question structures with detailed error tracking."""
        result = ValidationResult()

        for name, spec in self.questions.items():
            if isinstance(spec, BaseQuestion):
                # Already parsed - apply business rules
                if isinstance(spec, ChoiceQuestion) and not spec.choices:
                    result.add_warning(
                        "Choice question has no choices defined",
                        location=name,
                        code="EMPTY_CHOICES",
                    )
            elif isinstance(spec, dict):
                # Raw dict - validate structure
                if "type" not in spec:
                    result.add_error(
                        "Question missing 'type' field",
                        location=name,
                        code="MISSING_TYPE",
                    )
            else:
                result.add_error(
                    "Question must be a dictionary",
                    location=name,
                    code="INVALID_FORMAT",
                )

        return result
