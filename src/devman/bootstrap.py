from __future__ import annotations

from pathlib import Path
import subprocess
import shutil
from typing import Optional
from datetime import datetime


def init_devman_store() -> Path:
    """Initialize devman store with git-backed meta-configuration."""
    store_root = Path.home() / ".devman-store"
    devman_path = store_root / "devman"

    if devman_path.exists():
        raise ValueError(f"Devman store already initialized at {store_root}")

    # Create structure
    devman_path.mkdir(parents=True)
    devman_config = devman_path / ".devman"
    devman_config.mkdir()

    templates_dir = devman_config / ".templates"
    templates_dir.mkdir()

    workflows_dir = devman_config / "workflows"
    workflows_dir.mkdir()

    # Copy seed templates into the templates directory
    seed_templates_path = Path(__file__).parent / "seed_templates"
    if seed_templates_path.exists():
        file_type_template = seed_templates_path / "file-type"
        if file_type_template.exists():
            shutil.copytree(file_type_template, templates_dir / "file-type")

    # Create minimal config
    config_path = devman_config / "config.toml"
    config_path.write_text(
        '[devman]\n'
        'version = "0.1.0"\n'
        'store_path = "~/.devman-store"\n'
    )

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=devman_path, check=True)
    subprocess.run(["git", "add", "."], cwd=devman_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "[init] Initialize devman store"],
        cwd=devman_path,
        check=True,
    )
    subprocess.run(
        ["git", "tag", "-a", "v0.1.0", "-m", "Initial devman version"],
        cwd=devman_path,
        check=True,
    )

    return store_root


def get_current_devman_version() -> str:
    """Get current devman template version from git tags."""
    store_root = Path.home() / ".devman-store"
    devman_path = store_root / "devman"

    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        cwd=devman_path,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return "unversioned"

    return result.stdout.strip()


def bootstrap_file_type(
    file_type: str,
    answers_file: Optional[Path] = None,
    template_version: Optional[str] = None,
) -> Path:
    """Bootstrap a new file type using copier templates."""
    store_root = Path.home() / ".devman-store"
    devman_path = store_root / "devman"
    template_path = devman_path / ".devman/.templates/file-type"
    target_path = store_root / file_type

    if target_path.exists():
        raise ValueError(f"File type already exists: {file_type}")

    if not template_version:
        template_version = get_current_devman_version()

    copier_cmd = ["copier", "copy"]

    if template_version != "unversioned":
        copier_cmd.extend(["--vcs-ref", template_version])

    if answers_file:
        copier_cmd.extend(["--data-file", str(answers_file)])

    copier_cmd.extend([str(template_path), str(target_path.parent)])

    result = subprocess.run(copier_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"Copier failed: {result.stderr}")

    # Add version metadata to config
    config_path = target_path / ".devman/config.toml"
    if config_path.exists():
        with open(config_path, "a") as f:
            f.write("\n[template]\n")
            f.write('name = "file-type"\n')
            f.write(f'devman_version = "{template_version}"\n')
            f.write(f'created_at = "{datetime.now().isoformat()}"\n')

    return target_path
