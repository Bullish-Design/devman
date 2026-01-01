"""Unit tests for integrations module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from devman.integrations import (
    ClaudeIntegration,
    NvimIntegration,
    TmuxIntegration,
    TmuxpIntegration,
)


class TestTmuxIntegration:
    """Tests for TmuxIntegration."""

    @pytest.fixture
    def tmux(self) -> TmuxIntegration:
        return TmuxIntegration()

    def test_is_available_when_command_exists(self, tmux: TmuxIntegration) -> None:
        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/tmux"
            assert tmux.is_available() is True

    def test_is_available_when_command_missing(self, tmux: TmuxIntegration) -> None:
        with patch("shutil.which") as mock_which:
            mock_which.return_value = None
            assert tmux.is_available() is False

    def test_session_exists_calls_correct_command(self, tmux: TmuxIntegration) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            result = tmux.session_exists("my-session")

            assert result is True
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "tmux" in args
            assert "has-session" in args
            assert "my-session" in args

    def test_kill_session_calls_correct_command(self, tmux: TmuxIntegration) -> None:
        with patch("subprocess.run") as mock_run:
            tmux.kill_session("my-session")

            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "tmux" in args
            assert "kill-session" in args
            assert "my-session" in args


class TestTmuxpIntegration:
    """Tests for TmuxpIntegration."""

    @pytest.fixture
    def tmuxp(self) -> TmuxpIntegration:
        return TmuxpIntegration()

    def test_is_available_when_command_exists(self, tmuxp: TmuxpIntegration) -> None:
        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/tmuxp"
            assert tmuxp.is_available() is True

    def test_is_available_when_command_missing(self, tmuxp: TmuxpIntegration) -> None:
        with patch("shutil.which") as mock_which:
            mock_which.return_value = None
            assert tmuxp.is_available() is False


class TestNvimIntegration:
    """Tests for NvimIntegration."""

    @pytest.fixture
    def nvim(self) -> NvimIntegration:
        return NvimIntegration()

    def test_is_available_when_command_exists(self, nvim: NvimIntegration) -> None:
        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/nvim"
            assert nvim.is_available() is True

    def test_is_available_when_command_missing(self, nvim: NvimIntegration) -> None:
        with patch("shutil.which") as mock_which:
            mock_which.return_value = None
            assert nvim.is_available() is False

    def test_build_session_commands(self, nvim: NvimIntegration, tmp_path: Path) -> None:
        session_path = tmp_path / "session.vim"
        commands = nvim.build_session_commands(tmp_path, session_path)

        assert isinstance(commands, list)
        assert len(commands) > 0
        # Should include cd command and source command
        assert any("cd" in cmd for cmd in commands)
        assert any("source" in cmd for cmd in commands)

    def test_remote_send_uses_correct_socket(
        self,
        nvim: NvimIntegration,
        tmp_path: Path,
    ) -> None:
        socket = tmp_path / "nvim.sock"

        with patch("subprocess.run") as mock_run:
            nvim.remote_send(socket, "echo 'test'")

            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "nvim" in args
            assert "--server" in args
            assert str(socket) in args


class TestClaudeIntegration:
    """Tests for ClaudeIntegration."""

    @pytest.fixture
    def claude(self) -> ClaudeIntegration:
        return ClaudeIntegration()

    def test_is_available_when_command_exists(
        self,
        claude: ClaudeIntegration,
    ) -> None:
        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/claude"
            assert claude.is_available() is True

    def test_is_available_when_command_missing(
        self,
        claude: ClaudeIntegration,
    ) -> None:
        with patch("shutil.which") as mock_which:
            mock_which.return_value = None
            assert claude.is_available() is False

    def test_ensure_workspace_settings_creates_directory(
        self,
        claude: ClaudeIntegration,
        tmp_path: Path,
    ) -> None:
        settings_path = claude.ensure_workspace_settings(
            tmp_path,
            None,
            False,
        )

        assert settings_path.exists()
        assert settings_path.parent == tmp_path / ".claude"
        assert (tmp_path / ".claude").exists()

    def test_ensure_workspace_settings_writes_json(
        self,
        claude: ClaudeIntegration,
        tmp_path: Path,
    ) -> None:
        settings_path = claude.ensure_workspace_settings(
            tmp_path,
            None,
            False,
        )

        # Should be valid JSON
        import json
        settings = json.loads(settings_path.read_text())
        assert "project" in settings
        assert "root" in settings["project"]

    def test_ensure_workspace_settings_with_interaction(
        self,
        claude: ClaudeIntegration,
        tmp_path: Path,
    ) -> None:
        interaction = tmp_path / "interaction.md"
        interaction.write_text("# Test", encoding="utf-8")

        settings_path = claude.ensure_workspace_settings(
            tmp_path,
            interaction,
            False,
        )

        import json
        settings = json.loads(settings_path.read_text())
        assert "interaction" in settings["project"]

    def test_emit_project_config_creates_file(
        self,
        claude: ClaudeIntegration,
        tmp_path: Path,
    ) -> None:
        config_path = claude.emit_project_config(tmp_path, None)

        assert config_path.exists()
        assert config_path.name == "project.json"

        import json
        config = json.loads(config_path.read_text())
        assert "workspace" in config

    def test_emit_project_config_when_emit_flag_true(
        self,
        claude: ClaudeIntegration,
        tmp_path: Path,
    ) -> None:
        claude.ensure_workspace_settings(
            tmp_path,
            None,
            emit_project_config=True,
        )

        # Should create CLAUDE.md
        claude_md = tmp_path / "CLAUDE.md"
        assert claude_md.exists()

        content = claude_md.read_text()
        assert "Claude Code Workspace" in content
