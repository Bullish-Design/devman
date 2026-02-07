"""Handler entrypoints for watcher match dispatch."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from devman.watcher.config import DevmanWatchConfig, PatternConfig

logger = logging.getLogger(__name__)

WatcherHandler = Callable[
    [PatternConfig, Path, str, Path, DevmanWatchConfig],
    None,
]


def handle_pattern_match(
    pattern: PatternConfig,
    matched_path: Path,
    change: str,
    repo_root: Path,
    config: DevmanWatchConfig,
) -> None:
    """Default match handler entrypoint.

    This is intentionally lightweight for MVP and can be expanded by Task 6
    to perform template instantiation.
    """
    logger.info(
        "watcher handler invoked",
        extra={
            "event": "watcher.handler",
            "change": change,
            "path": str(matched_path),
            "pattern": pattern.pattern,
            "template": pattern.template,
            "repo_root": str(repo_root),
            "ignore_dirs": config.settings.ignore_dirs,
        },
    )


DEFAULT_HANDLERS: tuple[WatcherHandler, ...] = (handle_pattern_match,)
