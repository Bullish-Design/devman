"""Workspace index management."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .models import WorkspaceEntry
from .workspace import load_workspace_config

INDEX_DIR = Path.home() / ".cache" / "llm-core"
INDEX_FILE = INDEX_DIR / "index.json"

SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", ".direnv", ".venv"}


def index_path() -> Path:
    return INDEX_FILE


def _serialize_entries(entries: list[WorkspaceEntry]) -> list[dict[str, object]]:
    return [entry.model_dump(mode="json") for entry in entries]


def _deserialize_entries(payload: list[dict[str, object]]) -> list[WorkspaceEntry]:
    return [WorkspaceEntry.model_validate(entry) for entry in payload]


def load_index() -> dict[str, object] | None:
    if not INDEX_FILE.exists():
        return None
    payload = json.loads(INDEX_FILE.read_text())
    if not isinstance(payload, dict):
        return None
    return payload


def write_index(entries: list[WorkspaceEntry]) -> None:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entries": _serialize_entries(entries),
    }
    INDEX_FILE.write_text(json.dumps(payload, indent=2))


def _scan_root(root: Path) -> list[WorkspaceEntry]:
    entries: list[WorkspaceEntry] = []
    if not root.exists():
        return entries
    for dirpath, dirnames, _ in os.walk(root):
        for skip in SKIP_DIRS:
            if skip in dirnames:
                dirnames.remove(skip)
        if ".devman" in dirnames:
            devman_dir = Path(dirpath) / ".devman"
            config = load_workspace_config(devman_dir)
            entries.append(
                WorkspaceEntry(
                    name=config.name,
                    root=config.root,
                    tags=config.tags,
                    group=config.group,
                )
            )
            dirnames.remove(".devman")
    return entries


def rebuild_index(roots: Iterable[Path]) -> list[WorkspaceEntry]:
    entries: list[WorkspaceEntry] = []
    for root in roots:
        entries.extend(_scan_root(root))
    write_index(entries)
    return entries


def refresh_index(roots: Iterable[Path]) -> list[WorkspaceEntry]:
    payload = load_index()
    if not payload:
        return rebuild_index(roots)
    entries_payload = payload.get("entries", [])
    if not isinstance(entries_payload, list):
        return rebuild_index(roots)
    return _deserialize_entries(entries_payload)


def list_entries(entries: Iterable[WorkspaceEntry]) -> list[str]:
    lines: list[str] = []
    for entry in entries:
        tag_segment = f" [{', '.join(entry.tags)}]" if entry.tags else ""
        group_segment = f" ({entry.group})" if entry.group else ""
        lines.append(f"{entry.name}{group_segment} - {entry.root}{tag_segment}")
    return lines


def find_entry(entries: Iterable[WorkspaceEntry], query: str) -> WorkspaceEntry | None:
    query_path = Path(query).expanduser()
    if query_path.exists():
        resolved = query_path.resolve()
        for entry in entries:
            if entry.root.resolve() == resolved:
                return entry
    for entry in entries:
        if entry.name == query:
            return entry
        if query in entry.tags:
            return entry
        if query in str(entry.root):
            return entry
    return None
