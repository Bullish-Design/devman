"""Utilities for generating starter watcher TOML configurations."""

from __future__ import annotations

from pathlib import Path

from devman.constants import DEFAULT_INSTANCE_STORE, DEFAULT_TEMPLATE_STORE

_STARTER_CONFIG = f"""[[pattern]]
name = "python-module"
pattern = "src/modules/*/"
template = "python-module"
on = ["added"]
exclude = ["**/draft-*", "**/*.tmp"]

[settings]
debounce_ms = 500
log_level = "INFO"
ignore_dirs = [".git", ".venv", "__pycache__", "node_modules"]
ignore_globs = ["**/*.pyc", "**/.DS_Store"]
instance_store = "{DEFAULT_INSTANCE_STORE}"
template_store = "{DEFAULT_TEMPLATE_STORE}"
allow_destructive_modified = false
"""


def generate_starter_config(output_path: Path, overwrite: bool = False) -> None:
    """Write a deterministic starter watcher config.

    The function will create parent directories when needed. By default it
    refuses to overwrite existing files and raises ``FileExistsError`` when
    ``output_path`` already exists. Set ``overwrite=True`` to replace an
    existing file.
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if overwrite else "x"
    with output_path.open(mode, encoding="utf-8") as file_handle:
        file_handle.write(_STARTER_CONFIG)
