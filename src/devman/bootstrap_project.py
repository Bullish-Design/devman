#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "copier>=9.0.0",
#   "tomli-w>=1.0.0",
# ]
# ///

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from typing import Optional
from datetime import datetime

import tomllib
import tomli_w

from devman.subprocess_utils import run_checked_subprocess


def _build_uv_run_command(*args: str) -> list[str]:
    return [sys.executable, "-m", "uv", "run", "--python", sys.executable, *args]


def _run_checked(
    command: list[str],
    cwd: Path | None = None,
    context: str = "Command",
):
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise RuntimeError(
            f"{context} failed with exit code {exc.returncode}. stderr: {stderr}"
        ) from exc


def bootstrap_project(
    project_template: str,
    target_dir: Path,
    answers_file: Optional[Path] = None,
    template_version: Optional[str] = None,
) -> dict:
    """Bootstrap a complete project using a meta-template."""
    store_root = Path.home() / ".devman-store"
    devman_path = store_root / "devman"
    template_path = devman_path / f".devman/.templates/{project_template}"

    if not template_path.exists():
        raise ValueError(f"Project template not found: {project_template}")

    if not template_version:
        from devman.bootstrap import get_current_devman_version
        template_version = get_current_devman_version()

    copier_cmd = _build_uv_run_command("copier", "copy")

    if template_version != "unversioned":
        copier_cmd.extend(["--vcs-ref", template_version])

    if answers_file:
        copier_cmd.extend(["--data-file", str(answers_file)])

    copier_cmd.extend([str(template_path), str(target_dir)])

    run_checked_subprocess(copier_cmd, context="Copier copy")

    # Execute .devman-bootstrap.py if it exists
    bootstrap_script = target_dir / ".devman-bootstrap.py"
    if bootstrap_script.exists():
        run_checked_subprocess(
            _build_uv_run_command(str(bootstrap_script)),
            cwd=target_dir,
            context="Bootstrap script",
        )

    # Read/update project metadata
    metadata_file = target_dir / ".devman-project.toml"
    metadata = {}
    if metadata_file.exists():
        with open(metadata_file, "rb") as f:
            metadata = tomllib.load(f)

    if "template" not in metadata:
        metadata["template"] = {}

    metadata["template"]["name"] = project_template
    metadata["template"]["version"] = template_version
    metadata["template"]["created_at"] = datetime.now().isoformat()

    with open(metadata_file, "wb") as f:
        tomli_w.dump(metadata, f)

    return {
        "project_path": target_dir,
        "file_types": metadata.get("file_types", []),
        "template": project_template,
        "version": template_version,
    }
