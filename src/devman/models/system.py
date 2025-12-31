# src/devman/models/system.py
"""System configuration models for llm-core."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field, computed_field

DEFAULT_SYSTEM_CONFIG_PATH = (
    Path.home() / ".config" / "llm-core" / "system.toml"
)


def _expand_paths(values: Iterable[Path]) -> list[Path]:
    return [value.expanduser() for value in values]


class SystemConfig(BaseModel):
    """Configuration persisted for llm-core system settings."""

    model_config = ConfigDict(extra="ignore")

    roots: list[Path] = Field(default_factory=list, description="Workspace roots")
    config_path: Path = Field(default=DEFAULT_SYSTEM_CONFIG_PATH, exclude=True)

    @computed_field
    @property
    def resolved_roots(self) -> list[Path]:
        """Roots with user/home expansion applied."""
        return _expand_paths(self.roots)

    @computed_field
    @property
    def config_dir(self) -> Path:
        """Directory containing the system config file."""
        return self.config_path.parent

    @computed_field
    @property
    def cache_dir(self) -> Path:
        """Default cache directory for llm-core."""
        return Path.home() / ".cache" / "llm-core"

    @computed_field
    @property
    def index_cache_path(self) -> Path:
        """Default index cache path."""
        return self.cache_dir / "index.json"

    @classmethod
    def load(cls, path: Path | None = None) -> "SystemConfig":
        """Load system configuration from TOML."""
        config_path = path or DEFAULT_SYSTEM_CONFIG_PATH
        data: dict[str, object] = {}
        if config_path.exists():
            import tomllib

            payload = tomllib.loads(config_path.read_text())
            if isinstance(payload.get("system"), dict):
                data = dict(payload["system"])
            else:
                data = payload
        return cls.model_validate({"config_path": config_path, **data})

    def save(self, path: Path | None = None) -> None:
        """Save system configuration to TOML."""
        config_path = path or self.config_path
        config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"roots": [str(root) for root in self.roots]}
        toml = _dump_system_toml(data)
        config_path.write_text(toml)


def _dump_system_toml(data: dict[str, object]) -> str:
    lines = ["[system]"]
    for key, value in data.items():
        if isinstance(value, list):
            items = ", ".join(_format_string(item) for item in value)
            lines.append(f"{key} = [{items}]")
        elif isinstance(value, bool):
            lines.append(f"{key} = {str(value).lower()}")
        else:
            lines.append(f"{key} = {_format_string(value)}")
    lines.append("")
    return "\n".join(lines)


def _format_string(value: object) -> str:
    escaped = str(value).replace("\\", "\\\\").replace('"', "\\\"")
    return f'"{escaped}"'
