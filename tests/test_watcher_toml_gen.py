from __future__ import annotations

from pathlib import Path

import pytest

from devman.constants import DEFAULT_INSTANCE_STORE, DEFAULT_TEMPLATE_STORE
from devman.watcher.config import DevmanWatchConfig
from devman.watcher.toml_gen import generate_starter_config


def test_generate_starter_config_writes_valid_deterministic_toml(tmp_path: Path) -> None:
    output_path = tmp_path / "watch.toml"

    generate_starter_config(output_path)

    generated = output_path.read_text(encoding="utf-8")
    expected = """[[pattern]]
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
    assert generated == expected

    config = DevmanWatchConfig.from_toml_file(output_path)
    assert len(config.patterns) == 1
    assert config.patterns[0].name == "python-module"
    assert config.settings.debounce_ms == 500


def test_generate_starter_config_refuses_to_overwrite(tmp_path: Path) -> None:
    output_path = tmp_path / "nested" / "watch.toml"
    output_path.parent.mkdir(parents=True)
    output_path.write_text("[settings]\ndebounce_ms = 123\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        generate_starter_config(output_path)


def test_generate_starter_config_overwrites_when_enabled(tmp_path: Path) -> None:
    output_path = tmp_path / "watch.toml"
    output_path.write_text("[settings]\ndebounce_ms = 123\n", encoding="utf-8")

    generate_starter_config(output_path, overwrite=True)

    generated = output_path.read_text(encoding="utf-8")
    assert 'name = "python-module"' in generated
    assert 'debounce_ms = 500' in generated
