# src/devman/devman_config.py
"""DevmanConfig for TOML-based project configuration."""

from __future__ import annotations

import tomllib
import tomli_w
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, computed_field

from . import __version__
from .config import ProjectConfig


class DevmanMetadata(BaseModel):
    """Devman tool metadata."""

    version: str = Field(default=__version__, description="Devman version used")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")


class TemplateConfig(BaseModel):
    """Template configuration and references."""

    files: list[str] = Field(default_factory=list, description="Template files to generate")
    custom_templates_dir: str | None = Field(default=None, description="Custom templates directory")

    def get_default_files(self, project_type: str, container_type: str) -> list[str]:
        """Get default template files for project configuration."""
        files = ["devenv.nix.j2", "justfile.j2", "pyproject.toml.j2", ".envrc.j2"]

        if container_type == "docker":
            files.extend(["Dockerfile.j2", "docker-compose.yml.j2"])
        elif container_type == "nixos":
            files.append("container.nix.j2")

        return files


class GenerationMetadata(BaseModel):
    """Metadata about project generation."""

    last_generated: datetime | None = Field(default=None, description="Last generation timestamp")
    generated_files: list[str] = Field(default_factory=list, description="List of generated files")


class DevmanConfig(BaseModel):
    """Complete devman.toml configuration."""

    devman: DevmanMetadata = Field(default_factory=DevmanMetadata)
    project: ProjectConfig = Field(..., description="Project configuration")
    templates: TemplateConfig = Field(default_factory=TemplateConfig)
    generation: GenerationMetadata = Field(default_factory=GenerationMetadata)

    @computed_field
    @property
    def devman_dir(self) -> Path:
        """Path to .devman directory."""
        return Path.cwd() / ".devman"

    @computed_field
    @property
    def config_file(self) -> Path:
        """Path to devman.toml file."""
        return self.devman_dir / "devman.toml"

    def ensure_templates_list(self) -> None:
        """Ensure templates.files is populated with defaults if empty."""
        if not self.templates.files:
            self.templates.files = self.templates.get_default_files(self.project.project_type, self.project.container_type)

    def update_metadata(self) -> None:
        """Update timestamps."""
        self.devman.updated_at = datetime.now()

    def mark_generated(self, generated_files: list[str]) -> None:
        """Mark files as generated."""
        self.generation.last_generated = datetime.now()
        self.generation.generated_files = generated_files
        self.update_metadata()

    def to_toml(self) -> str:
        """Serialize to TOML string."""
        # Convert to dict and handle datetime serialization
        data = self.model_dump(mode="json", exclude_none=True)
        return tomli_w.dumps(data)

    @classmethod
    def from_toml(cls, toml_content: str) -> DevmanConfig:
        """Create from TOML string."""
        data = tomllib.loads(toml_content)
        return cls.model_validate(data)

    @classmethod
    def from_file(cls, config_path: Path | str) -> DevmanConfig:
        """Load from TOML file."""
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        return cls.model_validate(data)

    def save(self, config_path: Path | str | None = None) -> None:
        """Save to TOML file."""
        if config_path is None:
            config_path = self.config_file

        config_path = Path(config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w") as f:
            f.write(self.to_toml())

    @classmethod
    def create_from_project_config(cls, project_config: ProjectConfig) -> DevmanConfig:
        """Create DevmanConfig from existing ProjectConfig."""
        config = cls(project=project_config)
        config.ensure_templates_list()
        return config

    def get_template_context(self) -> dict[str, Any]:
        """Get template context for rendering."""
        return self.project.get_template_context()
