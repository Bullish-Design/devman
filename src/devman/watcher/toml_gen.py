"""Utilities for generating starter watcher TOML configurations."""

from __future__ import annotations

from pathlib import Path

_STARTER_CONFIG = """[[pattern]]
name = "python-module"
pattern = "src/modules/*/"
template = "python-module"
on = ["added", "modified"]
exclude = ["**/draft-*", "**/*.tmp"]

[settings]
debounce_ms = 500
log_level = "INFO"
ignore_dirs = [".git", ".venv", "__pycache__", "node_modules"]
ignore_globs = ["**/*.pyc", "**/.DS_Store"]
instance_store = "~/.devman-store/instances"
template_store = "~/.devman-store/devman/.devman/.templates"
"""


def generate_starter_config(output_path: Path) -> None:
    """Write a deterministic starter watcher config.

    The function will create parent directories when needed and refuses to
    overwrite existing files, raising ``FileExistsError`` when ``output_path``
    already exists.
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as file_handle:
        file_handle.write(_STARTER_CONFIG)
