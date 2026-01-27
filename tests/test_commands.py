# tests/test_commands.py
"""Test command implementations."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devman.cli import app

runner = CliRunner()

# Skip markers for external tool dependencies
requires_copier = pytest.mark.skipif(
    shutil.which("copier") is None, reason="copier not available"
)
requires_nix = pytest.mark.skipif(
    shutil.which("nix-instantiate") is None, reason="nix-instantiate not available"
)


class TestInitCommand:
    """Tests for init command."""

    @requires_copier
    @requires_nix
    def test_init_creates_files(self, tmp_project: Path, devman_dir: Path):
        """Verify init creates all required files."""
        orig_cwd = os.getcwd()
        os.chdir(tmp_project)
        try:
            result = runner.invoke(
                app,
                [
                    "init",
                    "--devman-dir",
                    str(devman_dir),
                    "--project-name",
                    "test-project",
                ],
            )

            assert result.exit_code == 0
            assert devman_dir.exists()
            assert (devman_dir / "devenv.nix").exists()
            assert (devman_dir / "justfile").exists()
            assert (devman_dir / "state.yaml").exists()
            assert (devman_dir / ".envrc").exists()
            assert (devman_dir / "pyproject.toml").exists()
        finally:
            os.chdir(orig_cwd)

    @requires_copier
    @requires_nix
    def test_init_validates_nix_syntax(self, tmp_project: Path, devman_dir: Path):
        """Verify generated devenv.nix has valid syntax."""
        import subprocess

        orig_cwd = os.getcwd()
        os.chdir(tmp_project)
        try:
            result = runner.invoke(
                app,
                ["init", "--devman-dir", str(devman_dir)],
            )
            assert result.exit_code == 0

            # Verify nix can parse it
            nix_result = subprocess.run(
                ["nix-instantiate", "--parse", str(devman_dir / "devenv.nix")],
                capture_output=True,
            )
            assert nix_result.returncode == 0
        finally:
            os.chdir(orig_cwd)

    @requires_copier
    @requires_nix
    def test_init_respects_python_version(self, tmp_project: Path, devman_dir: Path):
        """Verify python version is correctly set."""
        orig_cwd = os.getcwd()
        os.chdir(tmp_project)
        try:
            result = runner.invoke(
                app,
                ["init", "--devman-dir", str(devman_dir), "--python-version", "3.13"],
            )
            assert result.exit_code == 0

            devenv_content = (devman_dir / "devenv.nix").read_text()
            assert 'version = "3.13"' in devenv_content
        finally:
            os.chdir(orig_cwd)

    @requires_copier
    @requires_nix
    def test_init_includes_just_package(self, tmp_project: Path, devman_dir: Path):
        """Verify devenv.nix includes just package (critical fix)."""
        orig_cwd = os.getcwd()
        os.chdir(tmp_project)
        try:
            result = runner.invoke(
                app,
                ["init", "--devman-dir", str(devman_dir)],
            )
            assert result.exit_code == 0

            devenv_content = (devman_dir / "devenv.nix").read_text()
            assert "pkgs.just" in devenv_content
        finally:
            os.chdir(orig_cwd)

    def test_init_fails_if_exists_without_force(
        self, tmp_project: Path, devman_dir: Path
    ):
        """Verify init fails if directory exists without --force."""
        devman_dir.mkdir(parents=True)

        orig_cwd = os.getcwd()
        os.chdir(tmp_project)
        try:
            result = runner.invoke(
                app,
                ["init", "--devman-dir", str(devman_dir)],
            )
            assert result.exit_code == 1
            assert "already exists" in result.output
        finally:
            os.chdir(orig_cwd)

    @requires_copier
    @requires_nix
    def test_init_overwrites_with_force(self, tmp_project: Path, devman_dir: Path):
        """Verify init overwrites with --force flag."""
        devman_dir.mkdir(parents=True)
        (devman_dir / "test.txt").write_text("old content")

        orig_cwd = os.getcwd()
        os.chdir(tmp_project)
        try:
            result = runner.invoke(
                app,
                ["init", "--devman-dir", str(devman_dir), "--force"],
            )
            assert result.exit_code == 0
            assert not (devman_dir / "test.txt").exists()
        finally:
            os.chdir(orig_cwd)

    @requires_copier
    @requires_nix
    def test_init_creates_state_file(self, tmp_project: Path, devman_dir: Path):
        """Verify state.yaml is created with correct structure."""
        import yaml

        orig_cwd = os.getcwd()
        os.chdir(tmp_project)
        try:
            result = runner.invoke(
                app,
                ["init", "--devman-dir", str(devman_dir), "--project-name", "my-project"],
            )
            assert result.exit_code == 0

            with open(devman_dir / "state.yaml") as f:
                state = yaml.safe_load(f)

            assert "template" in state
            assert "variables" in state
            assert "history" in state
            assert state["template"]["name"] == "my-project"
            assert state["variables"]["project_name"] == "my-project"
        finally:
            os.chdir(orig_cwd)

    @requires_copier
    @requires_nix
    def test_init_uses_cwd_name_as_default(self, tmp_project: Path, devman_dir: Path):
        """Verify project name defaults to current directory name."""
        import yaml

        orig_cwd = os.getcwd()
        os.chdir(tmp_project)
        try:
            result = runner.invoke(
                app,
                ["init", "--devman-dir", str(devman_dir)],
            )
            assert result.exit_code == 0

            with open(devman_dir / "state.yaml") as f:
                state = yaml.safe_load(f)

            assert state["variables"]["project_name"] == tmp_project.name
        finally:
            os.chdir(orig_cwd)

    def test_init_rolls_back_on_failure(self, tmp_project: Path, devman_dir: Path):
        """Verify directory is removed if init fails."""
        orig_cwd = os.getcwd()
        os.chdir(tmp_project)
        try:
            # Use invalid template to trigger failure
            result = runner.invoke(
                app,
                ["init", "--devman-dir", str(devman_dir), "--template", "nonexistent"],
            )
            assert result.exit_code == 1
            assert not devman_dir.exists()
        finally:
            os.chdir(orig_cwd)


class TestValidateCommand:
    """Tests for validate command."""

    @requires_copier
    @requires_nix
    def test_validate_success(self, tmp_project: Path, devman_dir: Path):
        """Verify validate succeeds for valid project."""
        orig_cwd = os.getcwd()
        os.chdir(tmp_project)
        try:
            # Create project first
            runner.invoke(
                app,
                ["init", "--devman-dir", str(devman_dir)],
            )

            result = runner.invoke(
                app,
                ["validate", "--devman-dir", str(devman_dir)],
            )
            assert result.exit_code == 0
        finally:
            os.chdir(orig_cwd)

    def test_validate_fails_missing_dir(self, tmp_project: Path, devman_dir: Path):
        """Verify validate fails when directory doesn't exist."""
        orig_cwd = os.getcwd()
        os.chdir(tmp_project)
        try:
            result = runner.invoke(
                app,
                ["validate", "--devman-dir", str(devman_dir)],
            )
            assert result.exit_code == 1
            assert "does not exist" in result.output
        finally:
            os.chdir(orig_cwd)

    def test_validate_detects_missing_devenv(
        self, tmp_project: Path, devman_dir: Path
    ):
        """Verify validate detects missing devenv.nix."""
        devman_dir.mkdir(parents=True)
        (devman_dir / "justfile").write_text("test:")
        (devman_dir / "state.yaml").write_text("template: {}")

        orig_cwd = os.getcwd()
        os.chdir(tmp_project)
        try:
            result = runner.invoke(
                app,
                ["validate", "--devman-dir", str(devman_dir)],
            )
            assert result.exit_code == 1
            assert "devenv.nix" in result.output
        finally:
            os.chdir(orig_cwd)

    @requires_nix
    def test_validate_detects_invalid_nix(self, tmp_project: Path, devman_dir: Path):
        """Verify validate detects invalid Nix syntax."""
        devman_dir.mkdir(parents=True)
        (devman_dir / "devenv.nix").write_text("{ invalid nix syntax")
        (devman_dir / "justfile").write_text("test:")
        (devman_dir / "state.yaml").write_text("template: {}")

        orig_cwd = os.getcwd()
        os.chdir(tmp_project)
        try:
            result = runner.invoke(
                app,
                ["validate", "--devman-dir", str(devman_dir)],
            )
            assert result.exit_code == 1
            assert "invalid" in result.output.lower()
        finally:
            os.chdir(orig_cwd)


