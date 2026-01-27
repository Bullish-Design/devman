# tests/test_template.py
"""Test template operations."""

from __future__ import annotations

from pathlib import Path

import pytest

from devman.template import format_data_payload, resolve_template_path


def test_resolve_template_path_bundled(template_dir: Path):
    """Test resolving bundled template by name."""
    script_dir = template_dir.parent.parent
    resolved = resolve_template_path("python-devenv", script_dir)
    assert resolved.exists()
    assert resolved.name == "python-devenv"


def test_resolve_template_path_absolute(template_dir: Path):
    """Test resolving template by absolute path."""
    script_dir = template_dir.parent.parent
    resolved = resolve_template_path(str(template_dir), script_dir)
    assert resolved == template_dir


def test_resolve_template_path_relative(template_dir: Path):
    """Test resolving template by relative path."""
    script_dir = template_dir.parent.parent
    relative_path = "./templates/python-devenv"
    resolved = resolve_template_path(relative_path, script_dir)
    assert resolved.exists()


def test_resolve_template_path_nonexistent():
    """Test that nonexistent template raises error."""
    with pytest.raises(ValueError, match="does not exist"):
        resolve_template_path("/nonexistent/path", Path.cwd())


def test_format_data_payload_strings():
    """Test formatting string values."""
    data = {"name": "test", "version": "1.0"}
    payload = format_data_payload(data)
    assert "name=test" in payload
    assert "version=1.0" in payload


def test_format_data_payload_booleans():
    """Test formatting boolean values."""
    data = {"enabled": True, "disabled": False}
    payload = format_data_payload(data)
    assert "enabled=true" in payload
    assert "disabled=false" in payload
