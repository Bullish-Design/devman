"""Pydantic models for devman watcher configuration."""

from __future__ import annotations

from pathlib import Path

import tomllib
from pydantic import BaseModel, Field, field_validator, model_validator

_ALLOWED_EVENTS = {"added", "modified", "deleted"}
_ALLOWED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class PatternConfig(BaseModel):
    """Pattern-to-template mapping for watcher-triggered instantiation."""

    name: str | None = Field(
        default=None,
        description="Optional human-readable name for this pattern rule.",
    )
    pattern: str = Field(description="Glob pattern to match (e.g. 'src/modules/*/').")
    template: str = Field(description="Template name in the devman template store.")
    on: list[str] = Field(
        default_factory=lambda: ["added"],
        description="Event names that trigger this rule.",
    )
    exclude: list[str] = Field(
        default_factory=list,
        description="Glob patterns excluded from matching.",
    )

    @field_validator("name", "pattern", "template")
    @classmethod
    def validate_non_empty_strings(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be empty")
        return stripped

    @field_validator("on", mode="before")
    @classmethod
    def validate_on_not_empty(cls, value: object) -> object:
        if value == []:
            raise ValueError("on must include at least one event")
        return value

    @field_validator("on")
    @classmethod
    def validate_events(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for event in value:
            event_name = event.strip().lower()
            if event_name not in _ALLOWED_EVENTS:
                allowed = ", ".join(sorted(_ALLOWED_EVENTS))
                raise ValueError(f"invalid event '{event}'; must be one of: {allowed}")
            normalized.append(event_name)
        return normalized


class SettingsConfig(BaseModel):
    """Watcher-level runtime settings."""

    debounce_ms: int = Field(default=500, ge=50, le=5000)
    log_level: str = Field(default="INFO")
    ignore_dirs: list[str] = Field(
        default_factory=lambda: [".git", ".venv", "__pycache__", "node_modules"],
    )
    ignore_globs: list[str] = Field(
        default_factory=lambda: ["**/*.pyc", "**/.DS_Store"],
    )
    instance_store: str = Field(default="~/.devman-store/instances")
    template_store: str = Field(default="~/.devman-store/devman/.devman/.templates")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        level = value.strip().upper()
        if level not in _ALLOWED_LOG_LEVELS:
            allowed = ", ".join(sorted(_ALLOWED_LOG_LEVELS))
            raise ValueError(f"invalid log level '{value}'; must be one of: {allowed}")
        return level


class DevmanWatchConfig(BaseModel):
    """Root watch configuration model."""

    patterns: list[PatternConfig] = Field(default_factory=list, alias="pattern")
    settings: SettingsConfig = Field(default_factory=SettingsConfig)

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def validate_required_fields(self) -> DevmanWatchConfig:
        for index, pattern in enumerate(self.patterns):
            if not pattern.pattern:
                raise ValueError(f"pattern[{index}].pattern is required")
            if not pattern.template:
                raise ValueError(f"pattern[{index}].template is required")
        return self

    @classmethod
    def from_toml_file(cls, path: Path) -> DevmanWatchConfig:
        """Load and validate a devman watcher config from TOML."""
        with path.open("rb") as file_handle:
            data = tomllib.load(file_handle)
        return cls.model_validate(data)
