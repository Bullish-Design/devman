from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from devman.constants import CONFIG_DIR, CONFIG_FILE


class DevmanConfig(BaseSettings):
    projects_root: Path | None = None

    model_config = SettingsConfigDict(
        env_prefix="DEVMAN_",
        env_file="~/.config/devman/config.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def load_config() -> DevmanConfig:
    return DevmanConfig()


class ConfigRepository:
    """Persists devman configuration to disk."""

    def __init__(self) -> None:
        self._config_path = Path(CONFIG_DIR).expanduser() / CONFIG_FILE

    @property
    def config_path(self) -> Path:
        return self._config_path

    def load(self) -> DevmanConfig:
        return load_config()

    def save_projects_root(self, projects_root: Path) -> None:
        """Save projects root to config file."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_root = projects_root.expanduser().resolve()
        self._config_path.write_text(
            f"DEVMAN_PROJECTS_ROOT={resolved_root}\n",
            encoding="utf-8",
        )
