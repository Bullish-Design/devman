"""Tests for Claude Code integration helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from devman.claude_code import check_claude_code, generate_claude_code_settings
from devman.models.workspace import WorkspaceConfig


def test_generate_claude_code_settings(tmp_path: Path) -> None:
    """Generate settings payload for Claude Code."""
    workspace_root = tmp_path / "workspace"
    devman_dir = workspace_root / ".devman"
    devman_dir.mkdir(parents=True)

    config = WorkspaceConfig(
        root=workspace_root,
        devman_dir=devman_dir,
        name="workspace",
        tags=[],
        group=None,
        tmuxp_workspace=None,
        tmuxp_session_name=None,
        claude_interaction=devman_dir / "interaction.md",
        claude_emit_project_config=True,
        nvim_init=None,
        nvim_listen=None,
        nvim_sessions_dir=None,
        nvim_default_session=None,
    )

    settings = generate_claude_code_settings(config)

    assert settings["workspace_name"] == "workspace"
    assert settings["workspace_root"] == str(workspace_root)
    assert settings["interaction_file"] == str(devman_dir / "interaction.md")
    assert settings["emit_project_config"] is True


def test_check_claude_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """Detect Claude Code availability."""
    monkeypatch.setattr("devman.claude_code.shutil.which", lambda _: "/usr/bin/claude")
    assert check_claude_code() is True

    monkeypatch.setattr("devman.claude_code.shutil.which", lambda _: None)
    assert check_claude_code() is False
