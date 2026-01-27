# tests/test_jj_info.py
"""Test jujutsu integration."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from devman.jj_info import get_jj_info


@pytest.mark.skipif(shutil.which("jj") is None, reason="jj not available")
def test_get_jj_info_in_repo(tmp_path):
    """Test getting jj info from a valid repo."""
    import os

    # Initialize jj repo
    result = subprocess.run(
        ["jj", "init", "--git"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
    )

    subprocess.run(
        ["jj", "bookmark", "create", "test-branch"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Change to repo directory
    old_cwd = os.getcwd()
    os.chdir(tmp_path)

    try:
        info = get_jj_info()
        assert info["bookmark"] is not None
        assert info["change_id"] is not None
    finally:
        os.chdir(old_cwd)


def test_get_jj_info_no_jj(monkeypatch):
    """Test getting jj info when jj is not available."""

    def mock_run(*args, **kwargs):
        raise FileNotFoundError("jj not found")

    monkeypatch.setattr(subprocess, "run", mock_run)

    info = get_jj_info()
    assert info["bookmark"] is None
    assert info["change_id"] is None
