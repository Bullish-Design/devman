"""Tests for workspace configuration loading."""

from __future__ import annotations

from pathlib import Path

from devman.models.workspace import WorkspaceConfig


def test_minimal_workspace_config(tmp_path: Path) -> None:
    """Ensure minimal .devman directory loads defaults."""
    workspace_root = tmp_path / "demo"
    devman_dir = workspace_root / ".devman"
    devman_dir.mkdir(parents=True)

    config = WorkspaceConfig.load(devman_dir)

    assert config.root == workspace_root
    assert config.devman_dir == devman_dir
    assert config.name == "demo"
    assert config.tags == []
    assert config.group is None
    assert config.tmuxp_workspace is None
    assert config.tmuxp_session_name is None
    assert config.claude_interaction is None
    assert config.claude_emit_project_config is False
    assert config.nvim_init is None
    assert config.nvim_listen == workspace_root / ".devman" / ".state" / "nvim.sock"
    assert config.nvim_sessions_dir is None
    assert config.nvim_default_session is None


def test_load_workspace_toml(tmp_path: Path) -> None:
    """Load workspace configuration from devman.toml."""
    workspace_root = tmp_path / "my-app"
    devman_dir = workspace_root / ".devman"
    devman_dir.mkdir(parents=True)

    (devman_dir / "devman.toml").write_text(
        """
[workspace]
name = "my-app"
tags = ["api", "web"]
group = "client-x"

[tmuxp]
workspace = "workspace.tmuxp.yaml"
session_name = "my-app"

[claude_code]
interaction = "interaction.md"
emit_project_config = false

[nvim]
init = "nvim/init.lua"
listen = ".devman/.state/nvim.sock"
sessions_dir = "sessions"
default_session = "home.vim"
""".strip()
    )

    config = WorkspaceConfig.load(devman_dir)

    assert config.name == "my-app"
    assert config.tags == ["api", "web"]
    assert config.group == "client-x"
    assert config.tmuxp_workspace == devman_dir / "workspace.tmuxp.yaml"
    assert config.tmuxp_session_name == "my-app"
    assert config.claude_interaction == devman_dir / "interaction.md"
    assert config.claude_emit_project_config is False
    assert config.nvim_init == devman_dir / "nvim/init.lua"
    assert config.nvim_listen == workspace_root / ".devman/.state/nvim.sock"
    assert config.nvim_sessions_dir == devman_dir / "sessions"
    assert config.nvim_default_session == "home.vim"
