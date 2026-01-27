# src/devman/validation.py
"""Validation utilities."""

from __future__ import annotations

import subprocess
from pathlib import Path

from devman.template import format_data_payload


def validate_template_pretend(
    template_path: Path, dest: Path, data: dict[str, object]
) -> None:
    """Run copier in pretend mode to check template."""
    result = subprocess.run(
        [
            "copier",
            "copy",
            "--pretend",
            "--data-file",
            "-",
            "--defaults",
            str(template_path),
            str(dest),
        ],
        input=format_data_payload(data),
        text=True,
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        raise ValueError(f"Template validation failed: {result.stderr}")


def validate_nix_syntax(devenv_file: Path) -> None:
    """Validate devenv.nix syntax using nix-instantiate."""
    result = subprocess.run(
        ["nix-instantiate", "--parse", str(devenv_file)],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise ValueError(f"Invalid Nix syntax: {result.stderr}")
