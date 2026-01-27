# tests/test_container.py
"""Test container operations."""

from __future__ import annotations

import subprocess

import pytest

from devman.container import list_devman_containers


def test_list_devman_containers_empty(monkeypatch):
    """Test listing containers when none exist."""

    def mock_run(*args, **kwargs):
        class Result:
            returncode = 0
            stdout = ""

        return Result()

    monkeypatch.setattr(subprocess, "run", mock_run)

    containers = list_devman_containers()
    assert containers == []


def test_list_devman_containers_found(monkeypatch):
    """Test listing containers when some exist."""

    def mock_run(*args, **kwargs):
        class Result:
            returncode = 0
            stdout = "devman-main-abc123\ndevman-test-def456\nother-container\n"

        return Result()

    monkeypatch.setattr(subprocess, "run", mock_run)

    containers = list_devman_containers()
    assert len(containers) == 2
    assert "devman-main-abc123" in containers
    assert "devman-test-def456" in containers
    assert "other-container" not in containers


# Note: Container creation/cleanup tests require sudo and are skipped in CI
@pytest.mark.sudo
def test_create_and_cleanup_container():
    """Integration test for container creation and cleanup."""
    pytest.skip("Requires sudo access and nixos-container")
    # Implementation would test actual container operations
