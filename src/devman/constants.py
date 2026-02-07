# src/devman/constants.py
"""Module-level constants for devman."""

from pathlib import Path

STORE_ROOT = Path.home() / ".devman-store"
DEVMAN_META_DIR = STORE_ROOT / "devman"
TEMPLATES_DIR = DEVMAN_META_DIR / ".devman" / ".templates"
WORKFLOWS_DIR = DEVMAN_META_DIR / ".devman" / "workflows"
CONFIG_FILE = DEVMAN_META_DIR / ".devman" / "config.toml"
WATCH_CONFIG_NAME = "devman-watch.toml"
