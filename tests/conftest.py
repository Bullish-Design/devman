# tests/conftest.py
"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def tmp_project(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary project directory."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    # Initialize version control for testing
    # Try jj first, then git
    if shutil.which("jj"):
        subprocess.run(
            ["jj", "init", "--git"],
            cwd=project_dir,
            check=False,
            capture_output=True,
        )
    elif shutil.which("git"):
        subprocess.run(
            ["git", "init"],
            cwd=project_dir,
            check=False,
            capture_output=True,
        )

    yield project_dir

    # Cleanup
    if project_dir.exists():
        shutil.rmtree(project_dir, ignore_errors=True)


@pytest.fixture
def devman_dir(tmp_project: Path) -> Path:
    """Return .devman directory path."""
    return tmp_project / ".devman"


@pytest.fixture
def template_dir() -> Path:
    """Return path to bundled templates."""
    return Path(__file__).parent.parent / "templates" / "python-devenv"


@pytest.fixture
def mock_jj_info(monkeypatch):
    """Mock jujutsu info for testing."""

    def mock_get_jj_info():
        return {"bookmark": "test-branch", "change_id": "abc123def456"}

    from devman import jj_info

    monkeypatch.setattr(jj_info, "get_jj_info", mock_get_jj_info)
