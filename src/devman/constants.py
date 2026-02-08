# src/devman/constants.py
"""Module-level constants for devman path layout."""

from pathlib import Path

STORE_ROOT_NAME = ".devman-store"
STORE_ROOT_USER_PATH = f"~/{STORE_ROOT_NAME}"
DEVMAN_META_DIR_NAME = "devman"
DEVMAN_CONFIG_DIR_NAME = ".devman"
TEMPLATES_DIR_NAME = ".templates"
WORKFLOWS_DIR_NAME = "workflows"
CONFIG_FILE_NAME = "config.toml"
INSTANCES_DIR_NAME = "instances"

DEVMAN_CONFIG_SUBPATH = Path(DEVMAN_CONFIG_DIR_NAME)
TEMPLATES_SUBPATH = DEVMAN_CONFIG_SUBPATH / TEMPLATES_DIR_NAME
WORKFLOWS_SUBPATH = DEVMAN_CONFIG_SUBPATH / WORKFLOWS_DIR_NAME
CONFIG_SUBPATH = DEVMAN_CONFIG_SUBPATH / CONFIG_FILE_NAME

DEFAULT_INSTANCE_STORE = f"{STORE_ROOT_USER_PATH}/{INSTANCES_DIR_NAME}"
DEFAULT_TEMPLATE_STORE = (
    f"{STORE_ROOT_USER_PATH}/{DEVMAN_META_DIR_NAME}/"
    f"{DEVMAN_CONFIG_DIR_NAME}/{TEMPLATES_DIR_NAME}"
)


def get_store_root() -> Path:
    return Path.home() / STORE_ROOT_NAME


def get_devman_meta_dir() -> Path:
    return get_store_root() / DEVMAN_META_DIR_NAME


def get_templates_dir() -> Path:
    return get_devman_meta_dir() / TEMPLATES_SUBPATH


def get_workflows_dir() -> Path:
    return get_devman_meta_dir() / WORKFLOWS_SUBPATH


def get_config_file() -> Path:
    return get_devman_meta_dir() / CONFIG_SUBPATH


WATCH_CONFIG_NAME = "devman-watch.toml"
