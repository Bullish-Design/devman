from __future__ import annotations

import os
from datetime import datetime
from importlib import resources
from pathlib import Path
import shutil
import subprocess
from typing import Optional

SEED_TEMPLATES_STRATEGY_EXTERNAL_REPO = "external_repo_path"
SEED_TEMPLATES_STRATEGY_PACKAGE_ASSETS = "package_assets"
DEFAULT_SEED_TEMPLATES_STRATEGY = SEED_TEMPLATES_STRATEGY_EXTERNAL_REPO
DEFAULT_SEED_TEMPLATES_REPO = Path("~/.devman-templates").expanduser()
SEED_TEMPLATES_ENV_VAR = "DEVMAN_SEED_TEMPLATES_REPO"


def _copy_seed_file_type_template(
    destination: Path,
    strategy: str,
    seed_templates_repo: Optional[Path] = None,
) -> None:
    """Copy the `file-type` seed template to the destination directory.

    Strategy options:
    - `external_repo_path` (default): read template from an external templates repository
      (`seed_templates_repo`, then `$DEVMAN_SEED_TEMPLATES_REPO`, then
      `~/.devman-templates`).
    - `package_assets` (optional fallback): read bundled package assets via
      `importlib.resources`.
    """
    if strategy == SEED_TEMPLATES_STRATEGY_EXTERNAL_REPO:
        configured_repo = (
            seed_templates_repo
            or Path(os.environ[SEED_TEMPLATES_ENV_VAR]).expanduser()
            if SEED_TEMPLATES_ENV_VAR in os.environ
            else DEFAULT_SEED_TEMPLATES_REPO
        )
        file_type_template = configured_repo / "file-type"
        if not file_type_template.exists():
            raise ValueError(
                "Seed template 'file-type' not found at "
                f"{file_type_template}. Configure {SEED_TEMPLATES_ENV_VAR}, pass "
                "seed_templates_repo, or use strategy='package_assets'."
            )

        shutil.copytree(file_type_template, destination)
        return

    if strategy == SEED_TEMPLATES_STRATEGY_PACKAGE_ASSETS:
        package_template = resources.files("devman").joinpath(
            "seed_templates", "file-type"
        )
        with resources.as_file(package_template) as local_template:
            shutil.copytree(local_template, destination)
        return

    raise ValueError(
        "Unknown seed templates strategy "
        f"'{strategy}'. Expected one of: "
        f"{SEED_TEMPLATES_STRATEGY_EXTERNAL_REPO}, "
        f"{SEED_TEMPLATES_STRATEGY_PACKAGE_ASSETS}"
    )


def init_devman_store(
    seed_templates_strategy: str = DEFAULT_SEED_TEMPLATES_STRATEGY,
    seed_templates_repo: Optional[Path] = None,
) -> Path:
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

    _copy_seed_file_type_template(
        destination=templates_dir / "file-type",
        strategy=seed_templates_strategy,
        seed_templates_repo=seed_templates_repo,
    )

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

    if not devman_path.exists():
        return "unversioned"

    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=devman_path,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return "unversioned"

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
