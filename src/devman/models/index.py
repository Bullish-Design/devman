"""Workspace index models."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceEntry(BaseModel):
    """Metadata for a single workspace."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    name: str
    workspace_root: Path
    devman_dir: Path
    tags: list[str] = Field(default_factory=list)
    group: str | None = None

    def matches(self, query: str) -> bool:
        """Check if the entry matches a query string."""
        normalized = query.lower()
        if normalized in self.name.lower():
            return True
        if normalized in str(self.workspace_root).lower():
            return True
        if self.group and normalized in self.group.lower():
            return True
        return any(normalized in tag.lower() for tag in self.tags)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "workspace_root": str(self.workspace_root),
            "devman_dir": str(self.devman_dir),
            "tags": list(self.tags),
            "group": self.group,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "WorkspaceEntry":
        return cls(
            name=str(payload.get("name", "")),
            workspace_root=Path(str(payload.get("workspace_root", ""))),
            devman_dir=Path(str(payload.get("devman_dir", ""))),
            tags=list(payload.get("tags", []) or []),
            group=payload.get("group"),
        )


class WorkspaceIndex(BaseModel):
    """Index payload for cached workspace data."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    entries: list[WorkspaceEntry]
    roots: list[Path]
    generated_at: str
    version: int = 1

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "generated_at": self.generated_at,
            "roots": [str(root) for root in self.roots],
            "entries": [entry.to_dict() for entry in self.entries],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "WorkspaceIndex":
        entries_payload = payload.get("entries", [])
        entries = []
        if isinstance(entries_payload, list):
            entries = [
                WorkspaceEntry.from_dict(entry)
                for entry in entries_payload
                if isinstance(entry, dict)
            ]
        roots_payload = payload.get("roots", [])
        roots = [Path(str(root)) for root in roots_payload if root]
        return cls(
            entries=entries,
            roots=roots,
            generated_at=str(payload.get("generated_at", "")),
            version=int(payload.get("version", 1)),
        )
