"""Unit tests for state module."""

from __future__ import annotations

from pathlib import Path

import pytest

from devman.models import SessionState, WorkspaceConfig
from devman.state import StateManager


class TestStateManager:
    """Tests for StateManager class."""

    @pytest.fixture
    def workspace_config(self, tmp_path: Path) -> WorkspaceConfig:
        """Create a test workspace config."""
        devman_dir = tmp_path / ".devman"
        devman_dir.mkdir(parents=True)
        return WorkspaceConfig(
            name="test-workspace",
            root=tmp_path,
            devman_dir=devman_dir,
            claude_interaction=None,
            claude_emit_project_config=False,
        )

    @pytest.fixture
    def state_manager(self) -> StateManager:
        """Create a StateManager instance."""
        return StateManager()

    def test_read_returns_empty_state_when_file_missing(
        self,
        state_manager: StateManager,
        workspace_config: WorkspaceConfig,
    ) -> None:
        state = state_manager.read(workspace_config)
        assert state.tmux_session is None
        assert state.nvim_listen is None

    def test_write_and_read_roundtrip(
        self,
        state_manager: StateManager,
        workspace_config: WorkspaceConfig,
        tmp_path: Path,
    ) -> None:
        # Create state
        nvim_socket = tmp_path / "nvim.sock"
        test_state = SessionState(
            tmux_session="my-session",
            nvim_listen=nvim_socket,
        )

        # Write state
        state_manager.write(workspace_config, test_state)

        # Read state back
        loaded_state = state_manager.read(workspace_config)

        assert loaded_state.tmux_session == "my-session"
        assert loaded_state.nvim_listen == nvim_socket

    def test_write_creates_directory_if_missing(
        self,
        state_manager: StateManager,
        tmp_path: Path,
    ) -> None:
        # Create config with non-existent devman dir
        devman_dir = tmp_path / ".devman"
        config = WorkspaceConfig(
            name="test",
            root=tmp_path,
            devman_dir=devman_dir,
            claude_interaction=None,
            claude_emit_project_config=False,
        )

        test_state = SessionState(
            tmux_session="test-session",
            nvim_listen=None,
        )

        # Should create directory and write state
        state_manager.write(config, test_state)

        assert devman_dir.exists()
        state_file = devman_dir / ".state.json"
        assert state_file.exists()

    def test_read_handles_corrupted_json(
        self,
        state_manager: StateManager,
        workspace_config: WorkspaceConfig,
    ) -> None:
        # Write corrupted JSON
        state_file = workspace_config.devman_dir / ".state.json"
        state_file.write_text("invalid json {{{", encoding="utf-8")

        # Should return empty state instead of crashing
        state = state_manager.read(workspace_config)
        assert state.tmux_session is None
        assert state.nvim_listen is None

    def test_state_file_path(
        self,
        state_manager: StateManager,
        workspace_config: WorkspaceConfig,
    ) -> None:
        expected_path = workspace_config.devman_dir / ".state.json"
        actual_path = state_manager.state_file_path(workspace_config)
        assert actual_path == expected_path
