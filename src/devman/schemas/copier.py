# src/devman/schemas/copier.py
from __future__ import annotations

import yaml
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from devman.schemas.questions import (
    StrQuestion,
    BoolQuestion,
    ChoiceQuestion,
    IntQuestion,
    FloatQuestion,
    YamlQuestion,
    JsonQuestion,
)
from devman.schemas.tasks import TaskList


class CopierConfig(BaseModel):
    """Root configuration model for copier.yaml files."""

    # Copier metadata fields (prefixed with _)
    subdirectory: str | None = Field(None, alias="_subdirectory")
    templates_suffix: str | None = Field(None, alias="_templates_suffix")
    skip_if_exists: list[str] = Field(default_factory=list, alias="_skip_if_exists")
    tasks: list[str | dict[str, Any]] = Field(default_factory=list, alias="_tasks")
    migrations: list[dict[str, Any]] = Field(default_factory=list, alias="_migrations")
    jinja_extensions: list[str] = Field(default_factory=list, alias="_jinja_extensions")

    # Question fields (dynamic)
    questions: dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "populate_by_name": True,
        "extra": "allow",  # Allow extra fields for custom questions
    }

    @classmethod
    def from_yaml_file(cls, path: Path) -> CopierConfig:
        """Load and parse a copier.yaml file."""
        content = yaml.safe_load(path.read_text())

        # Separate metadata fields from questions
        questions = {}
        metadata = {}

        for key, value in content.items():
            if key.startswith("_"):
                metadata[key] = value
            else:
                questions[key] = value

        metadata["questions"] = questions
        return cls(**metadata)

    def to_yaml_file(self, path: Path) -> None:
        """Write configuration to copier.yaml format."""
        output = {}

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

        # Add questions
        output.update(self.questions)

        path.write_text(yaml.dump(output, sort_keys=False))

    def validate_questions(self) -> dict[str, str]:
        """Validate question structures and return any errors."""
        errors = {}

        for name, spec in self.questions.items():
            if not isinstance(spec, dict):
                errors[name] = "Question must be a dictionary"
                continue

            if "type" not in spec:
                errors[name] = "Question missing 'type' field"

        return errors
