from __future__ import annotations

import os
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
import shutil
import subprocess
from typing import Optional

from devman.constants import (
    CONFIG_SUBPATH,
    DEVMAN_CONFIG_SUBPATH,
    TEMPLATES_SUBPATH,
    WORKFLOWS_SUBPATH,
    STORE_ROOT_USER_PATH,
    get_devman_meta_dir,
    get_store_root,
)
from devman.subprocess_utils import run_checked_subprocess

SEED_TEMPLATES_STRATEGY_EXTERNAL_REPO = "external_repo_path"
SEED_TEMPLATES_STRATEGY_PACKAGE_ASSETS = "package_assets"
DEFAULT_SEED_TEMPLATES_STRATEGY = SEED_TEMPLATES_STRATEGY_EXTERNAL_REPO
DEFAULT_SEED_TEMPLATES_REPO = Path("~/.devman-templates").expanduser()
SEED_TEMPLATES_ENV_VAR = "DEVMAN_SEED_TEMPLATES_REPO"
SEED_TEMPLATE_NAMES = ("file-type", "devenv.nix", "python")


def _copy_seed_template(
    template_name: str,
    destination: Path,
    strategy: str,
    seed_templates_repo: Optional[Path] = None,
) -> None:
    """Copy a seed template to the destination directory.

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
        source_template = configured_repo / template_name
        if not source_template.exists():
            raise ValueError(
                f"Seed template '{template_name}' not found at "
                f"{source_template}. Configure {SEED_TEMPLATES_ENV_VAR}, pass "
                "seed_templates_repo, or use strategy='package_assets'."
            )

        shutil.copytree(source_template, destination)
        return

    if strategy == SEED_TEMPLATES_STRATEGY_PACKAGE_ASSETS:
        package_template = resources.files("devman").joinpath("seed_templates", template_name)
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
    store_root = get_store_root()
    devman_path = get_devman_meta_dir()

    if devman_path.exists():
        raise ValueError(f"Devman store already initialized at {store_root}")

    # Create structure
    devman_path.mkdir(parents=True)
    devman_config = devman_path / DEVMAN_CONFIG_SUBPATH
    devman_config.mkdir()

    templates_dir = devman_config / TEMPLATES_SUBPATH.name
    templates_dir.mkdir()

    workflows_dir = devman_config / WORKFLOWS_SUBPATH.name
    workflows_dir.mkdir()

    for template_name in SEED_TEMPLATE_NAMES:
        _copy_seed_template(
            template_name=template_name,
            destination=templates_dir / template_name,
            strategy=seed_templates_strategy,
            seed_templates_repo=seed_templates_repo,
        )

    # Create minimal config
    config_path = devman_path / CONFIG_SUBPATH
    config_path.write_text(
        "[devman]\n"
        "version = \"0.1.0\"\n"
        f'store_path = "{STORE_ROOT_USER_PATH}"\n'
    )

    # Initialize git repo
    run_checked_subprocess(["git", "init"], cwd=devman_path, context="Git init")
    run_checked_subprocess(["git", "add", "."], cwd=devman_path, context="Git add")
    run_checked_subprocess(
        ["git", "commit", "-m", "[init] Initialize devman store"],
        cwd=devman_path,
        context="Git commit",
    )
    run_checked_subprocess(
        ["git", "tag", "-a", "v0.1.0", "-m", "Initial devman version"],
        cwd=devman_path,
        context="Git tag",
    )

    return store_root


def get_current_devman_version() -> str:
    """Get current devman template version from git tags."""
    devman_path = get_devman_meta_dir()

    if not devman_path.exists():
        return "unversioned"

    try:
        result = run_checked_subprocess(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=devman_path,
            context="Git describe",
        )
    except RuntimeError:
        return "unversioned"

    return result.stdout.strip()


def bootstrap_file_type(
    file_type: str,
    answers_file: Optional[Path] = None,
    template_version: Optional[str] = None,
) -> Path:
    """Bootstrap a new file type using copier templates."""
    store_root = get_store_root()
    devman_path = get_devman_meta_dir()
    generic_template_path = devman_path / TEMPLATES_SUBPATH / "file-type"
    dedicated_template_path = devman_path / TEMPLATES_SUBPATH / file_type
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

    if dedicated_template_path.exists():
        copier_cmd.extend([str(dedicated_template_path), str(store_root)])
    else:
        copier_cmd.extend([str(generic_template_path), str(target_path.parent)])

    run_checked_subprocess(copier_cmd, context="Copier copy")

    # Add version metadata to config
    config_path = target_path / CONFIG_SUBPATH
    if config_path.exists():
        with open(config_path, "a") as f:
            f.write("\n[template]\n")
            f.write('name = "file-type"\n')
            f.write(f'devman_version = "{template_version}"\n')
            f.write(f'created_at = "{datetime.now(timezone.utc).isoformat()}"\n')

    return target_path
