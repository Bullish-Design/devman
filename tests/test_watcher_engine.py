from pathlib import Path

from devman.watcher.config import DevmanWatchConfig, PatternConfig
from devman.watcher.engine import Change, DevmanWatcher, find_matching_pattern
import devman.watcher.engine as watcher_engine


def test_engine_uses_watchfiles_change_enum() -> None:
    assert watcher_engine.Change.__module__.startswith("watchfiles")


def test_find_matching_pattern_matches_on_change_and_glob() -> None:
    patterns = [
        PatternConfig(
            name="module",
            pattern="src/modules/*/README.md",
            template="module-template",
            on=["added", "modified"],
        )
    ]

    matched = find_matching_pattern(
        Path("src/modules/core/README.md"),
        Change.modified,
        patterns,
    )

    assert matched is not None
    assert matched.template == "module-template"


def test_find_matching_pattern_respects_excludes() -> None:
    patterns = [
        PatternConfig(
            pattern="src/modules/**/*.md",
            template="module-template",
            exclude=["src/modules/**/draft-*"],
        )
    ]

    matched = find_matching_pattern(Path("src/modules/core/draft-notes.md"), "added", patterns)

    assert matched is None


def test_find_matching_pattern_supports_directory_style_patterns() -> None:
    patterns = [
        PatternConfig(
            pattern="src/modules/*/",
            template="module-template",
            on=["added"],
        )
    ]

    matched = find_matching_pattern(Path("src/modules/core/new-file.py"), "added", patterns)

    assert matched is not None


def test_run_once_applies_ignore_filters_and_dispatches_handlers() -> None:
    config = DevmanWatchConfig.model_validate(
        {
            "pattern": [
                {
                    "pattern": "src/modules/*/README.md",
                    "template": "module-template",
                    "on": ["added"],
                }
            ],
            "settings": {
                "ignore_dirs": [".git", "build"],
                "ignore_globs": ["**/*.tmp"],
            },
        }
    )

    seen: list[tuple[str, str]] = []

    def recording_handler(pattern: PatternConfig, matched_path: Path, change: str, *_: object) -> None:
        seen.append((pattern.template, f"{change}:{matched_path.as_posix()}"))

    watcher = DevmanWatcher(
        config=config,
        repo_root=Path("."),
        handlers=[recording_handler],
    )

    dispatches = watcher.run_once(
        {
            (Change.added, "src/modules/core/README.md"),
            (Change.added, "build/output/README.md"),
            (Change.added, "src/modules/core/temp.tmp"),
            (Change.modified, "src/modules/core/README.md"),
        }
    )

    assert dispatches == 1
    assert seen == [("module-template", "added:src/modules/core/README.md")]


def test_run_once_dispatches_all_handlers_and_skips_failed_handler() -> None:
    config = DevmanWatchConfig.model_validate(
        {
            "pattern": [{"pattern": "src/modules/*", "template": "module-template", "on": ["added"]}],
        }
    )

    calls: list[str] = []

    def ok_handler(*_: object) -> None:
        calls.append("ok")

    def failing_handler(*_: object) -> None:
        calls.append("fail")
        raise RuntimeError("boom")

    watcher = DevmanWatcher(
        config=config,
        repo_root=Path("."),
        handlers=[ok_handler, failing_handler, ok_handler],
    )

    dispatches = watcher.run_once({("added", "src/modules/auth")})

    assert dispatches == 2
    assert calls == ["ok", "fail", "ok"]
