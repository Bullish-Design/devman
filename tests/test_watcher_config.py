from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from devman.watcher.config import DevmanWatchConfig


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
    assert ".git" in config.settings.ignore_dirs
    assert "**/*.pyc" in config.settings.ignore_globs


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
