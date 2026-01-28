from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


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
