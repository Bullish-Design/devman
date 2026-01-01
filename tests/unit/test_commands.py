"""Unit tests for commands module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import typer

from devman.commands import doctor, index, switch
from devman.models import WorkspaceEntry


class TestDoctor:
    """Tests for doctor command."""

    def test_run_returns_availability_dict(self) -> None:
        result = doctor.run()

        assert isinstance(result, dict)
        assert "tmux" in result
        assert "tmuxp" in result
        assert "nvim" in result
        assert "claude" in result

        # All values should be booleans
        for value in result.values():
            assert isinstance(value, bool)

    def test_render_report(self) -> None:
        status = {
            "tmux": True,
            "nvim": False,
            "claude": True,
        }

        report = doctor.render_report(status)

        assert len(report) == 3
        assert "tmux: ok" in report
        assert "nvim: missing" in report
        assert "claude: ok" in report


class TestSwitch:
    """Tests for switch command."""

    def test_resolve_workspace_finds_by_name(self, tmp_path: Path) -> None:
        # Create mock index manager
        entry = WorkspaceEntry(
            name="my-workspace",
            workspace_root=tmp_path / "my-workspace",
            devman_dir=tmp_path / "my-workspace" / ".devman",
        )

        with patch("devman.commands.switch.IndexManager") as mock_manager_class:
            mock_manager = Mock()
            mock_index = Mock()
            mock_index.entries = [entry]
            mock_manager.refresh.return_value = mock_index
            mock_manager.find_entry.return_value = entry
            mock_manager_class.return_value = mock_manager

            result = switch.resolve_workspace("my-workspace", [])

            assert result == entry
            mock_manager.find_entry.assert_called_once()

    def test_run_exits_when_workspace_not_found(self) -> None:
        with patch("devman.commands.switch.resolve_workspace") as mock_resolve:
            mock_resolve.return_value = None

            with pytest.raises(typer.Exit):
                switch.run("nonexistent")

    def test_run_returns_workspace_when_found(self, tmp_path: Path) -> None:
        entry = WorkspaceEntry(
            name="found-workspace",
            workspace_root=tmp_path,
            devman_dir=tmp_path / ".devman",
        )

        with patch("devman.commands.switch.resolve_workspace") as mock_resolve:
            mock_resolve.return_value = entry

            result = switch.run("found")

            assert result == entry


class TestIndexCommands:
    """Tests for index commands."""

    def test_load_index_returns_none_when_missing(self) -> None:
        with patch("devman.commands.index.IndexManager") as mock_manager_class:
            mock_manager = Mock()
            mock_manager.load.return_value = None
            mock_manager_class.return_value = mock_manager

            result = index.load_index(mock_manager)

            assert result is None

    def test_refresh_index_uses_resolved_roots(self, tmp_path: Path) -> None:
        with patch("devman.commands.index.resolve_roots") as mock_resolve:
            with patch("devman.commands.index.IndexManager") as mock_manager_class:
                mock_resolve.return_value = [tmp_path]
                mock_manager = Mock()
                mock_index = Mock()
                mock_manager.refresh.return_value = mock_index
                mock_manager_class.return_value = mock_manager

                result = index.refresh_index(["/test"])

                mock_resolve.assert_called_once_with(["/test"])
                mock_manager.refresh.assert_called_once_with([tmp_path])
                assert result == mock_index

    def test_list_entries_formats_basic_entry(self, tmp_path: Path) -> None:
        entry = WorkspaceEntry(
            name="test-ws",
            workspace_root=tmp_path,
            devman_dir=tmp_path / ".devman",
        )

        lines = index.list_entries([entry])

        assert len(lines) == 1
        assert "test-ws" in lines[0]
        assert str(tmp_path) in lines[0]

    def test_list_entries_includes_group_and_tags(self, tmp_path: Path) -> None:
        entry = WorkspaceEntry(
            name="test-ws",
            workspace_root=tmp_path,
            devman_dir=tmp_path / ".devman",
            group="mygroup",
            tags=["tag1", "tag2"],
        )

        lines = index.list_entries([entry])

        assert len(lines) == 1
        assert "mygroup" in lines[0]
        assert "tag1" in lines[0]
        assert "tag2" in lines[0]

    def test_find_entry_returns_match(self, tmp_path: Path) -> None:
        entry = WorkspaceEntry(
            name="target",
            workspace_root=tmp_path,
            devman_dir=tmp_path / ".devman",
        )

        with patch("devman.commands.index.IndexManager") as mock_manager_class:
            mock_manager = Mock()
            mock_manager.find_entry.return_value = entry
            mock_manager_class.return_value = mock_manager

            result = index.find_entry([entry], "target", mock_manager)

            assert result == entry
            mock_manager.find_entry.assert_called_once_with([entry], "target")
