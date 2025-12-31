"""Workspace discovery utilities."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import tomllib

from devman.models import WorkspaceEntry


DEV_MAN_DIRNAME = ".devman"
ENV_ROOTS = "LLM_CORE_ROOTS"
SKIP_DIRS = {".git", ".hg", ".svn", ".direnv", ".venv", "node_modules"}


@dataclass(frozen=True)
class WorkspaceMetadata:
    name: str | None = None
    tags: list[str] = field(default_factory=list)
    group: str | None = None


def resolve_roots(roots: Iterable[str]) -> list[Path]:
    """Resolve workspace roots from CLI values or environment."""
    root_values = [root for root in roots if root]
    if not root_values:
        env_roots = os.environ.get(ENV_ROOTS)
        if env_roots:
            root_values = [root for root in env_roots.split(os.pathsep) if root]

    if not root_values:
        root_values = [str(Path.home())]

    resolved: list[Path] = []
    for root in root_values:
        candidate = Path(root).expanduser().resolve()
        if candidate not in resolved:
            resolved.append(candidate)
    return resolved


def resolve_root_paths(roots: Iterable[Path]) -> list[Path]:
    """Resolve and normalize root path objects."""
    resolved: list[Path] = []
    for root in roots:
        candidate = Path(root).expanduser().resolve()
        if candidate not in resolved:
            resolved.append(candidate)
    return resolved


def find_devman_dir(start: Path) -> Path | None:
    """Find the closest .devman directory at or above the start path."""
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for candidate in [current, *current.parents]:
        devman_dir = candidate / DEV_MAN_DIRNAME
        if devman_dir.is_dir():
            return devman_dir
    return None


def scan_roots(roots: Iterable[Path]) -> list[WorkspaceEntry]:
    """Scan the provided roots for devman workspaces."""
    entries: list[WorkspaceEntry] = []
    for root in roots:
        if not root.exists():
            continue
        for dirpath, dirnames, _ in os.walk(root):
            for skip in SKIP_DIRS:
                if skip in dirnames:
                    dirnames.remove(skip)
            if DEV_MAN_DIRNAME in dirnames:
                devman_dir = Path(dirpath) / DEV_MAN_DIRNAME
                entries.append(build_entry(Path(dirpath), devman_dir))
                dirnames.remove(DEV_MAN_DIRNAME)
    return entries


def build_entry(workspace_root: Path, devman_dir: Path) -> WorkspaceEntry:
    """Build a workspace entry for a workspace root."""
    metadata = _load_workspace_metadata(devman_dir)
    return WorkspaceEntry(
        name=metadata.name or workspace_root.name,
        workspace_root=workspace_root,
        devman_dir=devman_dir,
        tags=metadata.tags,
        group=metadata.group,
    )


def timestamp() -> str:
    """Return a UTC ISO8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()


def _load_workspace_metadata(devman_dir: Path) -> WorkspaceMetadata:
    config_path = devman_dir / "devman.toml"
    if not config_path.exists():
        return WorkspaceMetadata()

    payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    workspace = payload.get("workspace", {})
    name = workspace.get("name") if isinstance(workspace, dict) else None
    tags = workspace.get("tags", []) if isinstance(workspace, dict) else []
    group = workspace.get("group") if isinstance(workspace, dict) else None

    tag_list: list[str] = []
    if isinstance(tags, list):
        tag_list = [str(tag) for tag in tags]

    return WorkspaceMetadata(name=name, tags=tag_list, group=group)
