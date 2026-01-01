"""Unit tests for onboarding module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import typer

from devman.onboarding import wizard


class TestWizard:
    """Tests for onboarding wizard."""

    def test_run_creates_devman_directory(self, tmp_path: Path) -> None:
        with patch("devman.onboarding.wizard._report_dependencies"):
            result = wizard.run(root=str(tmp_path))

            assert result == tmp_path / ".devman"
            assert (tmp_path / ".devman").exists()

    def test_run_creates_required_files(self, tmp_path: Path) -> None:
        with patch("devman.onboarding.wizard._report_dependencies"):
            wizard.run(root=str(tmp_path))

            devman_dir = tmp_path / ".devman"
            assert (devman_dir / "devman.toml").exists()
            assert (devman_dir / "interaction.md").exists()
            assert (devman_dir / "nvim" / "init.lua").exists()

    def test_run_exits_if_devman_exists_without_force(self, tmp_path: Path) -> None:
        devman_dir = tmp_path / ".devman"
        devman_dir.mkdir()
        (devman_dir / "test.txt").write_text("test", encoding="utf-8")

        with pytest.raises(typer.Exit):
            wizard.run(root=str(tmp_path), force=False)

    def test_run_overwrites_if_force_flag_set(self, tmp_path: Path) -> None:
        # Create existing .devman with file
        devman_dir = tmp_path / ".devman"
        devman_dir.mkdir()
        test_file = devman_dir / "test.txt"
        test_file.write_text("old content", encoding="utf-8")

        with patch("devman.onboarding.wizard._report_dependencies"):
            wizard.run(root=str(tmp_path), force=True)

            # Old file should be gone
            assert not test_file.exists()

            # New files should exist
            assert (devman_dir / "devman.toml").exists()

    def test_run_uses_current_dir_when_root_not_specified(self) -> None:
        with patch("devman.onboarding.wizard._report_dependencies"):
            with patch("pathlib.Path.cwd") as mock_cwd:
                with patch("pathlib.Path.mkdir"):
                    with patch("pathlib.Path.write_text"):
                        mock_cwd.return_value = Path("/fake/path")

                        result = wizard.run()

                        expected = Path("/fake/path") / ".devman"
                        assert result == expected

    def test_run_expands_tilde_in_root(self, tmp_path: Path) -> None:
        with patch("devman.onboarding.wizard._report_dependencies"):
            with patch("pathlib.Path.expanduser") as mock_expand:
                mock_expand.return_value = tmp_path
                with patch("pathlib.Path.mkdir"):
                    with patch("pathlib.Path.write_text"):
                        wizard.run(root="~/test")

                        mock_expand.assert_called()

    def test_rendered_toml_contains_workspace_name(self, tmp_path: Path) -> None:
        with patch("devman.onboarding.wizard._report_dependencies"):
            wizard.run(root=str(tmp_path))

            toml_file = tmp_path / ".devman" / "devman.toml"
            content = toml_file.read_text()

            assert tmp_path.name in content

    def test_report_dependencies_warns_on_missing_tools(self) -> None:
        with patch("devman.onboarding.wizard.doctor_run") as mock_doctor:
            with patch("typer.echo") as mock_echo:
                mock_doctor.return_value = {
                    "tmux": True,
                    "claude": False,
                }

                wizard._report_dependencies()

                # Should report missing tools
                mock_echo.assert_called()
                calls = [str(call) for call in mock_echo.call_args_list]
                assert any("Missing" in str(call) for call in calls)

    def test_report_dependencies_silent_when_all_available(self) -> None:
        with patch("devman.onboarding.wizard.doctor_run") as mock_doctor:
            with patch("typer.echo") as mock_echo:
                mock_doctor.return_value = {
                    "tmux": True,
                    "claude": True,
                    "nvim": True,
                }

                wizard._report_dependencies()

                # Should not echo anything
                mock_echo.assert_not_called()
