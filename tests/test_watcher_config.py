from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from devman.constants import DEFAULT_INSTANCE_STORE, DEFAULT_TEMPLATE_STORE
from devman.watcher.config import DevmanWatchConfig
import devman.watcher.config as watcher_config


def test_config_uses_stdlib_tomllib() -> None:
    assert watcher_config.tomllib.__name__ == "tomllib"


def test_from_toml_file_loads_valid_config_and_normalizes_values(tmp_path: Path) -> None:
    config_path = tmp_path / "watch.toml"
    config_path.write_text(
        """[[pattern]]
name = "  module docs  "
pattern = "src/modules/*/README.md"
template = " docs-template "
on = [" Added ", "MODIFIED"]
exclude = ["**/draft-*", "**/*.tmp"]

[settings]
log_level = " debug "
""",
        encoding="utf-8",
    )

    config = DevmanWatchConfig.from_toml_file(config_path)

    assert len(config.patterns) == 1
    assert config.patterns[0].name == "module docs"
    assert config.patterns[0].template == "docs-template"
    assert config.patterns[0].on == ["added", "modified"]
    assert config.settings.log_level == "DEBUG"


def test_model_defaults_are_applied_when_sections_are_missing() -> None:
    config = DevmanWatchConfig.model_validate({})

    assert config.patterns == []
    assert config.settings.debounce_ms == 500
    assert config.settings.log_level == "INFO"
    assert config.settings.allow_destructive_modified is False
    assert ".git" in config.settings.ignore_dirs
    assert "**/*.pyc" in config.settings.ignore_globs
    assert config.settings.instance_store == DEFAULT_INSTANCE_STORE
    assert config.settings.template_store == DEFAULT_TEMPLATE_STORE


@pytest.mark.parametrize(
    ("payload", "expected_message"),
    [
        (
            {
                "pattern": [
                    {
                        "pattern": "src/modules/*",
                        "template": "module-template",
                        "on": [],
                    }
                ]
            },
            "on must include at least one event",
        ),
        (
            {
                "pattern": [
                    {
                        "pattern": "src/modules/*",
                        "template": "module-template",
                        "on": ["renamed"],
                    }
                ]
            },
            "invalid event",
        ),
        (
            {
                "settings": {
                    "log_level": "verbose",
                }
            },
            "invalid log level",
        ),
        (
            {
                "pattern": [
                    {
                        "pattern": "src/modules/*",
                        "template": "   ",
                    }
                ]
            },
            "value must not be empty",
        ),
    ],
)
def test_invalid_configs_raise_validation_error(payload: dict[str, object], expected_message: str) -> None:
    with pytest.raises(ValidationError, match=expected_message):
        DevmanWatchConfig.model_validate(payload)


def test_to_toml_file_round_trip_preserves_pattern_alias_shape(tmp_path: Path) -> None:
    config = DevmanWatchConfig.model_validate(
        {
            "pattern": [
                {
                    "name": "python module",
                    "pattern": "src/modules/*/",
                    "template": "python-module",
                    "on": ["added", "modified"],
                    "exclude": ["**/draft-*", "**/*.tmp"],
                }
            ],
            "settings": {
                "debounce_ms": 250,
                "log_level": "warning",
            },
        }
    )
    output_path = tmp_path / "nested" / "watch.toml"

    config.to_toml_file(output_path)

    raw_text = output_path.read_text(encoding="utf-8")
    assert "[[pattern]]" in raw_text
    assert "[[patterns]]" not in raw_text

    loaded = DevmanWatchConfig.from_toml_file(output_path)
    assert loaded == config


def test_get_template_for_pattern_reuses_runtime_matching_rules() -> None:
    config = DevmanWatchConfig.model_validate(
        {
            "pattern": [
                {
                    "pattern": "src/modules/*/",
                    "template": "python-module",
                    "on": ["added"],
                    "exclude": ["**/draft-*", "**/*.tmp"],
                }
            ]
        }
    )

    assert (
        config.get_template_for_pattern(Path("src/modules/api/README.md"), "added")
        == "python-module"
    )
    assert config.get_template_for_pattern(Path("src/modules/api/README.md"), "modified") is None
    assert config.get_template_for_pattern(Path("src/modules/draft-alpha/README.md"), "added") is None
    assert config.get_template_for_pattern(Path("src/modules/api/file.tmp"), "added") is None
