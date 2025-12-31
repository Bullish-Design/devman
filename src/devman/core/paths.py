# src/devman/core/paths.py
"""Path helpers for llm-core workspace management."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


DEFAULT_CACHE_DIRNAME = "llm-core"
DEV_MAN_DIRNAME = ".devman"
ENV_ROOTS = "LLM_CORE_ROOTS"


def cache_dir() -> Path:
    """Return the cache directory for llm-core data."""
    base = os.environ.get("XDG_CACHE_HOME")
    if base:
        return Path(base).expanduser() / DEFAULT_CACHE_DIRNAME
    return Path.home() / ".cache" / DEFAULT_CACHE_DIRNAME


def index_cache_path() -> Path:
    """Return the path to the index cache file."""
    return cache_dir() / "index.json"


def resolve_roots(roots: Iterable[str]) -> list[Path]:
    """Resolve workspace scan roots from CLI values or environment."""
    root_values = list(roots)
    if not root_values:
        env_roots = os.environ.get(ENV_ROOTS)
        if env_roots:
            root_values = [root for root in env_roots.split(os.pathsep) if root]

    resolved: list[Path] = []
    if root_values:
        for root in root_values:
            resolved.append(Path(root).expanduser().resolve())
        return resolved

    return [Path.home()]


def find_devman_dir(start: Path) -> Path | None:
    """Find the closest .devman directory at or above the start path."""
    for candidate in [start, *start.parents]:
        devman_dir = candidate / DEV_MAN_DIRNAME
        if devman_dir.exists() and devman_dir.is_dir():
            return devman_dir
    return None
