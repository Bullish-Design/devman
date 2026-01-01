"""Unit tests for discovery module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from devman.discovery import (
    IndexManager,
    build_entry,
    find_devman_dir,
    resolve_roots,
)
from devman.models import WorkspaceEntry, WorkspaceIndex


class TestFindDevmanDir:
    """Tests for find_devman_dir function."""

    def test_finds_devman_in_current_dir(self, tmp_path: Path) -> None:
        devman_dir = tmp_path / ".devman"
        devman_dir.mkdir()
        assert find_devman_dir(tmp_path) == devman_dir

    def test_finds_devman_in_parent_dir(self, tmp_path: Path) -> None:
        devman_dir = tmp_path / ".devman"
        devman_dir.mkdir()
        child_dir = tmp_path / "child"
        child_dir.mkdir()
        assert find_devman_dir(child_dir) == devman_dir

    def test_returns_none_when_not_found(self, tmp_path: Path) -> None:
        assert find_devman_dir(tmp_path) is None

    def test_stops_at_home_directory(self, tmp_path: Path) -> None:
        # Should not traverse above home directory
        deep_path = tmp_path / "a" / "b" / "c" / "d"
        deep_path.mkdir(parents=True)
        assert find_devman_dir(deep_path) is None


class TestBuildEntry:
    """Tests for build_entry function."""

    def test_builds_basic_entry(self, tmp_path: Path) -> None:
        devman_dir = tmp_path / ".devman"
        devman_dir.mkdir()

        entry = build_entry(tmp_path, devman_dir)

        assert entry.name == tmp_path.name
        assert entry.workspace_root == tmp_path
        assert entry.devman_dir == devman_dir
        assert entry.group is None
        assert entry.tags == []

    def test_reads_group_from_file(self, tmp_path: Path) -> None:
        devman_dir = tmp_path / ".devman"
        devman_dir.mkdir()
        (devman_dir / "group.txt").write_text("mygroup", encoding="utf-8")

        entry = build_entry(tmp_path, devman_dir)

        assert entry.group == "mygroup"

    def test_reads_tags_from_file(self, tmp_path: Path) -> None:
        devman_dir = tmp_path / ".devman"
        devman_dir.mkdir()
        (devman_dir / "tags.txt").write_text("tag1\ntag2\ntag3", encoding="utf-8")

        entry = build_entry(tmp_path, devman_dir)

        assert entry.tags == ["tag1", "tag2", "tag3"]


class TestResolveRoots:
    """Tests for resolve_roots function."""

    def test_returns_empty_list_for_empty_input(self) -> None:
        assert resolve_roots([]) == []

    def test_expands_tilde_in_paths(self) -> None:
        with patch.object(Path, "expanduser") as mock_expand:
            mock_expand.return_value = Path("/home/user/test")
            result = resolve_roots(["~/test"])
            assert len(result) == 1
            mock_expand.assert_called()

    def test_converts_strings_to_paths(self) -> None:
        result = resolve_roots(["/tmp/test"])
        assert len(result) == 1
        assert isinstance(result[0], Path)


class TestIndexManager:
    """Tests for IndexManager class."""

    def test_init_creates_default_cache_path(self) -> None:
        manager = IndexManager()
        assert manager.cache_path is not None

    def test_load_returns_none_when_cache_missing(self, tmp_path: Path) -> None:
        cache_path = tmp_path / "nonexistent_cache.json"
        manager = IndexManager(cache_path)
        assert manager.load() is None

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        cache_path = tmp_path / "index_cache.json"
        manager = IndexManager(cache_path)

        # Create test entry
        entry = WorkspaceEntry(
            name="test",
            workspace_root=tmp_path / "workspace",
            devman_dir=tmp_path / "workspace" / ".devman",
            group="testgroup",
            tags=["tag1", "tag2"],
        )
        index = WorkspaceIndex(
            entries=[entry],
            roots=[tmp_path],
        )

        # Save and load
        manager.save(index)
        loaded = manager.load()

        assert loaded is not None
        assert len(loaded.entries) == 1
        assert loaded.entries[0].name == "test"
        assert loaded.entries[0].group == "testgroup"
        assert loaded.entries[0].tags == ["tag1", "tag2"]

    def test_is_valid_checks_roots(self, tmp_path: Path) -> None:
        manager = IndexManager()
        entry = WorkspaceEntry(
            name="test",
            workspace_root=tmp_path,
            devman_dir=tmp_path / ".devman",
        )
        index = WorkspaceIndex(entries=[entry], roots=[tmp_path])

        # Same roots should be valid
        assert manager.is_valid(index, [tmp_path])

        # Different roots should be invalid
        assert not manager.is_valid(index, [tmp_path / "other"])

    def test_is_valid_checks_directory_existence(self, tmp_path: Path) -> None:
        manager = IndexManager()

        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()
        devman_dir = workspace_root / ".devman"
        devman_dir.mkdir()

        entry = WorkspaceEntry(
            name="test",
            workspace_root=workspace_root,
            devman_dir=devman_dir,
        )
        index = WorkspaceIndex(entries=[entry], roots=[tmp_path])

        # Should be valid when directories exist
        assert manager.is_valid(index, [tmp_path])

        # Should be invalid when devman_dir doesn't exist
        devman_dir.rmdir()
        assert not manager.is_valid(index, [tmp_path])

    def test_scan_finds_devman_directories(self, tmp_path: Path) -> None:
        # Create test workspaces
        ws1 = tmp_path / "workspace1"
        ws1.mkdir()
        (ws1 / ".devman").mkdir()

        ws2 = tmp_path / "workspace2"
        ws2.mkdir()
        (ws2 / ".devman").mkdir()

        manager = IndexManager()
        entries = manager.scan([tmp_path])

        assert len(entries) == 2
        names = {e.name for e in entries}
        assert "workspace1" in names
        assert "workspace2" in names

    def test_find_entry_by_exact_name(self, tmp_path: Path) -> None:
        entry1 = WorkspaceEntry(
            name="workspace1",
            workspace_root=tmp_path / "workspace1",
            devman_dir=tmp_path / "workspace1" / ".devman",
        )
        entry2 = WorkspaceEntry(
            name="workspace2",
            workspace_root=tmp_path / "workspace2",
            devman_dir=tmp_path / "workspace2" / ".devman",
        )

        manager = IndexManager()
        found = manager.find_entry([entry1, entry2], "workspace1")

        assert found == entry1

    def test_find_entry_by_partial_name(self, tmp_path: Path) -> None:
        entry = WorkspaceEntry(
            name="my-workspace",
            workspace_root=tmp_path / "my-workspace",
            devman_dir=tmp_path / "my-workspace" / ".devman",
        )

        manager = IndexManager()
        found = manager.find_entry([entry], "workspace")

        assert found == entry

    def test_find_entry_returns_none_when_not_found(self, tmp_path: Path) -> None:
        entry = WorkspaceEntry(
            name="workspace1",
            workspace_root=tmp_path / "workspace1",
            devman_dir=tmp_path / "workspace1" / ".devman",
        )

        manager = IndexManager()
        found = manager.find_entry([entry], "nonexistent")

        assert found is None
