"""Runtime watch loop and matching engine for devman watcher."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Iterator, Sequence
from fnmatch import fnmatch
from pathlib import Path

from watchfiles import Change, watch

from devman.watcher.config import DevmanWatchConfig, PatternConfig
from devman.watcher.handlers import DEFAULT_HANDLERS, WatcherHandler

logger = logging.getLogger(__name__)


class DevmanWatcher:
    """Filesystem watcher runtime for processing configured pattern matches."""

    def __init__(
        self,
        config: DevmanWatchConfig,
        repo_root: Path,
        handlers: Sequence[WatcherHandler] | None = None,
        watch_factory: Callable[..., Iterator[set[tuple[Change, str]]]] | None = None,
    ) -> None:
        self.config = config
        self.repo_root = repo_root.resolve()
        self.handlers = tuple(handlers) if handlers is not None else DEFAULT_HANDLERS
        self._watch_factory = watch_factory or watch

    def run(self) -> None:
        """Run the blocking watch loop until interrupted."""
        logger.info(
            "watcher loop started",
            extra={
                "event": "watcher.start",
                "repo_root": str(self.repo_root),
                "patterns": len(self.config.patterns),
                "debounce_ms": self.config.settings.debounce_ms,
            },
        )
        for changes in self._watch_factory(
            self.repo_root,
            watch_filter=self._watch_filter,
            debounce=self.config.settings.debounce_ms,
            raise_interrupt=False,
        ):
            self._process_changes(changes)

    def run_once(self, changes: Iterable[tuple[Change | str, str | Path]]) -> int:
        """Process a single change batch and return number of handler dispatches."""
        return self._process_changes(changes)

    def _process_changes(self, changes: Iterable[tuple[Change | str, str | Path]]) -> int:
        dispatch_count = 0
        for change, changed_path in changes:
            dispatch_count += process_change_event(
                config=self.config,
                repo_root=self.repo_root,
                handlers=self.handlers,
                change=change,
                changed_path=changed_path,
                is_ignored_path_fn=self._is_ignored_path,
            )
        return dispatch_count

    def _dispatch_handlers(self, pattern: PatternConfig, path: Path, change: str) -> int:
        dispatch_count = 0
        for handler in self.handlers:
            try:
                handler(pattern, path, change, self.repo_root, self.config)
                dispatch_count += 1
            except Exception:
                logger.exception(
                    "watcher handler failed",
                    extra={
                        "event": "watcher.error",
                        "handler": getattr(handler, "__name__", str(handler)),
                        "change": change,
                        "path": str(path),
                        "pattern": pattern.pattern,
                    },
                )
        return dispatch_count

    def _is_ignored_path(self, path: Path) -> bool:
        settings = self.config.settings
        posix_path = path.as_posix()

        for part in path.parts:
            if part in settings.ignore_dirs:
                return True

        for glob_pattern in settings.ignore_globs:
            if fnmatch(posix_path, glob_pattern):
                return True

        return False

    def _watch_filter(self, _change: Change, path: str) -> bool:
        candidate_path = Path(path)
        if candidate_path.is_absolute() and candidate_path.is_relative_to(self.repo_root):
            candidate_path = candidate_path.relative_to(self.repo_root)
        return not self._is_ignored_path(candidate_path)

    @staticmethod
    def _normalize_change(change: Change | str) -> str:
        if isinstance(change, Change):
            return change.name.lower()
        return str(change).strip().lower()


def find_matching_pattern(
    relative_path: str,
    change: Change | str,
    patterns: Sequence[PatternConfig],
) -> PatternConfig | None:
    """Find first matching pattern for a repo-relative path/event pair."""
    change_name = DevmanWatcher._normalize_change(change)
    path_posix = Path(relative_path).as_posix()

    for pattern in patterns:
        if change_name not in pattern.on:
            continue

        if _matches_glob(path_posix, pattern.pattern) is False:
            continue

        excluded = any(_matches_glob(path_posix, exclude) for exclude in pattern.exclude)
        if excluded:
            continue

        return pattern

    return None


def _matches_glob(path_posix: str, glob_pattern: str) -> bool:
    """Return whether ``path_posix`` matches ``glob_pattern``.

    For directory-style patterns ending in ``/`` we normalize matching in two ways:

    * Try matching both ``path_posix`` and a slash-suffixed form (for directory events that
      may be emitted without a trailing slash).
    * Preserve cascading child-file behavior by checking ``{glob_pattern}*``.
    """
    if fnmatch(path_posix, glob_pattern):
        return True

    # Support directory-like patterns such as "src/modules/*/".
    if glob_pattern.endswith("/"):
        path_with_slash = path_posix if path_posix.endswith("/") else f"{path_posix}/"
        if fnmatch(path_with_slash, glob_pattern):
            return True

        prefix_pattern = f"{glob_pattern}*"
        return fnmatch(path_posix, prefix_pattern)

    return False


def process_change_event(
    *,
    config: DevmanWatchConfig,
    repo_root: Path,
    handlers: Sequence[WatcherHandler],
    change: Change | str,
    changed_path: str | Path,
    is_ignored_path_fn: Callable[[Path], bool],
) -> int:
    """Process one incoming filesystem change and dispatch matching handlers."""
    change_name = DevmanWatcher._normalize_change(change)
    absolute_path = Path(changed_path)
    if absolute_path.is_absolute():
        if not absolute_path.is_relative_to(repo_root):
            logger.debug(
                "watcher skipped out-of-repo change",
                extra={
                    "event": "watcher.skipped_outside_repo",
                    "change": change_name,
                    "path": str(absolute_path),
                    "repo_root": str(repo_root),
                },
            )
            return 0
        relative_path = absolute_path.relative_to(repo_root)
    else:
        relative_path = absolute_path
        absolute_path = (repo_root / relative_path).resolve()

    if is_ignored_path_fn(relative_path):
        logger.debug(
            "watcher ignored change",
            extra={
                "event": "watcher.ignored",
                "change": change_name,
                "path": str(absolute_path),
                "relative_path": relative_path.as_posix(),
            },
        )
        return 0

    pattern = find_matching_pattern(relative_path.as_posix(), change_name, config.patterns)
    if pattern is None:
        logger.debug(
            "watcher no match",
            extra={
                "event": "watcher.no_match",
                "change": change_name,
                "path": str(absolute_path),
                "relative_path": relative_path.as_posix(),
            },
        )
        return 0

    logger.info(
        "watcher match found",
        extra={
            "event": "watcher.match",
            "change": change_name,
            "path": str(absolute_path),
            "relative_path": relative_path.as_posix(),
            "pattern": pattern.pattern,
            "template": pattern.template,
        },
    )

    dispatch_count = 0
    for handler in handlers:
        try:
            handler(pattern, absolute_path, change_name, repo_root, config)
            dispatch_count += 1
        except Exception:
            logger.exception(
                "watcher handler failed",
                extra={
                    "event": "watcher.error",
                    "handler": getattr(handler, "__name__", str(handler)),
                    "change": change_name,
                    "path": str(absolute_path),
                    "pattern": pattern.pattern,
                },
            )
    return dispatch_count