class TestCleanCommand:
    """Tests for clean command."""

    @requires_copier
    @requires_nix
    def test_clean_dry_run(self, tmp_project: Path, devman_dir: Path):
        """Verify clean --dry-run doesn't remove anything."""
        orig_cwd = os.getcwd()
        os.chdir(tmp_project)
        try:
            # Create project
            runner.invoke(
                app,
                ["init", "--devman-dir", str(devman_dir)],
            )

            # Create test-results
            test_results = devman_dir / "test-results"
            test_results.mkdir()
            (test_results / "report.json").write_text("{}")

            result = runner.invoke(
                app,
                ["clean", "--devman-dir", str(devman_dir), "--dry-run"],
            )
            assert result.exit_code == 0
            assert test_results.exists()
            assert "[DRY RUN]" in result.output
        finally:
            os.chdir(orig_cwd)

    @requires_copier
    @requires_nix
    def test_clean_removes_test_results(self, tmp_project: Path, devman_dir: Path):
        """Verify clean removes test-results directory."""
        orig_cwd = os.getcwd()
        os.chdir(tmp_project)
        try:
            # Create project
            runner.invoke(
                app,
                ["init", "--devman-dir", str(devman_dir)],
            )

            # Create test-results
            test_results = devman_dir / "test-results"
            test_results.mkdir()
            (test_results / "report.json").write_text("{}")

            result = runner.invoke(
                app,
                ["clean", "--devman-dir", str(devman_dir)],
            )
            assert result.exit_code == 0
            assert not test_results.exists()
        finally:
            os.chdir(orig_cwd)

    @requires_copier
    @requires_nix
    def test_clean_all_removes_caches(self, tmp_project: Path, devman_dir: Path):
        """Verify clean --all removes cache directories."""
        orig_cwd = os.getcwd()
        os.chdir(tmp_project)
        try:
            # Create project
            runner.invoke(
                app,
                ["init", "--devman-dir", str(devman_dir)],
            )

            # Create cache dirs
            (devman_dir / ".devenv").mkdir()
            (devman_dir / ".direnv").mkdir()

            result = runner.invoke(
                app,
                ["clean", "--devman-dir", str(devman_dir), "--all"],
            )
            assert result.exit_code == 0
            assert not (devman_dir / ".devenv").exists()
            assert not (devman_dir / ".direnv").exists()
        finally:
            os.chdir(orig_cwd)
