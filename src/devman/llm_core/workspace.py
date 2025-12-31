"""Workspace discovery and configuration loading."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from devman.models.workspace import WorkspaceConfig

ENV_ROOTS = "LLM_CORE_ROOTS"


def find_devman_dir(start: Path) -> Path | None:
    current = start.resolve()
    while True:
        candidate = current / ".devman"
        if candidate.exists():
            return candidate
        if current.parent == current:
            return None
        current = current.parent


def resolve_roots(cli_roots: Iterable[str]) -> list[Path]:
    roots = [Path(root).expanduser() for root in cli_roots if root]
    if not roots:
        env_roots = os.environ.get(ENV_ROOTS, "")
        if env_roots:
            roots = [Path(root).expanduser() for root in env_roots.split(":") if root]
    if not roots:
        roots = [Path.cwd()]
    unique_roots: list[Path] = []
    for root in roots:
        resolved = root.resolve()
        if resolved not in unique_roots:
            unique_roots.append(resolved)
    return unique_roots


def load_workspace_config(devman_dir: Path) -> WorkspaceConfig:
    return WorkspaceConfig.load(devman_dir)
