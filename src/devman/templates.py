# src/devman/templates.py
from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from devman.schemas import CopierConfig


TemplateSource = Literal["file", "git"]


class TemplateReference(BaseModel):
    """Represents a reference to a copier template."""

    source_type: TemplateSource
    location: str

    @field_validator("location")
    @classmethod
    def validate_location(cls, v: str, info) -> str:
        source_type = info.data.get("source_type")

        if source_type == "file":
            path = Path(v).expanduser()
            if not path.exists():
                raise ValueError(f"Template path does not exist: {v}")
            if not path.is_dir():
                raise ValueError(f"Template path is not a directory: {v}")

        elif source_type == "git":
            # Basic git URL validation
            git_patterns = [
                r"^https?://",
                r"^git@",
                r"^git://",
                r"^gh:",
                r"^gl:",
            ]
            if not any(re.match(p, v) for p in git_patterns):
                raise ValueError(f"Invalid git URL format: {v}")

        return v

    @classmethod
    def from_string(cls, source: str) -> TemplateReference:
        """Parse a template source string into a TemplateReference."""
        source = source.strip()

        # Check for git-like URLs
        if any(source.startswith(prefix) for prefix in ["http://", "https://", "git@", "git://", "gh:", "gl:"]):
            return cls(source_type="git", location=source)

        # Default to file path
        return cls(source_type="file", location=source)

    def resolve_path(self) -> Path:
        """Resolve the template to a local filesystem path."""
        if self.source_type == "file":
            return Path(self.location).expanduser().resolve()

        # For git sources, copier handles cloning
        # Return location as-is for copier to handle
        raise NotImplementedError("Git resolution handled by copier directly")


class TemplateValidator:
    """Validates copier templates."""

    @staticmethod
    def validate_structure(template_path: Path) -> dict[str, list[str]]:
        """Check template directory structure for common issues."""
        issues = {
            "errors": [],
            "warnings": [],
        }

        # Check for copier.yaml or copier.yml
        yaml_files = list(template_path.glob("copier.y*ml"))
        if not yaml_files:
            issues["errors"].append("No copier.yaml or copier.yml found")
            return issues

        if len(yaml_files) > 1:
            issues["warnings"].append("Multiple copier.yaml files found")

        # Try to parse the config
        try:
            config = CopierConfig.from_yaml_file(yaml_files[0])
            validation_errors = config.validate_questions()

            if validation_errors:
                for name, error in validation_errors.items():
                    issues["errors"].append(f"Question '{name}': {error}")

        except Exception as e:
            issues["errors"].append(f"Failed to parse copier.yaml: {e}")

        return issues

    @staticmethod
    def validate(reference: TemplateReference) -> dict[str, list[str]]:
        """Validate a template reference."""
        if reference.source_type == "file":
            return TemplateValidator.validate_structure(reference.resolve_path())

        # Git sources can't be validated without cloning
        return {"errors": [], "warnings": ["Git sources not validated until use"]}
