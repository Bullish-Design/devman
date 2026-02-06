from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Optional
from datetime import datetime

import tomllib
import tomli_w


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

    copier_cmd = ["copier", "copy"]

    if template_version != "unversioned":
        copier_cmd.extend(["--vcs-ref", template_version])

    if answers_file:
        copier_cmd.extend(["--data-file", str(answers_file)])

    copier_cmd.extend([str(template_path), str(target_dir)])

    result = subprocess.run(copier_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"Copier failed: {result.stderr}")

    # Execute .devman-bootstrap.py if it exists
    bootstrap_script = target_dir / ".devman-bootstrap.py"
    if bootstrap_script.exists():
        result = subprocess.run(
            ["python", str(bootstrap_script)],
            cwd=target_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Bootstrap script failed: {result.stderr}")

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
