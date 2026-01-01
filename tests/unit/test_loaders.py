"""Unit tests for loaders module."""

from __future__ import annotations

from pathlib import Path

import pytest

from devman.loaders import load_workspace_config


class TestLoadWorkspaceConfig:
    """Tests for load_workspace_config function."""

    def test_loads_minimal_config(self, tmp_path: Path) -> None:
        devman_dir = tmp_path / ".devman"
        devman_dir.mkdir()

        # Create minimal devman.toml
        config_file = devman_dir / "devman.toml"
        config_file.write_text(
            '[workspace]\nname = "test-workspace"\n',
            encoding="utf-8"
        )

        config = load_workspace_config(devman_dir)

        assert config.name == "test-workspace"
        assert config.root == tmp_path
        assert config.devman_dir == devman_dir

    def test_loads_full_config(self, tmp_path: Path) -> None:
        devman_dir = tmp_path / ".devman"
        devman_dir.mkdir()

        # Create interaction.md
        interaction_file = devman_dir / "interaction.md"
        interaction_file.write_text("# Test Interaction", encoding="utf-8")

        # Create nvim init
        nvim_dir = devman_dir / "nvim"
        nvim_dir.mkdir()
        init_file = nvim_dir / "init.lua"
        init_file.write_text("-- Neovim init", encoding="utf-8")

        # Create full devman.toml
        config_file = devman_dir / "devman.toml"
        config_file.write_text(
            """
[workspace]
name = "full-workspace"

[claude]
interaction = "interaction.md"
emit_project_config = true

[nvim]
listen = "/tmp/nvim.sock"
init = "nvim/init.lua"
default_session = "session.vim"
sessions_dir = "nvim/sessions"

[tmuxp]
workspace = "tmuxp.yaml"
session_name = "my-session"
""",
            encoding="utf-8"
        )

        config = load_workspace_config(devman_dir)

        assert config.name == "full-workspace"
        assert config.claude_interaction == interaction_file
        assert config.claude_emit_project_config is True
        assert config.nvim_listen == Path("/tmp/nvim.sock")
        assert config.nvim_init == init_file
        assert config.nvim_default_session == "session.vim"
        assert config.tmuxp_session_name == "my-session"

    def test_raises_when_config_missing(self, tmp_path: Path) -> None:
        devman_dir = tmp_path / ".devman"
        devman_dir.mkdir()

        with pytest.raises(FileNotFoundError):
            load_workspace_config(devman_dir)

    def test_handles_relative_paths(self, tmp_path: Path) -> None:
        devman_dir = tmp_path / ".devman"
        devman_dir.mkdir()

        # Create config with relative paths
        config_file = devman_dir / "devman.toml"
        config_file.write_text(
            """
[workspace]
name = "test"

[claude]
interaction = "interaction.md"

[nvim]
init = "nvim/init.lua"
""",
            encoding="utf-8"
        )

        config = load_workspace_config(devman_dir)

        # Paths should be resolved relative to devman_dir
        assert config.claude_interaction == devman_dir / "interaction.md"
        assert config.nvim_init == devman_dir / "nvim" / "init.lua"

    def test_handles_absolute_paths(self, tmp_path: Path) -> None:
        devman_dir = tmp_path / ".devman"
        devman_dir.mkdir()

        # Create config with absolute path
        config_file = devman_dir / "devman.toml"
        config_file.write_text(
            f"""
[workspace]
name = "test"

[nvim]
listen = "/tmp/nvim.sock"
""",
            encoding="utf-8"
        )

        config = load_workspace_config(devman_dir)

        # Absolute path should remain absolute
        assert config.nvim_listen == Path("/tmp/nvim.sock")

    def test_optional_fields_are_none_when_missing(self, tmp_path: Path) -> None:
        devman_dir = tmp_path / ".devman"
        devman_dir.mkdir()

        config_file = devman_dir / "devman.toml"
        config_file.write_text(
            '[workspace]\nname = "minimal"\n',
            encoding="utf-8"
        )

        config = load_workspace_config(devman_dir)

        assert config.claude_interaction is None
        assert config.nvim_listen is None
        assert config.nvim_init is None
        assert config.tmuxp_workspace is None
