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
        "src/modules/core/README.md",
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

    matched = find_matching_pattern("src/modules/core/draft-notes.md", "added", patterns)

    assert matched is None


def test_find_matching_pattern_supports_directory_style_patterns() -> None:
    patterns = [
        PatternConfig(
            pattern="src/modules/*/",
            template="module-template",
            on=["added"],
        )
    ]

    matched = find_matching_pattern("src/modules/core/new-file.py", "added", patterns)

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

def test_run_once_treats_enum_and_string_changes_identically() -> None:
    config = DevmanWatchConfig.model_validate(
        {
            "pattern": [
                {
                    "pattern": "src/modules/*/README.md",
                    "template": "module-template",
                    "on": ["added"],
                }
            ],
        }
    )

    enum_seen: list[tuple[str, str]] = []
    string_seen: list[tuple[str, str]] = []

    def enum_handler(pattern: PatternConfig, matched_path: Path, change: str, *_: object) -> None:
        enum_seen.append((pattern.template, f"{change}:{matched_path.as_posix()}"))

    def string_handler(pattern: PatternConfig, matched_path: Path, change: str, *_: object) -> None:
        string_seen.append((pattern.template, f"{change}:{matched_path.as_posix()}"))

    enum_watcher = DevmanWatcher(
        config=config,
        repo_root=Path('.'),
        handlers=[enum_handler],
    )
    string_watcher = DevmanWatcher(
        config=config,
        repo_root=Path('.'),
        handlers=[string_handler],
    )

    enum_dispatches = enum_watcher.run_once({(Change.added, Path('src/modules/core/README.md'))})
    string_dispatches = string_watcher.run_once({('added', 'src/modules/core/README.md')})

    assert enum_dispatches == string_dispatches == 1
    assert enum_seen == string_seen == [('module-template', 'added:src/modules/core/README.md')]


def test_run_and_run_once_share_change_normalization_logic() -> None:
    config = DevmanWatchConfig.model_validate(
        {
            "pattern": [
                {
                    "pattern": "src/modules/*/README.md",
                    "template": "module-template",
                    "on": ["added"],
                }
            ],
        }
    )

    run_seen: list[tuple[str, str]] = []
    run_once_seen: list[tuple[str, str]] = []

    def run_handler(pattern: PatternConfig, matched_path: Path, change: str, *_: object) -> None:
        run_seen.append((pattern.template, f"{change}:{matched_path.as_posix()}"))

    def run_once_handler(pattern: PatternConfig, matched_path: Path, change: str, *_: object) -> None:
        run_once_seen.append((pattern.template, f"{change}:{matched_path.as_posix()}"))

    def watch_factory(*_: object, **__: object):
        yield {(Change.added, 'src/modules/core/README.md')}

    run_watcher = DevmanWatcher(
        config=config,
        repo_root=Path('.'),
        handlers=[run_handler],
        watch_factory=watch_factory,
    )
    run_once_watcher = DevmanWatcher(
        config=config,
        repo_root=Path('.'),
        handlers=[run_once_handler],
    )

    run_watcher.run()
    run_once_dispatches = run_once_watcher.run_once({(' ADDED ', Path('src/modules/core/README.md'))})

    assert run_once_dispatches == 1
    assert run_seen == run_once_seen == [('module-template', 'added:src/modules/core/README.md')]


def test_run_once_matches_relative_patterns_for_absolute_incoming_paths(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    changed_file = repo_root / "src" / "modules" / "core" / "README.md"
    changed_file.parent.mkdir(parents=True)
    changed_file.write_text("docs")

    config = DevmanWatchConfig.model_validate(
        {
            "pattern": [
                {
                    "pattern": "src/modules/*/README.md",
                    "template": "module-template",
                    "on": ["added"],
                }
            ],
        }
    )

    seen: list[str] = []

    def handler(_: PatternConfig, matched_path: Path, change: str, *__: object) -> None:
        seen.append(f"{change}:{matched_path.as_posix()}")

    watcher = DevmanWatcher(config=config, repo_root=repo_root, handlers=[handler])

    dispatches = watcher.run_once({(Change.added, changed_file)})

    assert dispatches == 1
    assert seen == [f"added:{changed_file.as_posix()}"]


def test_run_once_skips_absolute_paths_outside_repo_root(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    outside_file = tmp_path / "outside" / "src" / "modules" / "core" / "README.md"
    outside_file.parent.mkdir(parents=True)
    outside_file.write_text("docs")

    config = DevmanWatchConfig.model_validate(
        {
            "pattern": [
                {
                    "pattern": "src/modules/*/README.md",
                    "template": "module-template",
                    "on": ["added"],
                }
            ],
        }
    )

    seen: list[str] = []

    def handler(_: PatternConfig, matched_path: Path, change: str, *__: object) -> None:
        seen.append(f"{change}:{matched_path.as_posix()}")

    watcher = DevmanWatcher(config=config, repo_root=repo_root, handlers=[handler])

    dispatches = watcher.run_once({(Change.added, outside_file)})

    assert dispatches == 0
    assert seen == []
