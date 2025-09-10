# src/devman/config.py
from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, Optional

import yaml
from pydantic import BaseModel, Field

from .exceptions import ConfigurationError
from .security import SecurityConfig


class UserConfig(BaseModel):
    """User configuration settings with security defaults."""

    default_python_version: str = "3.11"
    default_template: str = "python-lib"
    author_name: str = "Your Name"
    author_email: str = "you@example.com"
    use_nix: bool = True
    use_docker: bool = True
    use_just: bool = True
    template_sources: Dict[str, str] = Field(default_factory=dict)
    cache_enabled: bool = True
    quiet_mode: bool = False

    # Security defaults
    security_enabled: bool = True
    pre_commit_hooks: bool = True
    dependency_scanning: bool = True
    secret_detection: bool = True
    security_linting: bool = True

    @classmethod
    def get_config_paths(cls) -> list[Path]:
        """Get possible configuration file locations in order of precedence."""
        paths = []

        # 1. Environment variable override
        if env_path := os.getenv("DEVMAN_CONFIG"):
            paths.append(Path(env_path))

        # 2. Current directory (project-specific)
        paths.append(Path.cwd() / ".devman.yml")

        # 3. User config directory (XDG Base Directory)
        if xdg_config := os.getenv("XDG_CONFIG_HOME"):
            paths.append(Path(xdg_config) / "devman" / "config.yml")
        else:
            paths.append(Path.home() / ".config" / "devman" / "config.yml")

        # 4. Home directory fallback
        paths.append(Path.home() / ".devman.yml")

        return paths

    @classmethod
    def load(cls) -> UserConfig:
        """Load config from standard locations."""
        for config_path in cls.get_config_paths():
            if config_path.exists():
                try:
                    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
                    if data is None:
                        continue  # Empty file
                    return cls.model_validate(data)
                except yaml.YAMLError as e:
                    raise ConfigurationError(f"Invalid YAML in config file {config_path}: {e}") from e
                except Exception as e:
                    raise ConfigurationError(f"Error reading config file {config_path}: {e}") from e

        # No config found, return defaults
        return cls()

    def save(self, path: Optional[Path] = None) -> Path:
        """Save config to file."""
        if path is None:
            # Use the default user config location
            config_paths = self.get_config_paths()
            # Skip environment variable and current directory, use user config
            path = config_paths[2] if len(config_paths) > 2 else config_paths[-1]

        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Create a clean dict for serialization
            config_data = self.model_dump()

            # Write with nice formatting
            yaml_content = yaml.dump(config_data, default_flow_style=False, sort_keys=True, indent=2)

            path.write_text(yaml_content, encoding="utf-8")
            return path

        except Exception as e:
            raise ConfigurationError(f"Failed to save config to {path}: {e}") from e

    def get_effective_config_path(self) -> Optional[Path]:
        """Get the path of the config file that would be loaded."""
        for config_path in self.get_config_paths():
            if config_path.exists():
                return config_path
        return None

    def update_setting(self, key: str, value: str) -> None:
        """Update a single configuration setting."""
        if not hasattr(self, key):
            available_keys = list(self.__class__.model_fields.keys())
            raise ConfigurationError(f"Unknown config key '{key}'. Available keys: {', '.join(available_keys)}")

        field_info = self.__class__.model_fields[key]
        field_type = field_info.annotation

        # Convert string value to appropriate type
        try:
            if field_type == bool:
                # Handle boolean conversion
                if value.lower() in ("true", "yes", "1", "on"):
                    converted_value = True
                elif value.lower() in ("false", "no", "0", "off"):
                    converted_value = False
                else:
                    raise ValueError(f"Invalid boolean value: {value}")
            elif field_type == int:
                converted_value = int(value)
            elif field_type == float:
                converted_value = float(value)
            else:
                # String or other types
                converted_value = value

            setattr(self, key, converted_value)

        except ValueError as e:
            raise ConfigurationError(f"Invalid value '{value}' for config key '{key}': {e}") from e

    def get_security_config(self) -> SecurityConfig:
        """Get SecurityConfig based on user preferences."""
        return SecurityConfig(
            enable_pre_commit=self.pre_commit_hooks and self.security_enabled,
            enable_dependency_scan=self.dependency_scanning and self.security_enabled,
            enable_secret_detection=self.secret_detection and self.security_enabled,
            enable_security_linting=self.security_linting and self.security_enabled,
            enable_vulnerability_scan=self.dependency_scanning and self.security_enabled,
            bandit_enabled=self.security_linting and self.security_enabled,
            safety_enabled=self.dependency_scanning and self.security_enabled,
        )


class ConfigManager:
    """Manages configuration operations."""

    @staticmethod
    def initialize_config(path: Optional[Path] = None, overwrite: bool = False) -> Path:
        """Initialize a new configuration file with security defaults."""
        config = UserConfig()

        if path is None:
            # Use default user config location
            config_paths = UserConfig.get_config_paths()
            path = config_paths[2] if len(config_paths) > 2 else config_paths[-1]

        if path.exists() and not overwrite:
            raise ConfigurationError(f"Config file already exists: {path}")

        return config.save(path)

    @staticmethod
    def show_config_info() -> dict:
        """Show information about current configuration."""
        config = UserConfig.load()
        effective_path = config.get_effective_config_path()

        return {
            "config": config.model_dump(),
            "config_file": str(effective_path) if effective_path else "None (using defaults)",
            "search_paths": [str(p) for p in UserConfig.get_config_paths()],
        }
