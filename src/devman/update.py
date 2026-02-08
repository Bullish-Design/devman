from __future__ import annotations

from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

import tomllib
import tomli_w

from devman.subprocess_utils import run_checked_subprocess


def update_file_type(
    file_type: str,
    target_version: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """Update a file type configuration to a new template version."""
    store_root = Path.home() / ".devman-store"
    type_path = store_root / file_type

    if not type_path.exists():
        raise ValueError(f"File type not found: {file_type}")

    config_path = type_path / ".devman/config.toml"
    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    current_version = config.get("template", {}).get("devman_version", "unknown")

    if not target_version:
        from devman.bootstrap import get_current_devman_version
        target_version = get_current_devman_version()

    if current_version == target_version:
        return {
            "success": True,
            "message": f"Already at version {target_version}",
            "current_version": current_version,
            "target_version": target_version,
            "changes": [],
            "dry_run": dry_run,
        }

    copier_cmd = ["copier", "update"]

    if target_version != "unversioned":
        copier_cmd.extend(["--vcs-ref", target_version])

    if dry_run:
        copier_cmd.append("--pretend")

    copier_cmd.append(str(type_path))

    result = run_checked_subprocess(copier_cmd, context="Copier update")

    if not dry_run:
        config["template"]["devman_version"] = target_version
        config["template"]["updated_at"] = datetime.now(timezone.utc).isoformat()

        with open(config_path, "wb") as f:
            tomli_w.dump(config, f)

    return {
        "success": True,
        "current_version": current_version,
        "target_version": target_version,
        "changes": result.stdout.splitlines(),
        "dry_run": dry_run,
    }


def update_project(
    project_path: Path,
    target_version: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """Update a project to a new meta-template version."""
    metadata_file = project_path / ".devman-project.toml"

    if not metadata_file.exists():
        raise ValueError(f"Not a devman project: {project_path}")

    with open(metadata_file, "rb") as f:
        metadata = tomllib.load(f)

    current_version = metadata.get("template", {}).get("version", "unknown")
    template_name = metadata.get("template", {}).get("name")

    if not template_name:
        raise ValueError("Project metadata missing template name")

    if not target_version:
        from devman.bootstrap import get_current_devman_version
        target_version = get_current_devman_version()

    copier_cmd = ["copier", "update"]

    if target_version != "unversioned":
        copier_cmd.extend(["--vcs-ref", target_version])

    if dry_run:
        copier_cmd.append("--pretend")

    copier_cmd.append(str(project_path))

    result = run_checked_subprocess(copier_cmd, context="Copier update")

    if not dry_run:
        metadata["template"]["version"] = target_version
        metadata["template"]["updated_at"] = datetime.now(timezone.utc).isoformat()

        with open(metadata_file, "wb") as f:
            tomli_w.dump(metadata, f)

    return {
        "success": True,
        "template": template_name,
        "current_version": current_version,
        "target_version": target_version,
        "changes": result.stdout.splitlines(),
        "dry_run": dry_run,
    }
