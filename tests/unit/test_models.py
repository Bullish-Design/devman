"""Unit tests for models module."""

from __future__ import annotations

from pathlib import Path

import pytest

from devman.models import WorkspaceEntry, WorkspaceIndex


class TestWorkspaceEntry:
    """Tests for WorkspaceEntry model."""

    def test_creates_basic_entry(self, tmp_path: Path) -> None:
        entry = WorkspaceEntry(
            name="test",
            workspace_root=tmp_path,
            devman_dir=tmp_path / ".devman",
        )

        assert entry.name == "test"
        assert entry.workspace_root == tmp_path
        assert entry.devman_dir == tmp_path / ".devman"
        assert entry.group is None
        assert entry.tags == []

    def test_creates_entry_with_group_and_tags(self, tmp_path: Path) -> None:
        entry = WorkspaceEntry(
            name="test",
            workspace_root=tmp_path,
            devman_dir=tmp_path / ".devman",
            group="mygroup",
            tags=["tag1", "tag2"],
        )

        assert entry.group == "mygroup"
        assert entry.tags == ["tag1", "tag2"]

    def test_to_dict_conversion(self, tmp_path: Path) -> None:
        entry = WorkspaceEntry(
            name="test",
            workspace_root=tmp_path,
            devman_dir=tmp_path / ".devman",
            group="mygroup",
            tags=["tag1"],
        )

        data = entry.to_dict()

        assert data["name"] == "test"
        assert data["workspace_root"] == str(tmp_path)
        assert data["devman_dir"] == str(tmp_path / ".devman")
        assert data["group"] == "mygroup"
        assert data["tags"] == ["tag1"]

    def test_from_dict_conversion(self, tmp_path: Path) -> None:
        data = {
            "name": "test",
            "workspace_root": str(tmp_path),
            "devman_dir": str(tmp_path / ".devman"),
            "group": "mygroup",
            "tags": ["tag1", "tag2"],
        }

        entry = WorkspaceEntry.from_dict(data)

        assert entry.name == "test"
        assert entry.workspace_root == tmp_path
        assert entry.devman_dir == tmp_path / ".devman"
        assert entry.group == "mygroup"
        assert entry.tags == ["tag1", "tag2"]

    def test_roundtrip_to_dict_from_dict(self, tmp_path: Path) -> None:
        original = WorkspaceEntry(
            name="test",
            workspace_root=tmp_path,
            devman_dir=tmp_path / ".devman",
            group="group",
            tags=["a", "b"],
        )

        data = original.to_dict()
        restored = WorkspaceEntry.from_dict(data)

        assert restored == original


class TestWorkspaceIndex:
    """Tests for WorkspaceIndex model."""

    def test_creates_empty_index(self) -> None:
        index = WorkspaceIndex(entries=[], roots=[])

        assert index.entries == []
        assert index.roots == []

    def test_creates_index_with_entries(self, tmp_path: Path) -> None:
        entry = WorkspaceEntry(
            name="test",
            workspace_root=tmp_path,
            devman_dir=tmp_path / ".devman",
        )

        index = WorkspaceIndex(entries=[entry], roots=[tmp_path])

        assert len(index.entries) == 1
        assert index.entries[0] == entry
        assert index.roots == [tmp_path]

    def test_to_dict_conversion(self, tmp_path: Path) -> None:
        entry = WorkspaceEntry(
            name="test",
            workspace_root=tmp_path,
            devman_dir=tmp_path / ".devman",
        )
        index = WorkspaceIndex(entries=[entry], roots=[tmp_path])

        data = index.to_dict()

        assert "entries" in data
        assert "roots" in data
        assert len(data["entries"]) == 1
        assert data["roots"] == [str(tmp_path)]

    def test_from_dict_conversion(self, tmp_path: Path) -> None:
        data = {
            "entries": [
                {
                    "name": "test",
                    "workspace_root": str(tmp_path),
                    "devman_dir": str(tmp_path / ".devman"),
                    "group": None,
                    "tags": [],
                }
            ],
            "roots": [str(tmp_path)],
        }

        index = WorkspaceIndex.from_dict(data)

        assert len(index.entries) == 1
        assert index.entries[0].name == "test"
        assert len(index.roots) == 1
        assert index.roots[0] == tmp_path

    def test_roundtrip_to_dict_from_dict(self, tmp_path: Path) -> None:
        entry = WorkspaceEntry(
            name="test",
            workspace_root=tmp_path,
            devman_dir=tmp_path / ".devman",
            group="group",
            tags=["tag"],
        )
        original = WorkspaceIndex(entries=[entry], roots=[tmp_path])

        data = original.to_dict()
        restored = WorkspaceIndex.from_dict(data)

        assert len(restored.entries) == len(original.entries)
        assert restored.entries[0] == original.entries[0]
        assert restored.roots == original.roots
