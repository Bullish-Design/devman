# tests/test_validation.py
"""Test validation utilities."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from devman.validation import validate_nix_syntax, validate_template_pretend


@pytest.mark.skipif(shutil.which("nix-instantiate") is None, reason="nix-instantiate not available")
def test_validate_nix_syntax_valid(tmp_path: Path):
    """Test validation of valid Nix syntax."""
    nix_file = tmp_path / "test.nix"
    nix_file.write_text("{ pkgs, ... }: { packages = [ pkgs.git ]; }")

    # Should not raise
    validate_nix_syntax(nix_file)


@pytest.mark.skipif(shutil.which("nix-instantiate") is None, reason="nix-instantiate not available")
def test_validate_nix_syntax_invalid(tmp_path: Path):
    """Test validation of invalid Nix syntax."""
    nix_file = tmp_path / "test.nix"
    nix_file.write_text("{ invalid syntax")

    with pytest.raises(ValueError, match="Invalid Nix syntax"):
        validate_nix_syntax(nix_file)


@pytest.mark.skipif(shutil.which("copier") is None, reason="copier not available")
def test_validate_template_pretend_valid(template_dir: Path, tmp_path: Path):
    """Test template validation with valid template."""
    data = {
        "project_name": "test",
        "python_version": "3.12",
        "include_postgres": False,
        "include_redis": False,
    }

    # Should not raise
    validate_template_pretend(template_dir, tmp_path, data)


@pytest.mark.skipif(shutil.which("copier") is None, reason="copier not available")
def test_validate_template_pretend_invalid(tmp_path: Path):
    """Test template validation with invalid template."""
    invalid_template = tmp_path / "invalid_template"
    invalid_template.mkdir()

    data = {"project_name": "test"}

    with pytest.raises(ValueError, match="Template validation failed"):
        validate_template_pretend(invalid_template, tmp_path, data)
