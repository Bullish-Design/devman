# src/devman/core/index.py
"""Workspace indexing utilities for llm-core."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import tomllib

from . import paths


@dataclass(frozen=True)
class WorkspaceEntry:
    """Metadata for a single workspace."""

    name: str
    workspace_root: str
    devman_dir: str
    tags: list[str] = field(default_factory=list)
    group: str | None = None

    @classmethod
    def from_workspace(cls, workspace_root: Path, devman_dir: Path) -> "WorkspaceEntry":
        metadata = _load_workspace_metadata(devman_dir)
        return cls(
            name=metadata.name or workspace_root.name,
            workspace_root=str(workspace_root),
            devman_dir=str(devman_dir),
            tags=metadata.tags,
            group=metadata.group,
        )

    def matches(self, query: str) -> bool:
        """Check if the entry matches a query string."""
        normalized = query.lower()
        if normalized in self.name.lower():
            return True
        if normalized in self.workspace_root.lower():
            return True
        if self.group and normalized in self.group.lower():
            return True
        return any(normalized in tag.lower() for tag in self.tags)


@dataclass(frozen=True)
class WorkspaceIndex:
    """Index payload for cached workspace data."""

    entries: list[WorkspaceEntry]
    roots: list[str]
    generated_at: str
    version: int = 1

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "generated_at": self.generated_at,
            "roots": self.roots,
            "entries": [
                {
                    "name": entry.name,
                    "workspace_root": entry.workspace_root,
                    "devman_dir": entry.devman_dir,
                    "tags": entry.tags,
                    "group": entry.group,
                }
                for entry in self.entries
            ],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "WorkspaceIndex":
        entries = [
            WorkspaceEntry(
                name=str(entry.get("name", "")),
                workspace_root=str(entry.get("workspace_root", "")),
                devman_dir=str(entry.get("devman_dir", "")),
                tags=list(entry.get("tags", []) or []),
                group=entry.get("group"),
            )
            for entry in payload.get("entries", [])
        ]
        return cls(
            entries=entries,
            roots=[str(root) for root in payload.get("roots", [])],
            generated_at=str(payload.get("generated_at", "")),
            version=int(payload.get("version", 1)),
        )


class IndexManager:
    """Manage the workspace index cache."""

    def __init__(self, cache_path: Path | None = None) -> None:
        self.cache_path = cache_path or paths.index_cache_path()

    def load(self) -> WorkspaceIndex | None:
        """Load the index cache from disk."""
        if not self.cache_path.exists():
            return None
        payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        return WorkspaceIndex.from_dict(payload)

    def save(self, index: WorkspaceIndex) -> None:
        """Persist the index cache to disk."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(index.to_dict(), indent=2),
            encoding="utf-8",
        )

    def refresh(self, roots: Iterable[Path]) -> WorkspaceIndex:
        """Refresh the index using cache when possible."""
        resolved_roots = _resolve_roots(roots)
        cached = self.load()
        if cached and self._is_valid(cached, resolved_roots):
            return cached
        return self.rebuild(resolved_roots)

    def rebuild(self, roots: Iterable[Path]) -> WorkspaceIndex:
        """Rebuild the index by scanning the provided roots."""
        resolved_roots = _resolve_roots(roots)
        entries = self._scan(resolved_roots)
        index = WorkspaceIndex(
            entries=entries,
            roots=[str(root) for root in resolved_roots],
            generated_at=_timestamp(),
        )
        self.save(index)
        return index

    def find_entry(
        self, entries: Iterable[WorkspaceEntry], query: str
    ) -> WorkspaceEntry | None:
        """Find a workspace entry by name, tag, group, or path."""
        for entry in entries:
            if entry.matches(query):
                return entry
        return None

    def _is_valid(self, index: WorkspaceIndex, roots: list[Path]) -> bool:
        if [str(root) for root in roots] != index.roots:
            return False
        for entry in index.entries:
            if not Path(entry.devman_dir).is_dir():
                return False
        return True

    def _scan(self, roots: Iterable[Path]) -> list[WorkspaceEntry]:
        entries: list[WorkspaceEntry] = []
        for root in roots:
            if not root.exists():
                continue
            for dirpath, dirnames, _ in os.walk(root):
                if paths.DEV_MAN_DIRNAME in dirnames:
                    devman_dir = Path(dirpath) / paths.DEV_MAN_DIRNAME
                    entries.append(WorkspaceEntry.from_workspace(Path(dirpath), devman_dir))
                    dirnames.remove(paths.DEV_MAN_DIRNAME)
        return entries


@dataclass(frozen=True)
class WorkspaceMetadata:
    name: str | None = None
    tags: list[str] = field(default_factory=list)
    group: str | None = None


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


def _resolve_roots(roots: Iterable[Path]) -> list[Path]:
    return [Path(root).expanduser().resolve() for root in roots]


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()
